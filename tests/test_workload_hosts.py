"""Offline coverage for generic Docker VMs and existing inventory roles."""
from pathlib import Path
import unittest

from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[1]


class WorkloadHostTests(unittest.TestCase):
    def setUp(self):
        self.inventory = yaml.safe_load(
            (ROOT / "bastion/ansible/plays/inventory_from_cluster.yaml").read_text()
        )[0]
        self.plays = yaml.safe_load(
            (ROOT / "bastion/ansible/site_internal.yaml").read_text()
        )
        self.env = NativeEnvironment(undefined=StrictUndefined)

    def inventory_for(self, role):
        context = {
            "item": {"key": "test-vm", "value": {"role": role, "vmid": 203}},
            "cluster": {"login_user": "test-user", "network": {"base_prefix": "192.0.2"}},
        }
        host, groups = {}, set()
        for task in self.inventory["tasks"]:
            if "ansible.builtin.add_host" not in task:
                continue
            selected = self.env.from_string("{{ " + task["when"] + " }}").render(context)
            if not selected:
                continue
            values = {
                key: self.env.from_string(value).render(context)
                for key, value in task["ansible.builtin.add_host"].items()
            }
            groups.update(values.pop("groups").split(","))
            host.update(values)
        return host, groups

    def test_workload_receives_internal_access_without_app_membership(self):
        host, groups = self.inventory_for("workload")
        self.assertEqual(groups, {"internal", "cluster", "workload"})
        self.assertEqual(host["ansible_host"], "192.0.2.203")
        self.assertEqual(host["ansible_user"], "test-user")
        self.assertEqual(host["ansible_ssh_private_key_file"], "/home/test-user/.ssh/id_ed25519_internal")
        self.assertEqual(host["ansible_python_interpreter"], "/usr/bin/python3")
        self.assertNotIn("ansible_connection", host)

    def test_existing_roles_keep_their_groups(self):
        expected = {
            "bastion": {"bastion", "cluster"},
            "proxy": {"proxy", "cluster"},
            **{role: {"internal", "cluster", role}
               for role in ("app", "audiomuse", "dns", "storage", "rip")},
        }
        for role, groups in expected.items():
            with self.subTest(role=role):
                self.assertEqual(self.inventory_for(role)[1], groups)
        self.assertEqual(self.inventory_for("unknown"), ({}, set()))

    def test_only_docker_play_explicitly_adds_workload_group(self):
        plays = [p for p in self.plays if "workload" in p.get("hosts", "")]
        self.assertEqual(len(plays), 1)
        play = plays[0]
        self.assertEqual(play["hosts"], "app:workload")
        self.assertEqual(play["roles"], [{
            "role": "docker", "vars": {"docker_users": ["{{ login_user }}"]},
        }])
        self.assertTrue(play["become"])
        for name in ("Deploy Prometheus on app hosts", "Deploy Grafana on app hosts"):
            self.assertEqual(next(p for p in self.plays if p.get("name") == name)["hosts"], "app")

    def test_common_setup_remains_available_and_nfs_is_opt_in(self):
        for name, pattern in (
            ("Harden SSH on internal hosts", "internal"),
            ("Install node_exporter on all VMs", "cluster"),
            ("Point internal hosts systemd-resolved to dns-01", "cluster:!dns"),
        ):
            self.assertEqual(next(p for p in self.plays if p.get("name") == name)["hosts"], pattern)
        play = next(p for p in self.plays if p.get("name") == "Mount shared NFS storage on whitelisted hosts")
        role = next(r for r in play["roles"] if r["role"] == "storage_nfs_client")
        self.assertIn("inventory_hostname in storage_nfs_client_names", role["when"])

    def test_example_is_generic_and_does_not_deploy_services(self):
        example = yaml.safe_load((ROOT / "cluster.yaml.example").read_text())
        workloads = {name for name, vm in example["vms"].items() if vm["role"] == "workload"}
        self.assertEqual(workloads, {"workload-01"})
        ids = [vm["vmid"] for vm in example["vms"].values()]
        self.assertEqual(len(ids), len(set(ids)))
        for service in example["services"]:
            self.assertNotIn(service.get("target_vm"), workloads)
        self.assertTrue(workloads.isdisjoint(example["storage"]["nfs"]["clients"]))


if __name__ == "__main__":
    unittest.main()
