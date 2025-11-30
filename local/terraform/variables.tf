variable "proxmox_username" {
  type        = string
  description = "Proxmox username (e.g. root@pam)"
}

variable "proxmox_password" {
  type        = string
  description = "Proxmox password or API token secret"
  sensitive   = true
}

variable "debian_user_password" {
  type        = string
  description = "Initial password for login_user on Debian"
  sensitive   = true
}

variable "ssh_public_key_path" {
  type        = string
  description = "Local SSH public key for login_user on bastion"
}

