"""Offline argument-rendering checks; no host or Tailnet changes."""
from pathlib import Path
import unittest

from jinja2.nativetypes import NativeEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "bastion/ansible/roles/tailscale"


class TailscaleTests(unittest.TestCase):
    def setUp(self):
        self.tasks = yaml.safe_load((ROLE / "tasks/main.yaml").read_text())
        self.defaults = yaml.safe_load((ROLE / "defaults/main.yaml").read_text())
        self.env = NativeEnvironment()
        self.env.filters["bool"] = lambda value: str(value).lower() in ("true", "1", "yes")
        self.context = dict(self.defaults, tailscale_auth_key="TEST_ONLY",
                            tailscale_hostname="router-test", tailscale_backend_state="Running",
                            tailscale_advertise_routes=["192.0.2.0/24"],
                            tailscale_advertise_tags=["tag:router-test"],
                            tailscale_enable_ip_forward=True)

    def arguments(self):
        task = next(t for t in self.tasks if t["name"] == "Build tailscale up arguments")
        self.assertTrue(task["no_log"])
        return self.env.from_string(task["ansible.builtin.set_fact"]["tailscale_up_args"]).render(self.context)

    def test_default_is_explicitly_disabled(self):
        self.assertIs(self.defaults["tailscale_advertise_exit_node"], False)
        self.assertIn("--advertise-exit-node=false", self.arguments())

    def test_exit_toggle_preserves_every_other_argument(self):
        disabled = self.arguments()
        self.context["tailscale_advertise_exit_node"] = True
        enabled = self.arguments()
        expected = ["--advertise-exit-node=true" if a == "--advertise-exit-node=false" else a
                    for a in disabled]
        self.assertEqual(enabled, expected)
        self.assertIn("--advertise-routes=192.0.2.0/24", enabled)
        self.assertIn("--accept-routes=false", enabled)
        self.context["tailscale_advertise_exit_node"] = False
        self.assertEqual(self.arguments(), disabled)

    def test_forwarding_required_only_when_exit_enabled(self):
        task = next(t for t in self.tasks if t["name"] == "Require IP forwarding when advertising an exit node")
        expr = task["ansible.builtin.assert"]["that"][0]
        for exit_enabled, forwarding, valid in [(True, False, False), (True, True, True),
                                                 (False, False, True), (False, True, True)]:
            self.context.update(tailscale_advertise_exit_node=exit_enabled,
                                tailscale_enable_ip_forward=forwarding)
            self.assertEqual(self.env.from_string("{{ " + expr + " }}").render(self.context), valid)

    def test_bastion_play_wires_opt_in_and_has_scoped_tag(self):
        plays = yaml.safe_load((ROOT / "bastion/ansible/site_bastion.yaml").read_text())
        play = next(p for p in plays if p.get("name") == "Join bastion to Tailscale")
        self.assertIn("tailscale", play["tags"])
        expr = play["roles"][0]["vars"]["tailscale_advertise_exit_node"]
        self.assertIs(self.env.from_string(expr).render(ts_node={}), False)
        self.assertIs(self.env.from_string(expr).render(ts_node={"advertise_exit_node": True}), True)


if __name__ == "__main__":
    unittest.main()
