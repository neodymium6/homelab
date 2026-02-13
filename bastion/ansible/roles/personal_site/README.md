# Personal Site Role

Deploys a simple Nginx container for a public-facing personal site.

## Purpose

- Create `/opt/stacks/personal-site`
- Render static `index.html`
- Run Nginx via Docker Compose
- Optionally allow only proxy host access with UFW

## Defaults

- `personal_site_image`: `nginx:stable-alpine`
- `personal_site_port`: `8080`
- `personal_site_dir`: `/opt/stacks/personal-site`
- `personal_site_compose_path`: `/opt/stacks/personal-site/docker-compose.yml`

## Firewall Behavior

- If `personal_site_enable_ufw: true` and `personal_site_allow_from_proxy_only: true`,
  only `personal_site_proxy_ip` is allowed to access `personal_site_port`.
