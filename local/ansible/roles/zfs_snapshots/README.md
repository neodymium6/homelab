# Data-volume recovery snapshots

Opt-in host-side ZFS snapshots. Configure `proxmox.ssh_host` (an existing SSH
alias is supported) and `proxmox.zfs_snapshots` in ignored `cluster.yaml`.
Pin one existing zvol by its exact dataset name and numeric ZFS `guid`.
The role does not create storage or discover/select disks automatically.

Run from the operator checkout:

```sh
cd local/ansible
ansible-playbook -i localhost, site_proxmox.yaml --check
ansible-playbook -i localhost, site_proxmox.yaml
```

The playbook is also imported by `site_local.yaml`. No guest configuration,
freeze, stop, or reboot is performed. Default schedule: 06:30 in the top-level
`timezone` (UTC if omitted), persistent catch-up after host downtime. Defaults
retain the newest seven successful daily generations, not seven executions;
missed days are not synthesized. Re-running on the same local day is idempotent.
Ansible variables `zfs_snapshot_keep` and `zfs_snapshot_time` override defaults.

Only names `homelab-daily-YYYYMMDD` directly on the pinned zvol with the **local**
property `homelab:snapshot-policy=daily-v1` are eligible for automatic deletion.
A new snapshot must succeed before pruning. Foreign snapshots, descendants,
holds and clones are not forcibly removed. Never manually reuse the managed
namespace/marker for snapshots intended to be permanent.

Check with `systemctl status homelab-zfs-snapshots.timer` and
`journalctl -u homelab-zfs-snapshots.service`. Run the installed helper with
`--dry-run` to inspect its plan without changing ZFS. Set `enabled: false` and
reapply to stop future timer runs; this does not delete existing snapshots or
interrupt a currently running service. Keep the configuration block when disabling.

Snapshots cover the entire data volume, not selected shares. A running guest's
ext4 filesystem is crash-consistent, not application-consistent, and guest RAM
buffers are excluded. Continue native application/DB backups. Recovery should
clone a selected snapshot to an explicitly approved separate recovery volume
and recover files through an isolated guest (journal recovery may be required).
Do not roll back the live volume or attach two writable copies with the same
filesystem UUID to the production guest.

Snapshots are not an independent backup: pool loss loses them too. Changed or
deleted blocks consume pool space until retained generations expire. Existing
pool/guest capacity monitoring remains important. Service failures are visible
in systemd; this role does not add a new notification integration.

See [OpenZFS snapshot semantics](https://openzfs.github.io/openzfs-docs/man/v2.2/8/zfs-snapshot.8.html).
