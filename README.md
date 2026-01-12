# Homelab Infrastructure

Infrastructure as Code for managing a Proxmox-based homelab environment with bastion host architecture.

## Overview

This project automates the deployment and configuration of VMs on Proxmox VE using Terraform and Ansible. It implements a secure bastion host pattern where:

- **Local machine**: Creates and bootstraps the bastion VM
- **Bastion host**: Acts as a jump server and infrastructure controller for internal VMs
- **Internal VMs**: Managed exclusively from the bastion host

All VMs are configured with Nix and Home Manager for declarative system configuration.
All required Ansible roles are vendored in this repository—no external role dependencies. Standard collections (`community.general`, `community.crypto`) are installed via `ansible-galaxy`.

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
            ┌──────────────────────┐
            │ Internal VMs         │
            │ - DNS (Unbound + AGH)│
            │ - Home Manager       │
            └──────────────────────┘
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
```

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
│    - Install and configure Unbound (dns role)      │
│    - Install and configure AdGuard Home (dns role) │
│    - Configure systemd-resolved (all VMs)          │
│ 4. ansible: Install Home Manager on all VMs        │
│    - Install Nix (multi-user daemon)               │
│    - Clone home-manager config repository          │
│    - Apply Home Manager switch via flakes          │
└────────────────────────────────────────────────────┘
```

## Makefile Targets

### Root Makefile

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
  - Serves DNS records for homelab domain (home.arpa)
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

The app-01 VM is provisioned with higher resources (4 CPU cores, 8GB RAM) to accommodate multiple Docker Compose stacks.

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

- **Entrypoints**: HTTP (port 80) and HTTPS (port 443)
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
- **Router**: `traefik-proxy.internal.example.com` → Traefik dashboard (with auth + IP filter)

#### Proxy Configuration Block

The `proxy` section in `cluster.yaml` defines global Traefik settings:

```yaml
proxy:
  acme_email: "you@example.net"              # Let's Encrypt email
  cloudflare_dns_api_token: "CF_TOKEN_HERE"  # Cloudflare API token for DNS challenge
```

### Service Proxy Options

Per-service proxy configuration options:

| Option | Description | Required | Default |
|--------|-------------|----------|---------|
| `enable` | Enable proxying for this service | Yes | `false` |
| `scheme` | Backend protocol (http/https) | No | `http` |
| `port` | Backend service port | Yes (unless `service` set) | - |
| `service` | Use Traefik internal service (e.g., `api@internal`) | No | - |
| `auth.users` | Basic auth users (htpasswd format) | No | - |
| `allow_cidrs` | IP whitelist (CIDR notation) | No | - |

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

Examples:
- AdGuard Home UI: `https://agh-proxy.internal.example.com`
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

## Home Manager Integration

All VMs receive Nix and Home Manager for declarative system configuration. The Home Manager configuration is maintained in a separate repository and cloned to `~/.config/home-manager` on each VM.

Repository: [neodymium6/home-manager](https://github.com/neodymium6/home-manager)

## Ansible Roles (vendored)

- `local/ansible/roles/controller_bootstrap`: Installs Python + venv, installs Ansible, downloads Terraform to `/usr/local/bin`, clones this repo on the bastion, and copies `cluster.yaml` + `terraform.tfvars`.
- `bastion/ansible/roles/ssh_keypair`: Generates `~/.ssh/id_ed25519_internal` for accessing internal VMs from the bastion.
- `bastion/ansible/roles/ssh_hardening`: Applies UFW rules (open or bastion-restricted), disables password SSH, enables pubkey auth, optional fail2ban.
- `bastion/ansible/roles/ssh_client_config`: Renders SSH `config` entries for all internal VMs using the internal key.
- `bastion/ansible/roles/traefik`: Installs Docker and Traefik reverse proxy on VMs with `role: proxy`, with dynamic configuration generation from `cluster.yaml`.
- `bastion/ansible/roles/docker`: Installs Docker and Docker Compose on VMs with `role: app`, and adds specified users to the docker group.
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
