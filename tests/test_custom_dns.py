"""Offline schema, rendering and scoped DNS apply regressions."""
import importlib.util
from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "bastion/ansible/roles/unbound"
spec = importlib.util.spec_from_file_location(
    "custom_dns", ROOT / "bastion/ansible/filter_plugins/custom_dns.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class CustomDNSTests(unittest.TestCase):
    def model(self, records):
        return plugin.homelab_dns_records(
            {"records": records}, "internal.example.com", {"vm": {"vmid": 10}},
            {"app": {"target_vm": "vm"}, "retired": {"target_vm": "missing"}})

    def record(self, **kwargs):
        return {"name": "reader.internal.example.com", "type": "A", "value": "192.0.2.10"} | kwargs

    def render(self, records):
        ctx = yaml.safe_load((ROLE / "defaults/main.yaml").read_text())
        ctx.update(unbound_zone_name="internal.example.com",
                   unbound_zone_base_prefix="192.0.2", unbound_zone_vms={"vm": {"vmid": 10}},
                   unbound_zone_services={"app": {"target_vm": "vm"}},
                   unbound_upstream_dns=["192.0.2.53"], unbound_validated_records=self.model(records))
        return Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True).from_string(
            (ROLE / "templates/homelab.conf.j2").read_text()).render(ctx)

    def test_absent_empty_and_defaults(self):
        self.assertEqual(plugin.homelab_dns_records({}, "home.arpa", {}, {}), [])
        self.assertEqual(self.model([]), [])
        item = self.model([self.record(name="Reader.Internal.Example.Com.")])[0]
        self.assertEqual(item["name"], "reader.internal.example.com")
        self.assertEqual(item["ttl"], 300)
        self.assertFalse(item["outside_zone"])

    def test_ipv6_and_multiple_addresses(self):
        records = [self.record(), self.record(value="192.0.2.11"),
                   self.record(type="AAAA", value="2001:db8::10", ttl=0)]
        self.assertEqual(len(self.model(records)), 3)
        self.assertIn('IN AAAA 2001:db8::10', self.render(records))

    def test_invalid_schema_and_values(self):
        for config in (None, [], "text", {"record": []}, {"records": None}, {"records": {}}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                plugin.homelab_dns_records(config, "home.arpa", {}, {})
        for patch in ({"name": "reader"}, {"name": "*.example.com"},
                      {"name": 'bad.example.com"\nserver:'}, {"name": "bad..example.com"},
                      {"name": "-bad.example.com"}, {"name": "x" * 64 + ".example.com"},
                      {"name": "a.example.com\x00"}, {"type": "CNAME"},
                      {"type": "TXT"}, {"type": "a"}, {"type": "AAAA"},
                      {"value": "192.0.2.999"}, {"value": "192.0.2.0/24"},
                      {"type": "AAAA", "value": "fe80::1%eth0"}, {"value": 123},
                      {"ttl": True}, {"ttl": "300"}, {"ttl": -1},
                      {"ttl": 2147483648}, {"typo": "value"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.model([self.record(**patch)])
        for item in (None, "text", {}, {"name": "a.example.com", "type": "A"}):
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.model([item])

    def test_generated_names_and_zone_cannot_be_overridden(self):
        for name in ("VM.internal.example.com.", "app.internal.example.com",
                     "internal.example.com", "example.com"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.model([self.record(name=name)])

    def test_duplicates_and_rrset_ttl_mismatch(self):
        for second in (self.record(name="READER.internal.example.com."),
                       self.record(value="192.0.2.11", ttl=900)):
            with self.subTest(second=second), self.assertRaises(ValueError):
                self.model([self.record(), second])

    def test_generated_records_unchanged_and_removal(self):
        before = self.render([])
        records = [self.record(), self.record(name="reader.example.net")]
        after = self.render(records)
        for line in before.splitlines():
            if line.strip():
                self.assertIn(line, after.splitlines())
        self.assertIn('local-zone: "internal.example.com." static', after)
        self.assertNotIn('local-zone: "example.net."', after)
        self.assertIn('local-zone: "reader.example.net." transparent', after)
        self.assertNotIn('reader.', self.render([]))

    def test_one_outside_zone_per_owner(self):
        result = self.render([self.record(name="reader.example.net"),
                              self.record(name="reader.example.net", value="192.0.2.11")])
        self.assertEqual(result.count('local-zone: "reader.example.net."'), 1)

    def test_scoped_apply_validates_before_replace(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yaml").read_text())
        self.assertIn("ansible.builtin.set_fact", tasks[0])
        selected = [t for t in tasks if "service-dns" in t.get("tags", [])]
        self.assertEqual(len(selected), 2)
        self.assertIn("ansible.builtin.set_fact", selected[0])
        template = selected[1]["ansible.builtin.template"]
        self.assertEqual(template["validate"], "/usr/sbin/unbound-checkconf %s")
        self.assertTrue(template["backup"])
        makefile = (ROOT / "bastion/Makefile").read_text()
        for target in ("dns-check", "dns-apply"):
            body = makefile.split(target + ":\n", 1)[1].split("\n\n", 1)[0]
            self.assertIn("--limit 'localhost,dns' --tags service-dns", body)
            self.assertNotIn("$(TERRAFORM)", body)
        self.assertIn("--check --diff", makefile.split("dns-check:\n", 1)[1].split("\n\n", 1)[0])

    def test_example_and_site_wiring(self):
        example = yaml.safe_load((ROOT / "cluster.yaml.example").read_text())
        self.assertEqual(len(self.model(example["dns"]["records"])), 2)
        plays = yaml.safe_load((ROOT / "bastion/ansible/site_internal.yaml").read_text())
        dns = next(p for p in plays if p.get("name") == "Install and configure Unbound on DNS hosts")
        self.assertEqual(dns["vars"]["unbound_custom_dns"], "{{ dns | default({}) }}")
        self.assertEqual(dns["hosts"], "dns")


if __name__ == "__main__":
    unittest.main()
