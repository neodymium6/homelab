# Personal Site Role

Deploys a personal-site container image and keeps it updated with a systemd timer.

## Purpose

- Create `/opt/stacks/personal-site`
- Run container via Docker Compose
- Periodically run `docker compose pull` and `docker compose up -d --remove-orphans`
- Optionally allow only proxy host access with UFW

## Defaults

- `personal_site_image`: `ghcr.io/neodymium6/profile.neodymium6.net:latest`
- `personal_site_port`: `8080`
- `personal_site_dir`: `/opt/stacks/personal-site`
- `personal_site_compose_path`: `/opt/stacks/personal-site/docker-compose.yml`
- `personal_site_update_enable`: `true`
- `personal_site_update_on_boot_sec`: `2m`
- `personal_site_update_unit_active_sec`: `1h`
- `personal_site_update_cleanup_enable`: `false`
- `personal_site_update_cleanup_until`: `168h`

## Firewall Behavior

- If `personal_site_enable_ufw: true` and `personal_site_allow_from_proxy_only: true`,
  only `personal_site_proxy_ip` is allowed to access `personal_site_port`.
