# Bastion Deployment

Terraform and Ansible configurations executed on the bastion VM to create and configure internal VMs.

## Overview

1. **Terraform**: Creates internal VMs on Proxmox
2. **Ansible**: Configures bastion and internal VMs
   - Generates SSH key for internal access
   - Applies SSH hardening
   - Configures SSH client
3. **Ansible**: Installs Nix and Home Manager on all VMs

## Directory Structure

```
bastion/
├── terraform/               # Internal VMs infrastructure
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars    # Your credentials (git-ignored)
└── ansible/                 # Configuration management
    ├── site_bastion.yaml   # Bastion configuration
    ├── site_internal.yaml  # Internal VMs configuration
    ├── site_homemanager.yaml # Home Manager setup
    └── plays/
        ├── bastion/
        │   ├── generate_internal_key.yaml
        │   ├── ssh_hardening.yaml
        │   └── ssh_config.yaml
        ├── internal/
        │   └── ssh_hardening.yaml
        └── homemanager/
            └── apply_debian.yaml
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
| `make bastion-setup` | Configure bastion (SSH key, hardening, config) |
| `make internal-setup` | Configure internal VMs (SSH hardening) |
| `make homemanager` | Install Nix + Home Manager on all VMs |
| `make clean` | Destroy internal VMs |

## Deployment Workflow

```
1. bastion-setup (before VM creation)
   - Generate id_ed25519_internal SSH key pair

2. tf-apply
   - Create internal VMs with id_ed25519_internal.pub

3. internal-setup
   - Configure SSH hardening on internal VMs

4. homemanager
   - Install Nix on all VMs (bastion + internal)
   - Clone home-manager config
   - Apply Home Manager switch
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
- `TERRAFORM`: Terraform command (default: `$HOME/.local/bin/terraform`)

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
