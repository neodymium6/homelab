# Traefik Reverse Proxy Role

Ansible role for installing and configuring Traefik reverse proxy on VMs with `role: proxy`.

## Overview

This role:
- Installs Docker and Docker Compose
- Deploys Traefik v2.11 as a Docker container
- Generates static and dynamic configuration from `cluster.yaml`
- Configures automatic HTTPS via Let's Encrypt (Cloudflare DNS challenge)
- Sets up service routing with optional authentication and IP filtering

## Requirements

- Debian-based system (tested on Debian 12)
- `cluster.yaml` with `proxy` configuration block
- Cloudflare API token for DNS challenge
- Services defined in `cluster.yaml` with `proxy.enable: true`

## Role Variables

### Defaults (defaults/main.yml)

| Variable | Default | Description |
|----------|---------|-------------|
| `traefik_image` | `traefik:v2.11` | Traefik Docker image |
| `traefik_dir` | `/etc/traefik` | Traefik configuration directory |
| `traefik_dynamic_dir` | `/etc/traefik/dynamic` | Dynamic configuration directory |
| `traefik_acme_path` | `/etc/traefik/acme.json` | ACME certificate storage |
| `traefik_static_path` | `/etc/traefik/traefik.yml` | Static configuration file |
| `traefik_dynamic_path` | `/etc/traefik/dynamic/dynamic.yml` | Dynamic configuration file |
| `traefik_env_path` | `/etc/traefik/traefik.env` | Environment file (Cloudflare token) |
| `traefik_compose_path` | `/etc/traefik/docker-compose.yml` | Docker Compose file |
| `traefik_cf_env_var` | `CF_DNS_API_TOKEN` | Cloudflare environment variable name |
| `traefik_docker_packages` | `[docker.io, docker-compose]` | Docker packages to install |

### Required Variables (from cluster.yaml)

```yaml
proxy:
  acme_email: "you@example.net"
  cloudflare_dns_api_token: "YOUR_CLOUDFLARE_TOKEN"

network:
  domain: "internal.example.com"

services:
  - name: "service-name"
    target_vm: "target-vm-name"
    proxy:
      enable: true
      scheme: "http"
      port: 3000
      auth:
        users:
          - "user:$apr1$hashed_password"
      allow_cidrs:
        - "192.168.1.0/24"
```

## Configuration

### Static Configuration (traefik.yml)

Generated from `templates/traefik.yml.j2`:

- **Entrypoints**:
  - `web` (port 80): Redirects to HTTPS
  - `websecure` (port 443): HTTPS with TLS

- **Certificate Resolver**:
  - Name: `cf`
  - Provider: Cloudflare DNS
  - Storage: `/etc/traefik/acme.json`
  - Domain: `{{ network.domain }}` with wildcard SAN

- **File Provider**: Watches `/etc/traefik/dynamic` directory

- **API Dashboard**: Enabled

### Dynamic Configuration (dynamic.yml)

Auto-generated from `templates/dynamic.yml.j2` based on services in `cluster.yaml`:

**For each service with `proxy.enable: true`:**

1. **Router**: Routes `<service-name>-proxy.{{ domain }}` to service
2. **Service**: Load balancer pointing to `<service-name>.{{ domain }}:<port>`
3. **Middlewares** (optional):
   - IP whitelist (`allow_cidrs`)
   - Basic authentication (`auth.users`)

**Special handling for Traefik dashboard:**
- Services with `proxy.service: "api@internal"` route to Traefik API
- Matches paths: `/api` and `/dashboard`

### Service Proxy Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `enable` | bool | Yes | `false` | Enable proxying |
| `scheme` | string | No | `http` | Backend protocol (http/https) |
| `port` | int | Yes* | - | Backend port (*unless `service` set) |
| `service` | string | No | - | Use Traefik internal service (e.g., `api@internal`) |
| `backend_host` | string | No | `<name>.<domain>` | Backend hostname or IP address |
| `backend_url` | string | No | - | Full backend URL (overrides scheme/host/port) |
| `insecure_skip_verify` | bool | No | `false` | Skip TLS verification (for self-signed certs) |
| `auth.users` | list | No | - | Basic auth users (htpasswd format) |
| `allow_cidrs` | list | No | - | IP whitelist (CIDR notation) |

## Example Playbook

```yaml
- name: Configure Traefik on proxy hosts
  hosts: proxy
  become: true
  vars_files:
    - ../../cluster.yaml
  roles:
    - role: traefik
```

## Example Service Configurations

### Simple HTTP Service

```yaml
services:
  - name: "agh"
    target_vm: "dns-01"
    proxy:
      enable: true
      scheme: "http"
      port: 3000
```

Result: `https://agh-proxy.internal.example.com` → `http://agh.internal.example.com:3000`

### Service with Authentication

```yaml
services:
  - name: "admin-panel"
    target_vm: "internal-01"
    proxy:
      enable: true
      scheme: "http"
      port: 8080
      auth:
        users:
          - "admin:$apr1$H6uskkkW$IgXLP6ewTrSuBkTrqE8wj/"
```

Generate password hash:
```bash
htpasswd -nb admin mypassword
```

### Service with IP Filtering

```yaml
services:
  - name: "metrics"
    target_vm: "internal-01"
    proxy:
      enable: true
      scheme: "http"
      port: 9090
      allow_cidrs:
        - "192.168.1.0/24"
        - "10.0.0.0/8"
```

### Traefik Dashboard

```yaml
services:
  - name: "traefik"
    target_vm: "proxy-01"
    proxy:
      enable: true
      service: "api@internal"
      auth:
        users:
          - "admin:$apr1$..."
      allow_cidrs:
        - "192.168.1.0/24"
```

Result: `https://traefik-proxy.internal.example.com/dashboard/`

### Proxmox Web UI (External Backend)

```yaml
services:
  - name: "proxmox"
    target_vm: "pve"  # Not used for backend routing
    proxy:
      enable: true
      scheme: "https"
      port: 8006
      backend_host: "192.168.1.100"  # Direct IP or FQDN of Proxmox host
      insecure_skip_verify: true      # Required for self-signed certificates
      allow_cidrs:
        - "192.168.1.0/24"
```

Result: `https://proxmox-proxy.internal.example.com` → `https://192.168.1.100:8006`

**Note**: This configuration:
- Routes directly to a Proxmox host IP instead of using DNS resolution
- Skips TLS verification for Proxmox's self-signed certificate
- Restricts access to LAN only (no authentication required, Proxmox handles auth)

## Handlers

### Restart traefik

Triggered when configuration files change:
- `traefik.yml` (static config)
- `dynamic.yml` (dynamic config)
- `traefik.env` (environment file)
- `docker-compose.yml` (compose file)

Restarts Traefik container via Docker Compose.

## Files and Templates

| Template | Destination | Purpose |
|----------|-------------|---------|
| `traefik.yml.j2` | `/etc/traefik/traefik.yml` | Static configuration |
| `dynamic.yml.j2` | `/etc/traefik/dynamic/dynamic.yml` | Dynamic routing config |
| `traefik.env.j2` | `/etc/traefik/traefik.env` | Cloudflare token |
| `docker-compose.yml.j2` | `/etc/traefik/docker-compose.yml` | Docker Compose config |

## Deployment

The role performs these tasks:

1. Install Docker packages (`docker.io`, `docker-compose`)
2. Enable Docker service
3. Create Traefik directories
4. Create ACME storage file (`acme.json` with 0600 permissions)
5. Deploy configuration templates
6. Start Traefik via Docker Compose

## Accessing Traefik

### Dashboard

Access the Traefik dashboard at:
```
https://traefik-proxy.{{ network.domain }}/dashboard/
```

Note: Trailing slash is required.

### API

Access the Traefik API at:
```
https://traefik-proxy.{{ network.domain }}/api/
```

### Service Endpoints

All proxied services follow the pattern:
```
https://<service-name>-proxy.{{ network.domain }}
```

## Certificates

Let's Encrypt certificates are:
- **Automatically obtained** via Cloudflare DNS challenge
- **Wildcard**: Covers `*.{{ network.domain }}`
- **Auto-renewed**: Traefik handles renewal before expiration
- **Persisted**: Stored in `/etc/traefik/acme.json`

## Troubleshooting

### Certificate not obtained

1. Check Cloudflare API token permissions (Zone:DNS:Edit)
2. Verify `proxy.cloudflare_dns_api_token` in `cluster.yaml`
3. Check Traefik logs: `docker-compose -f /etc/traefik/docker-compose.yml logs`

### Service not accessible

1. Verify service is in `cluster.yaml` with `proxy.enable: true`
2. Check dynamic config: `cat /etc/traefik/dynamic/dynamic.yml`
3. Check backend service is running on target VM
4. Verify DNS resolution: `dig <service-name>.{{ network.domain }}`

### Dashboard access denied

1. Verify IP is in `allow_cidrs`
2. Check basic auth credentials
3. Ensure URL includes trailing slash: `/dashboard/`

### Configuration changes not applied

1. Check handler was triggered (role output)
2. Manually restart: `docker-compose -f /etc/traefik/docker-compose.yml restart`
3. Check for syntax errors: `docker-compose -f /etc/traefik/docker-compose.yml config`

## Security Considerations

- **Firewall**: UFW allows HTTP/HTTPS from `network.base_prefix.0/network.cidr_suffix`
- **Fail2ban**: Installed on proxy VMs for SSH protection
- **TLS**: All traffic encrypted with Let's Encrypt certificates
- **IP Filtering**: Optional CIDR-based restrictions per service
- **Authentication**: Optional basic auth per service
- **Secrets**: Cloudflare token stored in `/etc/traefik/traefik.env` (0600 permissions)

## Dependencies

None. All functionality is self-contained.

## License

MIT

## Author

neodymium6
