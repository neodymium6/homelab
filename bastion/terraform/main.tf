terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.87.0"
    }
  }
  required_version = ">= 1.5.0"
}

locals {
  cluster    = yamldecode(file("${path.module}/../../cluster.yaml"))
  login_user = local.cluster.login_user
  storage    = try(local.cluster.storage, {})

  internal_vms = {
    for name, vm in local.cluster.vms :
    name => vm
    if vm.role != "bastion"
  }

  storage_vms = {
    for name, vm in local.internal_vms :
    name => vm
    if vm.role == "storage"
  }

  bastion_internal_pub_path = "/home/${local.login_user}/.ssh/id_ed25519_internal.pub"
  storage_data_disk         = try(local.storage.data_disk, null)
}

provider "proxmox" {
  endpoint = local.cluster.proxmox.endpoint
  username = var.proxmox_username
  password = var.proxmox_password
  insecure = true
}

resource "proxmox_virtual_environment_vm" "internal" {
  for_each = local.internal_vms

  vm_id       = each.value.vmid
  name        = each.key
  node_name   = local.cluster.proxmox.node_name
  description = "Homelab internal VM (managed from bastion)"

  clone {
    vm_id = local.cluster.proxmox.debian_template_vmid
  }

  cpu {
    cores   = lookup(each.value, "cpu_cores", 2)
    sockets = 1
    type    = "x86-64-v2-AES"
  }

  memory {
    dedicated = lookup(each.value, "memory_mb", 2048)
  }

  network_device {
    bridge = "vmbr0"
  }

  disk {
    datastore_id = local.cluster.proxmox.datastore
    interface    = "scsi0"
    size         = 20
  }

  dynamic "disk" {
    for_each = each.value.role == "storage" && local.storage_data_disk != null ? [local.storage_data_disk] : []

    content {
      datastore_id = lookup(disk.value, "datastore_id", local.cluster.proxmox.datastore)
      interface    = lookup(disk.value, "interface", "scsi1")
      size         = lookup(disk.value, "size_gb", 100)
      file_format  = lookup(disk.value, "file_format", "raw")
    }
  }

  dynamic "usb" {
    for_each = coalesce(try(each.value.usb_devices, null), [])

    content {
      host    = try(trimspace(usb.value.host), null)
      mapping = try(trimspace(usb.value.mapping), null)
      usb3    = coalesce(try(usb.value.usb3, null), false)
    }
  }

  initialization {
    datastore_id = local.cluster.proxmox.datastore

    user_account {
      username = local.login_user
      password = var.debian_user_password

      keys = [file(local.bastion_internal_pub_path)]
    }

    ip_config {
      ipv4 {
        address = format(
          "%s.%d/%d",
          local.cluster.network.base_prefix,
          each.value.vmid,
          local.cluster.network.cidr_suffix
        )
        gateway = local.cluster.network.gateway_v4
      }
    }

    dns {
      servers = local.cluster.network.upstream_dns
    }
  }

  agent {
    enabled = true
  }

  lifecycle {
    ignore_changes = [started]

    precondition {
      condition     = length(local.storage_vms) <= 1
      error_message = "Only one VM with role 'storage' is supported."
    }

    precondition {
      condition     = local.storage_data_disk == null || length(local.storage_vms) == 1
      error_message = "storage.data_disk requires exactly one VM with role 'storage'."
    }

    precondition {
      condition = alltrue([
        for usb_device in coalesce(try(each.value.usb_devices, null), []) :
        length(compact([
          try(trimspace(usb_device.host), ""),
          try(trimspace(usb_device.mapping), ""),
        ])) == 1
      ])
      error_message = "Each vm.usb_devices entry must define exactly one of 'host' or 'mapping'."
    }
  }
}
