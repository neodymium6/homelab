# Homelab Infrastructure

Infrastructure as Code for managing a Proxmox-based homelab environment with bastion host architecture.

## Overview

This project automates the deployment and configuration of VMs on Proxmox VE using Terraform and Ansible. It implements a secure bastion host pattern where:

- **Local machine**: Creates and bootstraps the bastion VM
- **Bastion host**: Acts as a jump server and infrastructure controller for internal VMs
- **Internal VMs**: Managed exclusively from the bastion host

All VMs are configured with Nix and Home Manager for declarative system configuration.
All required Ansible roles are vendored in this repository—no external role dependencies. Standard collections (`community.general`, `community.crypto`, `community.docker`) are installed via `ansible-galaxy`.

## Architecture

```
┌─────────────────┐
│ Local Machine   │
│ (Your PC)       │
└────────┬────────┘
         │ SSH + Terraform
         ▼
┌─────────────────┐
│ Bastion VM      │
│ - Terraform     │──┐
│ - Ansible       │  │ SSH
│ - Home Manager  │  │
└─────────────────┘  │
                     ▼
            ┌──────────────────────────────┐
            │ Internal VMs                 │
            │ - DNS (Unbound + AGH)        │
            │ - Proxy (Traefik)            │
            │ - Apps (Docker)              │
            │ - Monitoring (Prometheus +   │
            │   Alertmanager + Grafana +   │
            │   Node Exporter)             │
            │ - Home Manager               │
            └──────────────────────────────┘
```

## Project Structure

```
homelab/
├── cluster.yaml              # Central cluster configuration
├── Makefile                  # Root orchestration (local → bastion)
├── local/                    # Executed from your local machine
│   ├── README.md            # Local deployment documentation
│   ├── terraform/           # Creates bastion VM on Proxmox
│   ├── ansible/             # Bootstraps bastion as controller
│   └── Makefile
└── bastion/                 # Executed on bastion VM
    ├── README.md            # Bastion deployment documentation
    ├── terraform/           # Creates internal VMs on Proxmox
    ├── ansible/             # Configures all VMs + Home Manager
    └── Makefile
```

## Quick Start

### Prerequisites

- **Local machine**: Terraform, Ansible, yq, SSH access to Proxmox
- **Proxmox VE**: Running server with Debian cloud-init template
- **Git**: For repository management

`yq` is required by the root `Makefile` to read values from `cluster.yaml` (for example, bastion host/user resolution).

For detailed prerequisites, see [local/README.md](local/README.md).

### Setup

1. **Clone the repository**

```bash
git clone https://github.com/neodymium6/homelab.git
cd homelab
```

2. **Configure cluster settings**

```bash
cp cluster.yaml.example cluster.yaml
# Edit cluster.yaml with your Proxmox and network settings
```

3. **Configure Terraform credentials**

Create `local/terraform/terraform.tfvars` and `bastion/terraform/terraform.tfvars` with your Proxmox credentials.

See [local/README.md](local/README.md) for detailed configuration instructions.

4. **Deploy**

```bash
make all
```

This will deploy the bastion VM, bootstrap it, and then deploy internal VMs from the bastion.

## Configuration

### cluster.yaml

Central configuration file defining:

```yaml
proxmox:
  endpoint: "https://your-proxmox:8006/api2/json"
  node_name: "pve"
  datastore: "local-zfs"
  debian_template_vmid: 9000

network:
  base_prefix: "192.168.1"
  cidr_suffix: 24
  gateway_v4: "192.168.1.1"
  homelab_dns:
    - "192.168.1.102"
  upstream_dns:
    - "192.168.1.1"
    - "1.1.1.1"
  domain: "internal.example.com"

login_user: "youruser"

vms:
  bastion-01:
    vmid: 101
    role: "bastion"
    cpu_cores: 2
    memory_mb: 2048

  dns-01:
    vmid: 102
    role: "dns"
    cpu_cores: 2
    memory_mb: 2048

  proxy-01:
    vmid: 103
    role: "proxy"
    cpu_cores: 2
    memory_mb: 2048

  app-01:
    vmid: 201
    role: "app"
    cpu_cores: 4
    memory_mb: 8192

services:
  - name: "bastion"
    target_vm: "bastion-01"
  - name: "dns"
    target_vm: "dns-01"
  - name: "proxy"
    target_vm: "proxy-01"
  - name: "app"
    target_vm: "app-01"
  - name: "agh"
    target_vm: "dns-01"
    proxy:
      enable: true
      scheme: "http"
      port: 3000
  - name: "ntfy"
    target_vm: "app-01"
    upstream_base_url: "https://ntfy.sh"
    security:
      message_size_limit: "4K"
      message_delay_limit: "1h"
      visitor_request_limit_burst: 30
      visitor_request_limit_replenish: "10s"
      visitor_message_daily_limit: 200
      visitor_subscription_limit: 20
      visitor_subscriber_rate_limiting: true
    proxy:
      enable: true
      scheme: "http"
      port: 8079
      methods:
        - "GET"
        - "HEAD"
        - "OPTIONS"
      public_hostnames:
        - "ntfy.example.com"
    homepage:
      display_name: "ntfy"
      category: "Infrastructure"
      icon: "mdi-bell-badge-outline"
      href: "https://ntfy.example.com"
  - name: "ntfy-pub"
    target_vm: "app-01"
    proxy:
      enable: true
      scheme: "http"
      port: 8079
      methods:
        - "POST"
        - "PUT"
        - "OPTIONS"
      public_hostnames:
        - "ntfy-pub.example.com"
  - name: "personal-site"
    target_vm: "app-01"
    image: "ghcr.io/neodymium6/profile.neodymium6.net:latest"
    update_enable: true
    update_on_boot_sec: "2m"
    update_unit_active_sec: "15m"
    update_cleanup_enable: true
    update_cleanup_until: "168h"
    proxy:
      enable: true
      scheme: "http"
      backends:
        - port: 8080
        - port: 8081
      healthcheck:
        path: "/"
        interval: "1s"
        timeout: "500ms"
      retry:
        attempts: 2
        initial_interval: "100ms"
      public_hostnames:
        - "www.example.com"
  - name: "traefik"
    target_vm: "proxy-01"
    proxy:
      enable: true
      service: "api@internal"
      auth:
        users:
          - "admin:$apr1$CHANGE_ME"
      allow_cidrs:
        - "192.168.1.0/24"

proxy:
  acme_email: "you@example.net"
  cloudflare_dns_api_token: "CF_TOKEN_HERE"
  cloudflare_tunnel_token: "CF_TUNNEL_TOKEN_HERE"

docker:
  reserved_cidr: "172.30.0.0/16"
  networks:
    monitoring:
      subnet: "172.30.10.0/28"

secrets:
  monitoring:
    grafana_admin_user: "admin"
    grafana_admin_password: "changeme"
  ntfy:
    auth_users:
      - "subscriber:$2a$10$REPLACE_WITH_BCRYPT_HASH:user"
      - "publisher:$2a$10$REPLACE_WITH_BCRYPT_HASH:user"
    auth_access:
      - "subscriber:*:read"
      - "publisher:*:write"
```

For `ntfy`, use two public hosts with different HTTP method policies on the same backend:
- `ntfy.<domain>` for subscribe/read paths (`GET`, `HEAD`, `OPTIONS`)
- `ntfy-pub.<domain>` for publish paths (`POST`, `PUT`, `OPTIONS`)

This keeps read clients and publish clients separated by both router method matching and ntfy ACLs.

VMs are assigned IPs based on their VMID: `<base_prefix>.<vmid>/<cidr_suffix>`

Example: VMID 102 → 192.168.1.102/24

## Deployment Workflow

```
┌────────────────────────────────────────────────────┐
│ Local Machine: make all                            │
├────────────────────────────────────────────────────┤
│ 1. terraform: Create bastion VM                    │
│ 2. ansible: Bootstrap bastion                      │
│    - Install Python + Ansible venv                 │
│    - Download Terraform to /usr/local/bin          │
│    - Clone homelab repo                            │
│    - Copy cluster.yaml + terraform.tfvars          │
└────────────┬───────────────────────────────────────┘
             │ SSH to bastion
             ▼
┌────────────────────────────────────────────────────┐
│ Bastion VM: make all                               │
├────────────────────────────────────────────────────┤
│ 1. terraform: Create internal VMs                  │
│ 2. ansible: Configure bastion                      │
│    - Generate internal SSH keypair                 │
│    - SSH hardening (UFW + optional fail2ban)       │
│    - SSH client config for internal hosts          │
│ 3. ansible: Configure internal VMs                 │
│    - SSH hardening (allow only from bastion)       │
│    - Install and configure Traefik (proxy role)    │
│    - Run Cloudflare Tunnel (proxy role)            │
│    - Install and configure Unbound (dns role)      │
│    - Install and configure AdGuard Home (dns role) │
│    - Deploy ntfy server (app role)                 │
│    - Deploy Homepage dashboard (app role)          │
│    - Deploy personal-site container (app role)     │
│    - Install Node Exporter (all VMs)               │
│    - Install Prometheus (app role)                 │
│    - Install Alertmanager (app role)               │
│    - Install Grafana (app role)                    │
│    - Configure systemd-resolved (all VMs)          │
│ 4. ansible: Install Home Manager on all VMs        │
│    - Install Nix (multi-user daemon)               │
│    - Clone home-manager config repository          │
│    - Apply Home Manager switch via flakes          │
└────────────────────────────────────────────────────┘
```

## Makefile Targets

### Root Makefile

Requirement: `yq` must be installed on the local machine because the root `Makefile` parses `cluster.yaml`.

| Target | Description |
|--------|-------------|
| `make all` | Deploy local, then bastion (full deployment) |
| `make local` | Deploy only local components (bastion VM) |
| `make bastion` | Execute deployment on bastion via SSH |
| `make debug GIT_BRANCH=<branch>` | Deploy with custom git branch |
| `make clean` | Destroy all infrastructure |

For detailed targets and usage, see:
- [local/README.md](local/README.md) - Local deployment targets
- [bastion/README.md](bastion/README.md) - Bastion deployment targets

## SSH Access

### Access Bastion

```bash
ssh <login_user>@<base_prefix>.<bastion_vmid>
```

### Access Internal VMs

Internal VMs are only accessible from bastion using the dedicated SSH key:

```bash
# From bastion
ssh -i ~/.ssh/id_ed25519_internal <login_user>@<internal_vm_ip>
```

## Security Features

- **SSH Hardening**: UFW with optional fail2ban, password authentication disabled, key-only access enforced
- **Managed SSH Access**: Generated internal key (`id_ed25519_internal`) plus templated SSH client config for internal hosts
- **Bastion Pattern**: Internal VMs not directly accessible from outside
- **Git Ignored Secrets**: All sensitive files (`.tfvars`, keys) excluded from git

## DNS Services

VMs with `role: dns` are configured with DNS services for the homelab:

- **Unbound**: Local recursive DNS resolver listening on port 5353
  - Serves DNS records for homelab domain (`network.domain`, e.g. `internal.example.com`)
  - Falls back to `home.arpa` only when `network.domain` is not set
  - Forwards upstream queries to external DNS (1.1.1.1, gateway)
  - Configured with A, CNAME, and PTR records from `cluster.yaml`

- **AdGuard Home**: DNS filtering and ad-blocking proxy listening on port 53
  - HTTP interface on port 3000
  - Forwards queries to Unbound on localhost:5353
  - Provides DNS-based ad filtering and query logging

All VMs are configured with systemd-resolved to use the homelab DNS server specified in `network.homelab_dns`.

DNS resolution flow:
```
VM → systemd-resolved → AdGuard Home (port 53) → Unbound (port 5353) → Upstream DNS
```

## Docker Application Host

VMs with `role: app` are configured as Docker hosts for running containerized applications:

- **Docker Engine**: Docker runtime for running containers
- **Docker Compose**: Tool for defining and running multi-container applications
- **User Access**: Login user added to docker group for non-root Docker access
- **Web Apps**: Homepage dashboard and personal-site container stack
- **Notifications**: ntfy server for self-hosted push notifications
- **Monitoring**: Prometheus, Alertmanager, and Grafana deployed for infrastructure observability

The app-01 VM is provisioned with higher resources (4 CPU cores, 8GB RAM) to accommodate multiple Docker Compose stacks.

Personal-site uses dual backends (`:8080`, `:8081`) with rolling updates and Traefik health checks/retry, enabling zero-downtime style deployments for normal web traffic.

### Homepage Dashboard

The Homepage dashboard is deployed on app-01 as the primary service discovery and monitoring interface:

- **Service Links**: Automatic links to infrastructure services (Traefik, AdGuard Home, etc.)
- **Resource Monitoring**: CPU, memory, and disk usage widgets
- **Docker Compose**: Deployed via docker-compose in `/opt/stacks/homepage`
- **Access**: Available at `https://homepage-proxy.<domain>` via Traefik
- **Firewall**: UFW configured to allow connections only from proxy-01

## Reverse Proxy with Traefik

VMs with `role: proxy` are configured with Traefik as a reverse proxy for exposing internal services via HTTPS.

### Features

- **Automatic HTTPS**: Let's Encrypt certificates via ACME DNS challenge (Cloudflare)
- **Wildcard Certificates**: Automatically covers `*.internal.example.com`
- **HTTP → HTTPS Redirect**: All HTTP traffic redirected to HTTPS
- **Dynamic Configuration**: Services auto-configured from `cluster.yaml`
- **Dashboard**: Traefik API dashboard with authentication and IP filtering
- **Middleware Support**: IP whitelisting and basic authentication per service

### Configuration

Traefik is configured in two parts: static configuration (entrypoints, ACME resolver) and dynamic configuration (routers, services, middlewares).

#### Static Configuration (traefik.yml)

- **Entrypoints**: HTTP (port 80), HTTPS (port 443), tunnel (port 8080 on localhost)
- **ACME Resolver**: Cloudflare DNS challenge with wildcard certificate
- **File Provider**: Watches `/etc/traefik/dynamic` for dynamic config

#### Dynamic Configuration (dynamic.yml)

Auto-generated from `cluster.yaml` services with `proxy.enable: true`:

```yaml
services:
  - name: "agh"
    target_vm: "dns-01"
    proxy:
      enable: true
      scheme: "http"          # Backend protocol (default: http)
      port: 3000              # Backend port

  - name: "personal-site"
    target_vm: "app-01"
    image: "ghcr.io/neodymium6/profile.neodymium6.net:latest"
    update_enable: true
    update_on_boot_sec: "2m"
    update_unit_active_sec: "15m"
    update_cleanup_enable: true
    update_cleanup_until: "168h"
    proxy:
      enable: true
      scheme: "http"
      backends:
        - port: 8080
        - port: 8081
      healthcheck:
        path: "/"
        interval: "1s"
        timeout: "500ms"
      retry:
        attempts: 2
        initial_interval: "100ms"
      public_hostnames:
        - "www.example.com"

  - name: "traefik"
    target_vm: "proxy-01"
    proxy:
      enable: true
      service: "api@internal"  # Special: Traefik dashboard
      auth:
        users:
          - "admin:$apr1$..."   # htpasswd format
      allow_cidrs:
        - "192.168.1.0/24"      # IP whitelist
```

This creates:
- **Router**: `agh-proxy.internal.example.com` → `http://agh.internal.example.com:3000`
- **Router**: `personal-site-proxy.internal.example.com` and `www.example.com` → load-balanced backends (`:8080`, `:8081`)
- **Router**: `traefik-proxy.internal.example.com` → Traefik dashboard (with auth + IP filter)

#### Proxy Configuration Block

The `proxy` section in `cluster.yaml` defines global Traefik settings:

```yaml
proxy:
  acme_email: "you@example.net"              # Let's Encrypt email
  cloudflare_dns_api_token: "CF_TOKEN_HERE"  # Cloudflare API token for DNS challenge
  cloudflare_tunnel_token: "CF_TUNNEL_TOKEN_HERE"  # Cloudflare tunnel token
```

### Service Proxy Options

Per-service proxy configuration options:

| Option | Description | Required | Default |
|--------|-------------|----------|---------|
| `enable` | Enable proxying for this service | Yes | `false` |
| `scheme` | Backend protocol (http/https) | No | `http` |
| `port` | Single backend service port | Yes (unless `service`, `backend_url`, or `backends` set) | - |
| `methods` | Allowed HTTP methods at router level (e.g., `["POST", "PUT"]`) | No | - |
| `backends` | Multiple backend targets (`[{port, host?}]`) | No | - |
| `service` | Use Traefik internal service (e.g., `api@internal`) | No | - |
| `backend_url` | Full backend URL (overrides `scheme/host/port`) | No | - |
| `backend_host` | Default backend host for `port` or `backends[].host` fallback | No | `<name>.<domain>` |
| `healthcheck` | Traefik health check block (`path`, `interval`, `timeout`) | No | - |
| `retry` | Retry middleware block (`attempts`, `initial_interval`) | No | - |
| `public_hostnames` | Additional public hostnames. Internal `-proxy` host remains available. | No | - |
| `auth.users` | Basic auth users (htpasswd format) | No | - |
| `allow_cidrs` | IP whitelist (CIDR notation) | No | - |
| `allow_public_with_cidrs` | Allow `public_hostnames` + `allow_cidrs` combination without validation error | No | `false` |

### DNS Integration

Traefik-proxied services automatically get CNAME entries in Unbound:

- Service: `agh.internal.example.com` → `192.168.1.102` (dns-01)
- Proxy endpoint: `agh-proxy.internal.example.com` → `proxy.internal.example.com` (CNAME)

### Deployment

Traefik runs as a Docker container managed by Docker Compose:

```yaml
# /etc/traefik/docker-compose.yml
services:
  traefik:
    image: traefik:v2.11
    ports:
      - "80:80"
      - "443:443"
      - "127.0.0.1:8080:8080"
    volumes:
      - /etc/traefik/traefik.yml:/etc/traefik/traefik.yml:ro
      - /etc/traefik/dynamic:/etc/traefik/dynamic:ro
      - /etc/traefik/acme.json:/etc/traefik/acme.json
    env_file:
      - /etc/traefik/traefik.env
    restart: unless-stopped
```

Configuration files:
- `/etc/traefik/traefik.yml` - Static configuration
- `/etc/traefik/dynamic/dynamic.yml` - Dynamic configuration (auto-generated)
- `/etc/traefik/acme.json` - Certificate storage
- `/etc/traefik/traefik.env` - Environment variables (Cloudflare token)

### Accessing Services

After deployment, proxied services are accessible via:

```
https://<service-name>-proxy.internal.example.com
```

Optional public hostnames can be added per service with `proxy.public_hostnames`.
If you expose a service publicly via Cloudflare Tunnel, do not set restrictive `allow_cidrs` unless you explicitly include Cloudflare egress ranges.
Validation in the Traefik role will fail when both are set, unless `proxy.allow_public_with_cidrs: true` is explicitly added.

Examples:
- AdGuard Home UI: `https://agh-proxy.internal.example.com`
- Personal Site (internal): `https://personal-site-proxy.internal.example.com`
- Personal Site (public): `https://www.example.com` (if configured in Cloudflare Tunnel)
- Traefik Dashboard: `https://traefik-proxy.internal.example.com`

### Security

- **Firewall**: UFW allows HTTP/HTTPS from `192.168.1.0/24` on proxy VMs
- **Fail2ban**: Enabled on proxy VMs for SSH protection
- **TLS**: All traffic encrypted with Let's Encrypt certificates
- **IP Whitelisting**: Optional per-service CIDR restrictions
- **Basic Auth**: Optional per-service authentication

### Certificate Management

Let's Encrypt certificates are automatically:
- **Obtained**: On first request via Cloudflare DNS challenge
- **Renewed**: Before expiration (Traefik handles renewal)
- **Stored**: In `/etc/traefik/acme.json` (persisted across restarts)

Wildcard certificate covers:
- `internal.example.com`
- `*.internal.example.com`

## Monitoring Stack

The homelab includes a comprehensive monitoring stack for infrastructure observability, deployed on VMs with `role: app`.

### Components

#### Prometheus

**Metrics Collection and Time-Series Database**

- **Version**: v2.49.0
- **Port**: 9090
- **Deployment**: Docker container via Docker Compose
- **Storage**: `/opt/stacks/prometheus/data`
- **Configuration**: Auto-generated from `cluster.yaml` to scrape all VMs

Prometheus collects metrics from:
- **Node Exporter** on all VMs (system metrics: CPU, memory, disk, network)
- **Proxmox VE** API (via optional Proxmox exporter)

**Scrape Configuration**:
```yaml
scrape_configs:
  - job_name: 'node-exporter'
    static_configs:
      - targets:
          - '192.168.1.121:9100'  # bastion-01
          - '192.168.1.122:9100'  # app-01
          - '192.168.1.123:9100'  # dns-01
          - '192.168.1.124:9100'  # proxy-01
```

**Access**: `https://prometheus-proxy.internal.example.com` via Traefik

**Networking**: Uses dedicated monitoring network (`172.30.10.0/28`) isolated from application networks

**Firewall**: UFW allows access only from proxy VM for web UI, and from monitoring Docker network for container-based scrapers

#### Alertmanager

**Alert Grouping, Routing, and Silencing**

- **Version**: v0.27.0
- **Port**: 9093
- **Deployment**: Docker container via Docker Compose
- **Storage**: `/opt/stacks/alertmanager/data`
- **Notifications**: Alertmanager webhook payloads are transformed by `am_ntfy_bridge` and published to ntfy
- **Recommended ntfy Route**: Use internal publish endpoint `https://ntfy-pub-proxy.<domain>` (POST-capable)

**Prometheus Integration**: Prometheus automatically discovers Alertmanager on the same app host via `alertmanager:9093`

**Access**: Optional via Traefik at `https://alertmanager-proxy.internal.example.com` when `services[].proxy.enable` is configured

**Firewall**: UFW allows proxy-only access when Alertmanager port exposure is enabled

#### Grafana

**Metrics Visualization and Dashboards**

- **Version**: v10.3.0
- **Port**: 3001
- **Deployment**: Docker container via Docker Compose
- **Storage**: `/opt/stacks/grafana/data`
- **Credentials**: Configured in `cluster.yaml` under `secrets.monitoring`

**Pre-provisioned Dashboards**:
1. **Node Exporter Full** (`node-exporter-full.json`)
   - Comprehensive system metrics visualization
   - CPU, memory, disk I/O, network, filesystem metrics
   - 15KB+ dashboard with detailed graphs

2. **Proxmox Nodes** (`proxmox-nodes.json`)
   - Proxmox-specific monitoring
   - Hypervisor resource usage

**Datasource**: Prometheus automatically configured as default datasource

**Access**: `https://grafana-proxy.internal.example.com` via Traefik

**Firewall**: UFW allows access only from proxy VM

#### Node Exporter

**System Metrics Export**

- **Version**: v1.10.2
- **Port**: 9100
- **Deployment**: Systemd service (binary installation)
- **Installation**: On all VMs in the cluster

Node Exporter exposes hardware and OS metrics for Prometheus scraping:
- CPU usage and load average
- Memory and swap usage
- Disk I/O and filesystem metrics
- Network interface statistics
- System uptime

**Firewall**: UFW rules allow access from:
- App VM IP (for Prometheus scraper)
- Monitoring Docker network subnet (for containerized Prometheus)

### Network Architecture

The monitoring stack uses a dedicated external Docker network for isolation:

```yaml
docker:
  reserved_cidr: "172.30.0.0/16"
  networks:
    monitoring:
      subnet: "172.30.10.0/28"
```

This network:
- **Isolates** monitoring traffic from application containers
- **Enables** Prometheus container to scrape node_exporter on the same host
- **Secured** with UFW rules allowing only necessary traffic

### Configuration

Add monitoring services to `cluster.yaml`:

```yaml
services:
  - name: "prometheus"
    target_vm: "app-01"
    proxy:
      enable: true
      scheme: "http"
      port: 9090
      allow_cidrs:
        - "192.168.1.0/24"
    homepage:
      display_name: "Prometheus"
      category: "Monitoring"
      icon: "si-prometheus"

  - name: "alertmanager"
    target_vm: "app-01"
    notifications:
      ntfy_topic: "alerts"
      ntfy_base_url: "https://ntfy-pub-proxy.internal.example.com"
    proxy:
      enable: true
      scheme: "http"
      port: 9093
      allow_cidrs:
        - "192.168.1.0/24"
    homepage:
      display_name: "Alertmanager"
      category: "Monitoring"
      icon: "si-prometheus"

  - name: "grafana"
    target_vm: "app-01"
    proxy:
      enable: true
      scheme: "http"
      port: 3001
      allow_cidrs:
        - "192.168.1.0/24"
    homepage:
      display_name: "Grafana"
      category: "Monitoring"
      icon: "si-grafana"

docker:
  reserved_cidr: "172.30.0.0/16"
  networks:
    monitoring:
      subnet: "172.30.10.0/28"

secrets:
  monitoring:
    grafana_admin_user: "admin"
    grafana_admin_password: "changeme"
  alertmanager:
    ntfy_user: "alerting"
    ntfy_password: "change_me"
    # ntfy_token: "tk_..."
```

### Deployment Flow

1. **Node Exporter** installed on all VMs via systemd service
2. **Prometheus** deployed on app-01 with auto-generated scrape config
3. **Alertmanager** deployed on app-01 with ntfy webhook bridge
4. **Grafana** deployed on app-01 with Prometheus datasource pre-configured
5. **Dashboards** automatically provisioned on Grafana startup
6. **UFW Rules** configured to allow monitoring traffic

### Accessing Monitoring

After deployment, access the monitoring stack via:

- **Grafana Dashboard**: `https://grafana-proxy.internal.example.com`
  - Login with credentials from `cluster.yaml` secrets
  - Pre-loaded dashboards available immediately

- **Prometheus UI**: `https://prometheus-proxy.internal.example.com`
  - Query metrics directly
  - View scrape targets and configuration

- **Alertmanager UI**: `https://alertmanager-proxy.internal.example.com` (optional if proxied)
  - View active alerts, silences, and receiver status

- **Homepage**: Links to monitoring services in "Monitoring" category

## Home Manager Integration

All VMs receive Nix and Home Manager for declarative system configuration. The Home Manager configuration is maintained in a separate repository and cloned to `~/.config/home-manager` on each VM.

Repository: [neodymium6/home-manager](https://github.com/neodymium6/home-manager)

## Ansible Roles (vendored)

- `local/ansible/roles/controller_bootstrap`: Installs Python + venv, installs Ansible, downloads Terraform to `/usr/local/bin`, clones this repo on the bastion, and copies `cluster.yaml` + `terraform.tfvars`.
- `bastion/ansible/roles/ssh_keypair`: Generates `~/.ssh/id_ed25519_internal` for accessing internal VMs from the bastion.
- `bastion/ansible/roles/ssh_hardening`: Applies UFW rules (open or bastion-restricted), disables password SSH, enables pubkey auth, optional fail2ban.
- `bastion/ansible/roles/ssh_client_config`: Renders SSH `config` entries for all internal VMs using the internal key.
- `bastion/ansible/roles/traefik`: Installs Docker and Traefik reverse proxy on VMs with `role: proxy`, with dynamic configuration generation from `cluster.yaml`.
- `bastion/ansible/roles/cloudflare_tunnel`: Deploys `cloudflared` on VMs with `role: proxy` and connects Cloudflare Tunnel to Traefik tunnel entrypoint (`127.0.0.1:8080`).
- `bastion/ansible/roles/docker`: Installs Docker and Docker Compose on VMs with `role: app`, and adds specified users to the docker group.
- `bastion/ansible/roles/ntfy`: Deploys ntfy server via Docker Compose on VMs with `role: app`, with login/auth and optional proxy-only UFW access.
- `bastion/ansible/roles/homepage`: Deploys Homepage dashboard via Docker Compose on VMs with `role: app`, with UFW rules to restrict access to proxy-01.
- `bastion/ansible/roles/personal_site`: Deploys a simple Nginx-based personal site via Docker Compose on app VMs, with optional proxy-only UFW access.
- `bastion/ansible/roles/node_exporter`: Installs Node Exporter (v1.10.2) as a systemd service on all VMs for system metrics export, with UFW rules allowing access from app VM and monitoring Docker network.
- `bastion/ansible/roles/prometheus`: Deploys Prometheus (v2.49.0) via Docker Compose on VMs with `role: app`, with auto-generated scrape configuration from `cluster.yaml` and dedicated monitoring network.
- `bastion/ansible/roles/alertmanager`: Deploys Alertmanager (v0.27.0) with an `am_ntfy_bridge` webhook adapter for ntfy notifications.
- `bastion/ansible/roles/grafana`: Deploys Grafana (v10.3.0) via Docker Compose on VMs with `role: app`, with pre-provisioned Prometheus datasource and dashboards (Node Exporter Full, Proxmox Nodes).
- `bastion/ansible/roles/unbound`: Installs and configures Unbound recursive DNS resolver on VMs with `role: dns`.
- `bastion/ansible/roles/adguard_home`: Installs and configures AdGuard Home DNS filtering on VMs with `role: dns`.
- `bastion/ansible/roles/resolved_dns`: Configures systemd-resolved to use homelab DNS servers.
- `bastion/ansible/roles/nix_installer`: Installs Nix (multi-user daemon) and writes `~/.config/nix/nix.conf` with experimental features.
- `bastion/ansible/roles/home_manager`: Clones the Home Manager repo and runs `nix run home-manager/master -- switch` via flakes.

## Troubleshooting

### Bastion unreachable during cleanup

If bastion is already destroyed, `make clean` will warn but continue cleaning local resources.

### Terraform state issues

```bash
cd local/terraform  # or bastion/terraform
rm -rf .terraform terraform.tfstate*
terraform init
```

### Ansible connection failures

- Verify VM is running (check Proxmox console)
- Ensure cloud-init has completed
- Check SSH key configuration
- Verify network connectivity

### Home Manager failures

- Verify internet access from VM
- Check Nix daemon: `systemctl status nix-daemon`
- Verify experimental features in `~/.config/nix/nix.conf`

## Documentation

- [local/README.md](local/README.md) - Local deployment details
- [bastion/README.md](bastion/README.md) - Bastion deployment details

## License

MIT License - see [LICENSE](LICENSE) file for details.
