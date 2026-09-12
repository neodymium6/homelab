#!/usr/bin/python3
"""One exact zvol, one snapshot per local day, bounded owned-only retention."""
import argparse
from datetime import datetime
import fcntl
import json
import re
import subprocess
from zoneinfo import ZoneInfo

PROPERTY = "homelab:snapshot-policy"
POLICY = "daily-v1"
PREFIX = "homelab-daily-"


def zfs(*args):
    return subprocess.run(["/usr/sbin/zfs", *args], check=True, text=True,
                          capture_output=True, timeout=90).stdout.strip()


def validate(config):
    dataset = config["dataset"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*(/[A-Za-z0-9][A-Za-z0-9_.:-]*)+", dataset):
        raise ValueError("expected an exact child dataset")
    if not re.fullmatch(r"[0-9]+", config["guid"]):
        raise ValueError("expected a pinned dataset GUID")
    if type(config["keep"]) is not int or not 1 <= config["keep"] <= 366:
        raise ValueError("invalid retention")
    ZoneInfo(config["timezone"])


def verify_target(config):
    actual = dict(line.split("\t", 1) for line in zfs(
        "get", "-Hp", "-o", "property,value", "type,guid", config["dataset"]).splitlines())
    if actual != {"type": "volume", "guid": config["guid"]}:
        raise ValueError("target is not the pinned zvol")


def owned(config):
    result = []
    for line in zfs("list", "-Hp", "-r", "-t", "snapshot", "-o",
                    f"name,creation,{PROPERTY}", config["dataset"]).splitlines():
        name, created, marker = line.split("\t")
        if marker != POLICY or not re.fullmatch(
                re.escape(config["dataset"] + "@" + PREFIX) + r"[0-9]{8}", name):
            continue
        datetime.strptime(name.rsplit("-", 1)[1], "%Y%m%d")
        # Inherited properties do not confer ownership.
        prop = zfs("get", "-H", "-o", "value,source", PROPERTY, name)
        if prop == POLICY + "\tlocal":
            result.append((int(created), name))
    return sorted(result)


def run(config, dry_run=False, now=None):
    validate(config)
    verify_target(config)
    now = now or datetime.now(ZoneInfo(config["timezone"]))
    name = config["dataset"] + "@" + PREFIX + now.strftime("%Y%m%d")
    snapshots = owned(config)
    if any(created > now.timestamp() + 300 for created, _ in snapshots):
        raise ValueError("future snapshot: check clock before retention")
    if name not in [s[1] for s in snapshots]:
        print("create " + name, flush=True)
        if not dry_run:
            # A pre-existing unowned name fails creation, preventing any pruning.
            zfs("snapshot", "-o", PROPERTY + "=" + POLICY, name)
        snapshots.append((int(now.timestamp()), name))
    else:
        print("already present " + name, flush=True)
    for _, old in sorted(snapshots)[:-config["keep"]]:
        if dry_run:
            print("would prune " + old, flush=True)
            continue
        verify_target(config)
        if old not in [s[1] for s in owned(config)]:
            raise ValueError("snapshot ownership changed")
        print("prune " + old, flush=True)
        # No recursive, forced or deferred deletion. Holds/clones cause failure.
        zfs("destroy", old)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with open("/etc/homelab-zfs-snapshots.json", encoding="utf-8") as source:
        config = json.load(source)
    with open("/run/lock/homelab-zfs-snapshots.lock", "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(config, args.dry_run)


if __name__ == "__main__":
    main()
