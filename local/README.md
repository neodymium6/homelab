# Local Deployment

Terraform and Ansible configurations for creating and bootstrapping the bastion VM from your local machine.

## Overview

1. **Terraform**: Creates bastion VM on Proxmox
2. **Ansible**: Bootstraps bastion with Terraform, Ansible, and homelab repository

## Directory Structure

```
local/
├── terraform/               # Bastion VM infrastructure
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars    # Your credentials (git-ignored)
└── ansible/                 # Bastion bootstrap
    ├── site_local.yaml
    └── plays/
```

## Configuration

### terraform.tfvars

Create `local/terraform/terraform.tfvars`:

```hcl
proxmox_username       = "root@pam"
proxmox_password       = "your_proxmox_password"
ssh_public_key_path    = "~/.ssh/id_ed25519.pub"
debian_user_password   = "your_vm_password"
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make all` | Full deployment (init → apply → bootstrap) |
| `make bastion-tf-init` | Initialize Terraform |
| `make bastion-tf-apply` | Create bastion VM |
| `make bastion-bootstrap` | Bootstrap bastion with Ansible |
| `make debug GIT_BRANCH=<branch>` | Deploy with custom git branch |
| `make clean` | Destroy bastion VM |

## What Gets Installed on Bastion

- Terraform 1.8.5 (`~/.local/bin/terraform`)
- Ansible (`~/.venv/ansible`)
- Homelab repository (`~/homelab`)
- Configuration files (`cluster.yaml`, `terraform.tfvars`)

## Next Steps

After deployment, proceed with bastion deployment from root directory:

```bash
make bastion
```

See [../bastion/README.md](../bastion/README.md) for details.
