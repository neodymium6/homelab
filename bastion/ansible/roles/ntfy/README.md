# ntfy Role

Deploys a self-hosted `ntfy` server on app hosts via Docker Compose.

## Purpose

- Create `/opt/stacks/ntfy`
- Render `server.yaml` from cluster variables
- Run `binwiederhier/ntfy` as a persistent container
- Optionally restrict backend port access to `proxy-01` with UFW

## Defaults

- `ntfy_image`: `binwiederhier/ntfy:v2.17.0`
- `ntfy_port`: `8079`
- `ntfy_dir`: `/opt/stacks/ntfy`
- `ntfy_compose_path`: `/opt/stacks/ntfy/docker-compose.yaml`
- `ntfy_config_path`: `/opt/stacks/ntfy/server.yaml`
- `ntfy_base_url`: `https://ntfy-proxy.<network.domain>`
- `ntfy_upstream_base_url`: `https://ntfy.sh`
- `ntfy_enable_login`: `true`
- `ntfy_auth_default_access`: `deny-all`
- `ntfy_auth_access`: `[]`
- `ntfy_message_size_limit`: `4K`
- `ntfy_message_delay_limit`: `1h`
- `ntfy_visitor_request_limit_burst`: `30`
- `ntfy_visitor_request_limit_replenish`: `10s`
- `ntfy_visitor_message_daily_limit`: `200`
- `ntfy_visitor_subscription_limit`: `20`
- `ntfy_visitor_subscriber_rate_limiting`: `true`

## Required Secrets

Configure at least one bcrypt user in `cluster.yaml`:

```yaml
secrets:
  ntfy:
    auth_users:
      - "iphone:$2a$10$REPLACE_WITH_BCRYPT_HASH:user"
      - "publisher:$2a$10$REPLACE_WITH_BCRYPT_HASH:user"
    auth_access:
      - "iphone:*:read"
      - "publisher:*:write"
```

Generate a bcrypt hash with:

```bash
docker run --rm binwiederhier/ntfy:v2.17.0 user hash
```
