"""Validate Samba declarations before changing accounts or configuration."""
import re
from pathlib import PurePosixPath


def name(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z_][a-z0-9_-]{0,63}", value)


def storage_samba_model(users, shares, login_user):
    if not name(login_user) or not isinstance(users, dict) or not isinstance(shares, dict):
        raise ValueError("Samba requires a login user and users/shares mappings")
    for user, options in users.items():
        if not name(user) or user == "root" or not isinstance(options, dict):
            raise ValueError("Invalid Samba user")
        if set(options) - {"unix_account"} or options.get("unix_account", "managed") not in ("managed", "existing"):
            raise ValueError("Invalid Samba unix_account policy")
    result = {}
    defaults = dict(read_only=False, browseable=False, force_user=login_user,
                    create_mask="0664", directory_mask="0775", encryption="required",
                    follow_symlinks=False, inherit_permissions=False)
    allowed = set(defaults) | {"path", "valid_users", "force_group", "force_directory_mode"}
    for share, options in shares.items():
        if not name(share) or share in ("global", "homes", "printers") or not isinstance(options, dict):
            raise ValueError("Invalid or reserved Samba share name")
        if set(options) - allowed:
            raise ValueError("Unknown Samba share option")
        config = defaults | options
        path = config.get("path", "")
        if (not isinstance(path, str) or not path.startswith("/") or path == "/"
                or any(c in path for c in "\r\n\x00%") or ".." in PurePosixPath(path).parts):
            raise ValueError("Samba share path must be a literal absolute directory")
        members = config.get("valid_users")
        if not isinstance(members, list) or not members or any(not isinstance(u, str) or u not in users for u in members):
            raise ValueError("Every share requires declared valid_users")
        for key in ("read_only", "browseable", "follow_symlinks", "inherit_permissions"):
            if not isinstance(config[key], bool):
                raise ValueError("Samba boolean options must be YAML booleans")
        for key in ("force_user", "force_group"):
            if key in config and not name(config[key]):
                raise ValueError("Invalid Samba forced account")
        for key in ("create_mask", "directory_mask", "force_directory_mode"):
            if key in config and (not isinstance(config[key], str) or not re.fullmatch(r"[0-7]{3,4}", config[key])):
                raise ValueError("Samba masks must be quoted octal strings")
        if config["encryption"] not in ("default", "required", "desired", "off"):
            raise ValueError("Invalid Samba encryption policy")
        result[share] = config
    return dict(users=users, shares=result)


class FilterModule:
    def filters(self):
        return {"storage_samba_model": storage_samba_model}
