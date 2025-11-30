variable "proxmox_username" {
  type        = string
  description = "Proxmox username"
}

variable "proxmox_password" {
  type        = string
  description = "Proxmox password or token"
  sensitive   = true
}

variable "debian_user_password" {
  type        = string
  description = "Initial password for login_user on internal hosts"
  sensitive   = true
}

