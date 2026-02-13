# Cloudflare Tunnel Role

Deploys `cloudflared` on proxy hosts using Docker Compose.

## Purpose

- Connect Cloudflare Tunnel to the proxy host
- Forward traffic to Traefik tunnel entrypoint on `127.0.0.1:8080`
- Keep selective exposure controlled by Cloudflare Public Hostname settings

## Required cluster.yaml settings

```yaml
proxy:
  cloudflare_tunnel_token: "CF_TUNNEL_TOKEN_HERE"
```

## Defaults

- `cloudflare_tunnel_image`: `cloudflare/cloudflared:latest`
- `cloudflare_tunnel_dir`: `/opt/stacks/cloudflare-tunnel`
- `cloudflare_tunnel_compose_path`: `/opt/stacks/cloudflare-tunnel/docker-compose.yml`

## Behavior

1. Validate `proxy.cloudflare_tunnel_token`
2. Create compose directory
3. Render compose file
4. Run `docker compose up -d`
