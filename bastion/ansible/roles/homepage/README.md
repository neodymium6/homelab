# Homepage Role

Ansible role for deploying Homepage dashboard via Docker Compose on app VMs.

## Overview

This role:
- Creates directory structure for Homepage in `/opt/stacks/homepage`
- Deploys Homepage via Docker Compose
- Generates Homepage configuration files (settings, services, bookmarks, widgets)
- Configures UFW to allow access only from proxy-01
- Exposes Homepage on port 3000 for Traefik proxying

## Requirements

- Debian-based system (tested on Debian 12)
- Docker and Docker Compose installed (via docker role)
- `cluster.yaml` with network and VM configuration

## Role Variables

### Defaults (defaults/main.yaml)

| Variable | Default | Description |
|----------|---------|-------------|
| `homepage_image` | `ghcr.io/gethomepage/homepage:latest` | Homepage Docker image |
| `homepage_dir` | `/opt/stacks/homepage` | Homepage installation directory |
| `homepage_config_dir` | `{{ homepage_dir }}/config` | Configuration directory |
| `homepage_compose_path` | `{{ homepage_dir }}/docker-compose.yml` | Docker Compose file path |
| `homepage_port` | `3000` | Port to expose Homepage on |
| `homepage_enable_ufw` | `true` | Enable UFW firewall rules |
| `homepage_allow_from_proxy_only` | `true` | Restrict access to proxy-01 only |

### Required Variables (from playbook)

```yaml
homepage_proxy_ip: "{{ network.base_prefix }}.{{ vms['proxy-01'].vmid }}"
```

## Example Playbook

```yaml
- name: Deploy Homepage on app hosts
  hosts: app
  become: true
  gather_facts: false

  vars_files:
    - ../../cluster.yaml

  vars:
    homepage_proxy_ip: "{{ network.base_prefix }}.{{ vms['proxy-01'].vmid }}"

  roles:
    - role: homepage
```

## Configuration Files

The role deploys the following configuration files:

- **settings.yaml**: Basic Homepage settings (title, etc.)
- **services.yaml**: Service links (Traefik, AdGuard Home)
- **bookmarks.yaml**: Bookmarks (empty by default)
- **widgets.yaml**: Resource monitoring widgets (CPU, memory, disk)

## Firewall Configuration

When `homepage_enable_ufw` and `homepage_allow_from_proxy_only` are both true:
- UFW rule allows TCP traffic on port 3000 only from proxy-01's IP
- Direct client access to app-01:3000 is blocked
- Access must go through Traefik reverse proxy

## Accessing Homepage

Homepage is accessible via Traefik at:
```
https://homepage-proxy.{{ network.domain }}
```

## Handlers

### Restart homepage

Triggered when configuration files change. Restarts the Homepage container via Docker Compose.

## Dependencies

- Docker and Docker Compose must be installed (typically via the docker role)

## License

MIT

## Author

neodymium6
