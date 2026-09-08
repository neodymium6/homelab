"""Offline Samba schema and template regressions."""
import importlib.util
from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
from jinja2.nativetypes import NativeEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "bastion/ansible/roles/storage_samba"
spec = importlib.util.spec_from_file_location("samba_filter", ROOT / "bastion/ansible/filter_plugins/storage_samba.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class SambaTests(unittest.TestCase):
    def setUp(self):
        self.users = {"operator": {"unix_account": "existing"}, "writer": {}}
        self.shares = {"files": {"path": "/mnt/storage/files", "valid_users": ["writer"]}}

    def model(self):
        return plugin.storage_samba_model(self.users, self.shares, "operator")

    def test_defaults(self):
        config = self.model()["shares"]["files"]
        self.assertEqual(config["force_user"], "operator")
        self.assertEqual(config["encryption"], "required")
        self.assertFalse(config["browseable"])
        self.assertFalse(config["follow_symlinks"])
        self.assertEqual(config["directory_mask"], "0775")

    def test_reject_invalid_share_settings(self):
        for options in ({"path": "/"}, {"path": "/mnt/../etc"}, {"path": "/tmp/\n[global]"},
                        {"path": "/mnt/%u"}, {"valid_users": []}, {"valid_users": ["root"]},
                        {"read_only": "false"}, {"create_mask": 664},
                        {"force_user": "operator\nguest ok = yes"}, {"encryption": "invalid"},
                        {"typo": True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                plugin.storage_samba_model(self.users, {"files": self.shares["files"] | options}, "operator")

    def test_user_and_share_names(self):
        for user in ("root", "bad\nname", "user;bad"):
            with self.subTest(user=user), self.assertRaises(ValueError):
                plugin.storage_samba_model({user: {}}, {}, "operator")
        for share in ("global", "homes", "printers", "bad]name"):
            with self.subTest(share=share), self.assertRaises(ValueError):
                plugin.storage_samba_model(self.users, {share: self.shares["files"]}, "operator")

    def test_render_readonly_and_multiple_shares(self):
        self.shares["readonly"] = {"path": "/mnt/storage/media", "valid_users": ["operator"], "read_only": True}
        template = Environment(undefined=StrictUndefined).from_string((ROLE / "templates/smb.conf.j2").read_text())
        result = template.render(storage_samba_model=self.model(), storage_samba_users=self.users,
                                 storage_samba_workgroup="WORKGROUP")
        self.assertIn("[files]", result)
        self.assertIn("[readonly]", result)
        self.assertIn("read only = yes", result)
        self.assertIn("smb encrypt = required", result)
        self.assertNotIn("password", result)

    def test_legacy_adapter_preserves_effective_policy(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yaml").read_text())
        expression = next(t["ansible.builtin.set_fact"]["storage_samba_model"] for t in tasks
                          if "storage_samba_model" in t.get("ansible.builtin.set_fact", {}))
        context = yaml.safe_load((ROLE / "defaults/main.yaml").read_text())
        context.update(storage_samba_user="operator", storage_samba_force_user="operator")
        env = NativeEnvironment(undefined=StrictUndefined)
        env.filters["storage_samba_model"] = plugin.storage_samba_model
        model = env.from_string(expression).render(context)
        share = model["shares"]["storage"]
        self.assertTrue(share["browseable"])
        self.assertTrue(share["follow_symlinks"])
        self.assertTrue(share["inherit_permissions"])
        self.assertEqual(share["encryption"], "default")
        self.assertEqual(share["directory_mask"], "2775")
        result = Environment().from_string((ROLE / "templates/smb.conf.j2").read_text()).render(
            **(context | {"storage_samba_model": model}))
        self.assertNotIn("force user", result)
        self.assertNotIn("smb encrypt", result)

    def test_example_and_safety_guards(self):
        config = yaml.safe_load((ROOT / "cluster.yaml.example").read_text())
        samba = config["storage"]["samba"]
        plugin.storage_samba_model(samba["users"], samba["shares"], config["login_user"])
        tasks = yaml.safe_load((ROLE / "tasks/main.yaml").read_text())
        render = next(t for t in tasks if "ansible.builtin.template" in t)
        probe = next(t for t in tasks if t.get("ansible.builtin.command") == "pdbedit -L")
        self.assertIs(probe["check_mode"], False)
        self.assertIn("testparm", render["ansible.builtin.template"]["validate"])
        handlers = (ROLE / "handlers/main.yaml").read_text()
        self.assertNotIn("restarted", handlers)
        self.assertIn("reload-config", handlers)
        self.assertNotIn("state: absent", (ROLE / "tasks/main.yaml").read_text())


if __name__ == "__main__":
    unittest.main()
