# Jellyfin Role

Deploys Jellyfin on app hosts with Docker Compose.

## Storage

Media libraries are defined under `storage.jellyfin.libraries` in `cluster.yaml`.
The role mounts each library read-only into `/media/<name>` inside the container.

```yaml
storage:
  jellyfin:
    libraries:
      - name: "movies"
        path: "/mnt/storage/share/jellyfin/movies"
```

The storage host directories are created by the `storage_jellyfin_layout` role.

## Service

```yaml
services:
  - name: "jellyfin"
    target_vm: "app-01"
    proxy:
      enable: true
      scheme: "http"
      port: 8096
```
