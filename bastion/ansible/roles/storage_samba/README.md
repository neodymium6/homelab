# Samba shares

Declare `storage.samba.users` and `storage.samba.shares` as mappings, with
passwords in the ignored `secrets.storage.samba_passwords` mapping. See the
root example. One storage VM and one ext4 data disk remain the storage model.

Users default to non-login Unix accounts; `unix_account: existing` requires an
existing account. Existing Unix attributes and Samba passwords are preserved.
A password is required for a new Samba account, or when explicitly setting
`storage_samba_update_password: true`. Imported Samba accounts can be retained
without their plaintext password, but need a separately protected passdb
backup for disaster recovery. Removing a declaration never deletes an account
or its data; account revocation is a separate explicit operation.

Shares require a literal absolute `path` and a nonempty `valid_users` list of
declared users. Defaults are writable, not browseable, SMB encryption required,
symlinks disabled, file mask `0664`, directory mask `0775`, and Unix writes as
`login_user`. Optional `force_group`, `force_directory_mode`,
`inherit_permissions`, `read_only`, `browseable`, `encryption` and
`follow_symlinks` override those defaults. Quote octal masks. Existing directory
ownership and permissions are not changed; missing share directories are
created. Provision and mount backing storage before applying shares.

The legacy `share_name` / `user` and scalar `samba_password` configuration is
still supported with its original sharing policy. Do not mix the two schemas.
Configuration is validated with `testparm` and reloaded, not restarted. Removing
a share removes its declaration; existing SMB connections may retain access
until disconnected. Consumers and mount changes belong to their own repos.

For a scoped server-only apply on the bastion:

```sh
cd ~/homelab/bastion/ansible
ansible-playbook -i localhost, site_internal.yaml --tags storage-samba
```
