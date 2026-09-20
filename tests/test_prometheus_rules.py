"""Keep filesystem capacity alerts local without hiding host failures."""
from pathlib import Path
import re
import unittest

from jinja2 import Environment, StrictUndefined
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "bastion/ansible/roles/prometheus"


class PrometheusRuleTests(unittest.TestCase):
    def rules(self, test_alert=False):
        env = Environment(undefined=StrictUndefined)
        env.filters["bool"] = bool
        rendered = env.from_string(
            (ROLE / "templates/baseline_alerts.yml.j2").read_text()
        ).render(prometheus_enable_always_notify_test_alert=test_alert)
        return [r for g in yaml.safe_load(rendered)["groups"] for r in g["rules"]]

    def test_capacity_alerts_exclude_shared_filesystems(self):
        rules = [r for r in self.rules() if r["alert"] in {
            "HostDiskSpaceLow", "HostDiskInodeLow", "HostDiskWillFillSoon"
        }]
        self.assertEqual(len(rules), 5)
        for rule in rules:
            selectors = re.findall(r'fstype!~"([^"]+)"', rule["expr"])
            self.assertEqual(len(selectors), 1 if rule["alert"] == "HostDiskWillFillSoon" else 2)
            for pattern in selectors:
                for fs in ("nfs", "nfs4", "cifs", "smb3", "tmpfs", "overlay", "squashfs"):
                    self.assertIsNotNone(re.fullmatch(pattern, fs))
                for fs in ("ext4", "xfs", "zfs", "btrfs", "vfat"):
                    self.assertIsNone(re.fullmatch(pattern, fs))

    def test_host_availability_alerts_are_retained(self):
        rules = {r["alert"]: r for r in self.rules()}
        self.assertEqual(rules["InstanceDown"]["expr"], 'up{job=~"node|node_exporter"} == 0')
        self.assertEqual(rules["ScrapeErrors"]["expr"], "up == 0")
        self.assertNotIn("AlwaysNotifyTest", rules)
        self.assertIn("AlwaysNotifyTest", {r["alert"] for r in self.rules(True)})

    def test_scoped_rule_update_reloads_without_restart(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yaml").read_text())
        task = next(t for t in tasks if t["name"] == "Deploy Prometheus baseline alert rules")
        self.assertIn("prometheus-rules", task["tags"])
        self.assertEqual(task["notify"], "Reload prometheus")
        handlers = yaml.safe_load((ROLE / "handlers/main.yaml").read_text())
        handler = next(h for h in handlers if h["name"] == "Reload prometheus")
        argv = handler["ansible.builtin.command"]["argv"]
        self.assertIn("SIGHUP", argv)
        self.assertNotIn("restart", argv)


if __name__ == "__main__":
    unittest.main()
