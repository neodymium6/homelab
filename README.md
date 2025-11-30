# Homelab Infrastructure

Infrastructure as Code for managing a Proxmox-based homelab environment with bastion host architecture.

## Overview

This project automates the deployment and configuration of VMs on Proxmox VE using Terraform and Ansible. It implements a secure bastion host pattern where:

- **Local machine**: Creates and bootstraps the bastion VM
- **Bastion host**: Acts as a jump server and infrastructure controller for internal VMs
- **Internal VMs**: Managed exclusively from the bastion host

All VMs are configured with Nix and Home Manager for declarative system configuration.

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
            ┌─────────────────┐
            │ Internal VMs    │
            │ - Home Manager  │
            └─────────────────┘
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
  dns:
    - "8.8.8.8"

login_user: "youruser"

vms:
  bastion-01:
    vmid: 100
    role: "bastion"
    cpu_cores: 2
    memory_mb: 2048

  internal-01:
    vmid: 101
    role: "internal"
    cpu_cores: 2
    memory_mb: 2048
```

VMs are assigned IPs based on their VMID: `<base_prefix>.<vmid>/<cidr_suffix>`

Example: VMID 100 → 192.168.1.100/24

## Deployment Workflow

```
┌────────────────────────────────────────────────────┐
│ Local Machine: make all                            │
├────────────────────────────────────────────────────┤
│ 1. terraform: Create bastion VM                    │
│ 2. ansible: Bootstrap bastion                      │
│    - Install Terraform, Ansible                    │
│    - Clone homelab repo                            │
│    - Copy credentials                              │
└────────────┬───────────────────────────────────────┘
             │ SSH to bastion
             ▼
┌────────────────────────────────────────────────────┐
│ Bastion VM: make all                               │
├────────────────────────────────────────────────────┤
│ 1. terraform: Create internal VMs                  │
│ 2. ansible: Configure bastion                      │
│    - Generate SSH keys for internal access         │
│    - SSH hardening                                 │
│    - SSH config                                    │
│ 3. ansible: Configure internal VMs                 │
│    - SSH hardening                                 │
│ 4. ansible: Install Home Manager on all VMs        │
│    - Install Nix                                   │
│    - Clone home-manager config                     │
│    - Apply Home Manager switch                     │
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

- **SSH Hardening**: Password authentication disabled, key-only access
- **Dedicated Keys**: Separate SSH key (`id_ed25519_internal`) for internal VM access
- **Bastion Pattern**: Internal VMs not directly accessible from outside
- **Git Ignored Secrets**: All sensitive files (`.tfvars`, keys) excluded from git

## Home Manager Integration

All VMs receive Nix and Home Manager for declarative system configuration. The Home Manager configuration is maintained in a separate repository and cloned to `~/.config/home-manager` on each VM.

Repository: [neodymium6/home-manager](https://github.com/neodymium6/home-manager)

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
