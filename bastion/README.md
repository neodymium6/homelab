# Bastion Deployment

Terraform and Ansible configurations executed on the bastion VM to create and configure internal VMs.

## Overview

1. **Terraform**: Creates internal VMs on Proxmox
2. **Ansible**: Configures bastion and internal VMs
   - Generates SSH key for internal access
   - Applies SSH hardening (bastion + internal)
   - Configures SSH client on bastion
   - Installs Traefik reverse proxy on proxy role VMs
   - Runs Cloudflare Tunnel on proxy role VMs
   - Deploys ntfy notification server on app role VMs
   - Installs DNS services (Unbound + AdGuard Home) on dns role VMs
   - Installs monitoring stack (Node Exporter, Prometheus, Grafana)
   - Configures systemd-resolved on all VMs
3. **Ansible**: Installs Nix and Home Manager on all VMs
   - Installs Nix (multi-user daemon)
   - Clones and applies Home Manager config via flakes

## Directory Structure

```
bastion/
├── terraform/               # Internal VMs infrastructure
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars    # Your credentials (git-ignored)
└── ansible/                 # Configuration management
    ├── site_bastion.yaml    # Bastion configuration (ssh_keypair, ssh_hardening, ssh_client_config)
    ├── site_internal.yaml   # Internal VMs configuration (ssh_hardening, traefik, cloudflare_tunnel, docker, ntfy, homepage, personal_site, node_exporter, prometheus, grafana, unbound, adguard_home, resolved_dns)
    ├── site_homemanager.yaml # Home Manager setup (nix_installer, home_manager)
    └── roles/               # Vendored Ansible roles (no external role dependencies)

## Ansible Roles (vendored on bastion)

- `roles/ssh_keypair`: Generates `~/.ssh/id_ed25519_internal` for internal VM access.
- `roles/ssh_hardening`: Applies UFW (open or bastion-restricted), optional fail2ban, and enforces key-only SSH.
- `roles/ssh_client_config`: Renders SSH `config` entries for all internal hosts using the internal key.
- `roles/traefik`: Installs Docker and Traefik reverse proxy on VMs with `role: proxy`, with dynamic configuration generation from `cluster.yaml`.
- `roles/cloudflare_tunnel`: Deploys `cloudflared` on VMs with `role: proxy`, forwarding Cloudflare Tunnel traffic to Traefik tunnel entrypoint.
- `roles/docker`: Installs Docker and Docker Compose on VMs with `role: app`, and adds specified users to the docker group.
- `roles/ntfy`: Deploys ntfy server via Docker Compose on VMs with `role: app`, with optional proxy-only UFW access.
- `roles/homepage`: Deploys Homepage dashboard via Docker Compose on VMs with `role: app`, with UFW rules to restrict access to proxy-01.
- `roles/personal_site`: Deploys a personal-site container image via Docker Compose on app VMs, with optional proxy-only UFW access and a systemd timer for rolling zero-downtime style refresh.
- `roles/node_exporter`: Installs Node Exporter (v1.10.2) as a systemd service on all VMs for system metrics export.
- `roles/prometheus`: Deploys Prometheus (v2.49.0) via Docker Compose on VMs with `role: app`.
- `roles/grafana`: Deploys Grafana (v10.3.0) via Docker Compose on VMs with `role: app`.
- `roles/unbound`: Installs and configures Unbound recursive DNS resolver on VMs with `role: dns`.
- `roles/adguard_home`: Installs and configures AdGuard Home DNS filtering on VMs with `role: dns`.
- `roles/resolved_dns`: Configures systemd-resolved to use homelab DNS servers.
- `roles/nix_installer`: Installs Nix (multi-user daemon) and writes `~/.config/nix/nix.conf`.
- `roles/home_manager`: Clones the Home Manager repo and runs `nix run home-manager/master -- switch`.
```

## Configuration

### terraform.tfvars

Create `bastion/terraform/terraform.tfvars`:

```hcl
proxmox_username       = "root@pam"
proxmox_password       = "your_proxmox_password"
debian_user_password   = "your_vm_password"
```

This file should be copied by the local deployment, but you can create it manually if needed.

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make all` | Full deployment (init → bastion-setup → apply → internal-setup → homemanager) |
| `make tf-init` | Initialize Terraform |
| `make tf-apply` | Create internal VMs |
| `make bastion-setup` | Configure bastion (ssh_keypair, ssh_hardening, ssh_client_config) |
| `make internal-setup` | Configure internal VMs (ssh_hardening, traefik, cloudflare_tunnel, docker, ntfy, homepage, personal_site, node_exporter, prometheus, grafana, unbound, adguard_home, resolved_dns) |
| `make homemanager` | Install Nix + Home Manager on all VMs (nix_installer, home_manager) |
| `make clean` | Destroy internal VMs |

## Deployment Workflow

```
1. bastion-setup (runs roles on bastion)
   - Generate id_ed25519_internal SSH key pair
   - Harden SSH (UFW + optional fail2ban)
   - Render SSH client config for internal hosts

2. tf-apply
   - Create internal VMs with id_ed25519_internal.pub

3. internal-setup
   - Configure SSH hardening on internal VMs (allow only from bastion)
   - Install and configure Traefik on proxy role VMs
   - Run Cloudflare Tunnel on proxy role VMs
   - Deploy ntfy on app role VMs
   - Deploy Homepage on app role VMs
   - Deploy personal-site on app role VMs (image-based, rolling zero-downtime style timer refresh, optional image cleanup)
   - Install and configure Unbound on dns role VMs
   - Install and configure AdGuard Home on dns role VMs
   - Install Node Exporter on all VMs
   - Install Prometheus on app role VMs
   - Install Grafana on app role VMs
   - Configure systemd-resolved on all VMs

4. homemanager
   - Install Nix on all VMs (bastion + internal)
   - Clone home-manager config
   - Apply Home Manager switch via flakes
```

## SSH Key for Internal VMs

The bastion generates a dedicated SSH key pair:
- Private: `~/.ssh/id_ed25519_internal`
- Public: `~/.ssh/id_ed25519_internal.pub`

This key is used exclusively for accessing internal VMs from bastion. Internal VMs are created with this public key during Terraform apply.

## Home Manager

All VMs receive:
- Nix package manager (multi-user daemon)
- Home Manager from: https://github.com/neodymium6/home-manager
- Configuration cloned to `~/.config/home-manager`

Home Manager is applied via: `nix run home-manager/master -- switch --flake ~/.config/home-manager`

## Accessing Internal VMs

From bastion:

```bash
ssh -i ~/.ssh/id_ed25519_internal youruser@192.168.1.101
```

The SSH config playbook sets up convenient aliases for internal hosts.

## Variables Override

The bastion Makefile uses these environment variables:

- `ANSIBLE_VENV_BIN`: Path to Ansible virtualenv (default: `$HOME/.venv/ansible/bin`)
- `ANSIBLE_PLAYBOOK`: Ansible playbook command (default: `$ANSIBLE_VENV_BIN/ansible-playbook`)
- `ANSIBLE_GALAXY`: Ansible galaxy command (default: `$ANSIBLE_VENV_BIN/ansible-galaxy`)
- `TERRAFORM`: Terraform command (default: `/usr/local/bin/terraform`)

These match the paths configured by local deployment.

## Cleanup

From bastion:

```bash
make clean
```

This destroys internal VMs and removes:
- Terraform state
- SSH keys (`~/.ssh/id_ed25519_internal*`)

For full cleanup (including bastion), run `make clean` from root directory on your local machine.
