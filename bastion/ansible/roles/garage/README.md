# Garage

Installs Garage as a native systemd service on the storage VM. The role starts
Garage in single-node mode, then reconciles all declared buckets, access keys,
and exact read/write/owner permissions. Object data and metadata are stored
below the dedicated storage mount.

Garage is exposed to clients through the existing internal Traefik endpoint:

```text
S3 client -> https://garage-proxy.<network.domain> -> http://storage-01:3900
```

Use path-style S3 URLs, for example
`https://garage-proxy.internal.example.com/backup/restic`. No Cloudflare public
hostname is configured for this service.

## Configuration

Add the service, buckets, clients, and storage path to `cluster.yaml` as shown
in `cluster.yaml.example`. Generate credentials locally:

```bash
printf 'GK%s\n' "$(openssl rand -hex 16)"
openssl rand -hex 32
```

Use the first output for a client's `access_key_id`. Use the second output for
its `secret_access_key`, and generate separate values for `rpc_secret`,
`admin_token`, and `metrics_token`. Keep the real values only in the ignored
`cluster.yaml`; never add them to `cluster.yaml.example` or commit them.

Each client references its secret entry without embedding credentials in the
service declaration:

```yaml
services:
  - name: "garage"
    buckets:
      - name: "backup"
        clients:
          - name: "backup-admin"
            credentials_ref: "backup_admin"
            permissions:
              read: true
              write: true
              owner: true

secrets:
  garage:
    clients:
      backup_admin:
        access_key_id: "GK_REPLACE_ME"
        secret_access_key: "REPLACE_WITH_AT_LEAST_32_CHARACTERS"
```

The legacy single `bucket`, top-level `access_key_id`, and top-level
`secret_access_key` fields are rejected instead of being used as fallbacks.

Deployment is part of the existing `make all` and `make debug` paths through
`bastion/ansible/site_internal.yaml`. There is no separate Garage Make target.

## Restic Example

```bash
export RESTIC_REPOSITORY="s3:https://garage-proxy.internal.example.com/backup/restic"
export AWS_DEFAULT_REGION="garage"
export AWS_ACCESS_KEY_ID="<secrets.garage.clients.backup_admin.access_key_id>"
export AWS_SECRET_ACCESS_KEY="<secrets.garage.clients.backup_admin.secret_access_key>"
restic init
```

The single-node setup has no Garage-level redundancy. It is suitable as a
convenient backup target, but not as the only copy of important data.

`make clean` destroys the Terraform-managed storage VM and its attached data
disk. That includes all Garage metadata, objects, and snapshots under
`/mnt/storage/garage`.
