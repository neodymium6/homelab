"""Offline certificate configuration and existing alias regressions."""
import importlib.util
from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
from jinja2.nativetypes import NativeEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "bastion/ansible/roles/traefik"
spec = importlib.util.spec_from_file_location(
    "traefik_tls", ROOT / "bastion/ansible/filter_plugins/traefik_tls.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class TraefikTLSTests(unittest.TestCase):
    def setUp(self):
        self.context = yaml.safe_load((ROOT / "cluster.yaml.example").read_text())
        self.tasks = yaml.safe_load((ROLE / "tasks/main.yaml").read_text())

    def render(self, config=None):
        self.context["proxy"] = {"acme_email": "test@example.com", **(config or {})}
        env = NativeEnvironment(undefined=StrictUndefined)
        env.filters.update(plugin.FilterModule().filters())
        expression = self.tasks[0]["ansible.builtin.set_fact"]["traefik_additional_tls_domains"]
        self.context["traefik_additional_tls_domains"] = env.from_string(expression).render(self.context)
        return self.template("traefik.yml.j2")

    def template(self, name):
        env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
        return yaml.safe_load(env.from_string((ROLE / "templates" / name).read_text()).render(self.context))

    def test_default_unchanged(self):
        result = self.render()
        self.assertEqual(result, self.render({"additional_tls_domains": []}))
        self.assertEqual(result["entryPoints"]["websecure"]["http"]["tls"], {
            "certResolver": "cf", "domains": [{"main": self.context["network"]["domain"],
                "sans": ["*." + self.context["network"]["domain"]]}]})

    def test_additive_wildcard_literal_and_removal(self):
        before = self.render()
        after = self.render({"additional_tls_domains": ["*.int.example.net", "app.example.org"]})
        domains = after["entryPoints"]["websecure"]["http"]["tls"]["domains"]
        self.assertEqual(domains[1:], [{"main": "*.int.example.net"}, {"main": "app.example.org"}])
        del domains[1:]
        self.assertEqual(after, before)
        self.assertEqual(self.render(), before)

    def test_invalid_input_fails_before_render(self):
        for value in (None, False, "*.example.net", {}, [None], [12],
                      ["*.example.net", "*.EXAMPLE.NET"], ["example.net\n"],
                      ["https://example.net"], ["example.net:443"], ["example.net/path"],
                      ["*.*.example.net"], ["bad.*.example.net"], ["example"],
                      ["example.net."], ["bad..example.net"], ["-bad.example.net"],
                      ["a" * 64 + ".example.net"], [".".join(["a" * 63] * 5)],
                      ["192.0.2.10"], ["*.192.0.2.10"], ["[2001:db8::1]"],
                      ['evil.example.net"'], ["a.example.net\x00"]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.render({"additional_tls_domains": value})

    def test_normalizes_case(self):
        self.assertEqual(plugin.homelab_tls_domains(["*.INT.Example.NET"]), ["*.int.example.net"])

    def test_scoped_validation_precedes_changes(self):
        selected = [t for t in self.tasks if "service-certificates" in t.get("tags", [])]
        self.assertEqual(len(selected), 2)
        self.assertIs(selected[0], self.tasks[0])
        self.assertIn("ansible.builtin.set_fact", selected[0])
        self.assertEqual(selected[1]["ansible.builtin.template"]["src"], "traefik.yml.j2")
        self.assertEqual(selected[1]["notify"], "Restart traefik")

    def test_existing_alias_keeps_backend_and_restrictions(self):
        service = next(s for s in self.context["services"] if s["name"] == "agh")
        before = self.template("dynamic.yml.j2")
        service["proxy"]["hostnames"] = ["dns.int.example.net"]
        after = self.template("dynamic.yml.j2")
        rule = after["http"]["routers"]["agh"]["rule"]
        self.assertIn("Host(`dns.int.example.net`)", rule)
        self.assertIn("Host(`agh-proxy." + self.context["network"]["domain"] + "`)", rule)
        after["http"]["routers"]["agh"]["rule"] = before["http"]["routers"]["agh"]["rule"]
        self.assertEqual(after, before)

    def test_example_opt_in_only(self):
        self.assertEqual(self.context["proxy"]["additional_tls_domains"], [])


if __name__ == "__main__":
    unittest.main()
