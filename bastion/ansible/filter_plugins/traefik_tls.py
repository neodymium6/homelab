"""Validate opt-in certificate names independently of service routing."""
import ipaddress
import re


def homelab_tls_domains(names):
    if not isinstance(names, list):
        raise ValueError("proxy.additional_tls_domains must be a list")
    result = []
    for value in names:
        if not isinstance(value, str):
            raise ValueError("Additional TLS domains must be strings")
        name = value.lower()
        host = name[2:] if name.startswith("*.") else name
        labels = host.split(".")
        if (len(name) > 253 or len(labels) < 2 or
                any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                    for label in labels)):
            raise ValueError("TLS domains require an FQDN with optional leading '*.'")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("TLS domains must not be IP addresses")
        if name in result:
            raise ValueError("Duplicate additional TLS domain")
        result.append(name)
    return result


class FilterModule:
    def filters(self):
        return {"homelab_tls_domains": homelab_tls_domains}
