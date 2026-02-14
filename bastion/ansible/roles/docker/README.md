# Docker Role

Ansible role for installing Docker and Docker Compose v2 plugin on Debian-based systems.

## Overview

This role:
- Installs Docker, Docker Compose v2 plugin, and Python Docker SDK from Debian packages
- Enables and starts the Docker service
- Optionally adds users to the docker group for non-root Docker access

## Requirements

- Debian-based system (tested on Debian 12)

## Role Variables

### Defaults (defaults/main.yml)

| Variable | Default | Description |
|----------|---------|-------------|
| `docker_packages` | `[docker.io, docker-compose, python3-docker]` | Docker packages to install |
| `docker_users` | `[]` | List of users to add to docker group |

### Example Configuration

```yaml
docker_users:
  - "{{ login_user }}"
```

## Example Playbook

```yaml
- name: Install Docker on app hosts
  hosts: app
  become: true
  vars_files:
    - ../../cluster.yaml
  roles:
    - role: docker
      docker_users:
        - "{{ login_user }}"
```

## Usage

After applying this role, users in `docker_users` will need to log out and back in for group membership to take effect, or use `newgrp docker`.

## Dependencies

None. All functionality is self-contained.

## License

MIT

## Author

neodymium6
