# Navidrome lifecycle

The role manages Compose through `navidrome.service`. systemd waits for the
filesystem containing `navidrome_library_dir` before starting the container,
so an NFS-backed library cannot be replaced by its empty local mountpoint at
boot. The mount must be declared (for example by `storage_nfs_client` in fstab).

Compose runs attached, with `restart: "no"`; systemd restarts a terminated
application after ten seconds. Do not enable Docker's own restart policy:
it would bypass mount ordering when the Docker daemon starts. Docker restart
also restarts this service. Other containers do not depend on this unit.

Use `systemctl restart navidrome` or reapply this role for lifecycle changes.
The unit uses the already provisioned image without pulling at boot. It stops
only Navidrome, without removing its container, database or music files.
If the required mount fails to start, resolve the storage problem and start
`navidrome.service` again. This is boot ordering, not NFS outage recovery.

For a library check, verify that `/music` inside the container is the expected
filesystem and check scan completion; the HTTP healthcheck alone does not
prove that the music files are accessible.
