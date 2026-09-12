"""Exercise exact-target snapshot creation and non-recursive owned retention."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "snapshots", ROOT / "local/ansible/roles/zfs_snapshots/files/snapshots.py")
snapshots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshots)
DATASET = "tank/test/vm-104-disk-0"
CONFIG = dict(dataset=DATASET, guid="1234", keep=7, timezone="UTC")
NOW = datetime(2026, 1, 10, 6, 30, tzinfo=timezone.utc)


class FakeZFS:
    def __init__(self):
        self.rows = {}
        self.calls = []
        self.guid = "1234"
        self.kind = "volume"
        self.fail_create = False
        self.fail_delete = False
        for day in range(1, 10):
            self.rows[f"{DATASET}@homelab-daily-202601{day:02}"] = (
                int(datetime(2026, 1, day, tzinfo=timezone.utc).timestamp()), "daily-v1", "local")

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == "get" and "type,guid" in args:
            return f"type\t{self.kind}\nguid\t{self.guid}"
        if args[0] == "get":
            row = self.rows[args[-1]]
            return row[1] + "\t" + row[2]
        if args[0] == "list":
            return "\n".join(f"{name}\t{row[0]}\t{row[1]}" for name, row in self.rows.items())
        if args[0] == "snapshot":
            if self.fail_create or args[-1] in self.rows:
                raise subprocess.CalledProcessError(1, args)
            self.rows[args[-1]] = (int(NOW.timestamp()), "daily-v1", "local")
        elif args[0] == "destroy":
            if self.fail_delete:
                raise subprocess.CalledProcessError(1, args)
            if len(args) != 2 or "@" not in args[1]:
                raise AssertionError("unsafe deletion")
            del self.rows[args[1]]
        else:
            raise AssertionError(args)
        return ""


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeZFS()

    def run_manager(self, dry=False, config=None):
        with patch.object(snapshots, "zfs", self.fake), patch("builtins.print"):
            snapshots.run(config or CONFIG, dry, NOW)

    def test_keep_seven_then_same_day_idempotent(self):
        self.run_manager()
        self.assertEqual(len(self.fake.rows), 7)
        self.assertIn(DATASET + "@homelab-daily-20260110", self.fake.rows)
        self.fake.calls.clear()
        self.run_manager()
        self.assertFalse(any(c[0] in ("snapshot", "destroy") for c in self.fake.calls))

    def test_foreign_names_children_and_inherited_marker_untouched(self):
        foreign = {
            DATASET + "@migration": (1, "daily-v1", "local"),
            DATASET + "/child@homelab-daily-20250101": (1, "daily-v1", "local"),
            DATASET + "@homelab-daily-20250102": (1, "-", "-"),
            DATASET + "@homelab-daily-20250103": (1, "daily-v1", "inherited from tank"),
        }
        self.fake.rows.update(foreign)
        self.run_manager()
        for name, row in foreign.items():
            self.assertEqual(self.fake.rows[name], row)

    def test_no_prune_after_failed_creation(self):
        self.fake.fail_create = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_manager()
        self.assertFalse(any(c[0] == "destroy" for c in self.fake.calls))

    def test_unowned_same_day_collision_fails_closed(self):
        self.fake.rows[DATASET + "@homelab-daily-20260110"] = (1, "-", "-")
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_manager()
        self.assertFalse(any(c[0] == "destroy" for c in self.fake.calls))

    def test_holds_or_clones_are_not_forced(self):
        self.fake.fail_delete = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_manager()
        destroys = [c for c in self.fake.calls if c[0] == "destroy"]
        self.assertEqual(len(destroys), 1)
        self.assertEqual(len(destroys[0]), 2)

    def test_dry_run_is_read_only(self):
        before = self.fake.rows.copy()
        self.run_manager(True)
        self.assertEqual(before, self.fake.rows)
        self.assertFalse(any(c[0] in ("snapshot", "destroy") for c in self.fake.calls))

    def test_replaced_volume_or_filesystem_rejected(self):
        for attr, value in [("guid", "9999"), ("kind", "filesystem")]:
            self.fake = FakeZFS()
            setattr(self.fake, attr, value)
            with self.assertRaises(ValueError):
                self.run_manager()
            self.assertFalse(any(c[0] in ("snapshot", "destroy") for c in self.fake.calls))

    def test_invalid_inputs(self):
        for dataset in ("tank", "tank/data@a", "tank/data,other", "-r", "tank/../x", "tank/data\nx"):
            with self.assertRaises(ValueError):
                snapshots.validate(dict(CONFIG, dataset=dataset))
        for keep in (0, -1, 1000, True, "7"):
            with self.assertRaises(ValueError):
                snapshots.validate(dict(CONFIG, keep=keep))

    def test_clock_regression_rejected(self):
        self.fake.rows[DATASET + "@homelab-daily-20260111"] = (
            int(NOW.timestamp()) + 86400, "daily-v1", "local")
        with self.assertRaises(ValueError):
            self.run_manager()
        self.assertFalse(any(c[0] in ("snapshot", "destroy") for c in self.fake.calls))

    def test_empty_history(self):
        self.fake.rows.clear()
        self.run_manager()
        self.assertEqual(len(self.fake.rows), 1)


if __name__ == "__main__":
    unittest.main()
