# Personal Site Role

Deploys a personal-site container image and keeps it updated with a systemd timer.

## Purpose

- Create `/opt/stacks/personal-site`
- Run one container per backend port via Docker Compose
- Periodically run rolling updates (`pull` then one backend at a time with readiness checks)
- Optionally allow only proxy host access with UFW

## Defaults

- `personal_site_image`: `ghcr.io/neodymium6/profile.neodymium6.net:latest`
- `personal_site_backend_ports`: `[8080, 8081]`
- `personal_site_dir`: `/opt/stacks/personal-site`
- `personal_site_compose_path`: `/opt/stacks/personal-site/docker-compose.yml`
- `personal_site_update_enable`: `true`
- `personal_site_update_on_boot_sec`: `2m`
- `personal_site_update_unit_active_sec`: `1h`
- `personal_site_update_cleanup_enable`: `false`
- `personal_site_update_cleanup_until`: `168h`
- `personal_site_update_timeout_start_sec`: `10min`
- `personal_site_ready_path`: `/`
- `personal_site_ready_retries`: `300`
- `personal_site_ready_sleep_seconds`: `0.2`

## Firewall Behavior

- If `personal_site_enable_ufw: true` and `personal_site_allow_from_proxy_only: true`,
  only `personal_site_proxy_ip` is allowed to access all `personal_site_backend_ports`.
