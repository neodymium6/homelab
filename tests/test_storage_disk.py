"""Check the online growth and mounted-device preservation guards."""
from pathlib import Path
import unittest

from jinja2.nativetypes import NativeEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[1]


class StorageDiskTests(unittest.TestCase):
    def test_resize_is_nonforcing_and_guarded(self):
        tasks = yaml.safe_load((ROOT / "bastion/ansible/roles/storage_disk/tasks/main.yaml").read_text())
        filesystem = next(t["community.general.filesystem"] for t in tasks if "community.general.filesystem" in t)
        for task in tasks:
            if task.get("register") in ("storage_disk_lsblk", "storage_disk_mount", "storage_disk_uuid"):
                self.assertIs(task["check_mode"], False)
        self.assertTrue(filesystem["resizefs"])
        self.assertFalse(filesystem["force"])
        guard = next(t for t in tasks if t["name"].startswith("Reject partitions"))
        context = dict(storage_disk_device_path="/dev/sdb",
                       storage_disk_candidates=[dict(path="/dev/sdb", fstype="ext4")],
                       storage_disk_mount=dict(rc=0, stdout="/dev/sdb ext4"))
        env = NativeEnvironment()

        def valid():
            return all(env.from_string("{{ " + expr + " }}").render(context)
                       for expr in guard["ansible.builtin.assert"]["that"])

        self.assertTrue(valid())
        context["storage_disk_mount"]["stdout"] = "/dev/sdc ext4"
        self.assertFalse(valid())
        context["storage_disk_mount"] = dict(rc=1, stdout="")
        self.assertTrue(valid())
        context["storage_disk_candidates"][0]["fstype"] = "xfs"
        self.assertFalse(valid())
        context["storage_disk_candidates"][0]["fstype"] = None
        context["storage_disk_candidates"][0]["children"] = [dict(path="/dev/sdb1")]
        self.assertFalse(valid())


if __name__ == "__main__":
    unittest.main()
