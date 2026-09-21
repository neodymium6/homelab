"""Validate additive address records without replacing generated VM names."""
import ipaddress
import re


def fqdn(value):
    if not isinstance(value, str):
        raise ValueError("DNS names must be strings")
    name = value.removesuffix(".").lower()
    labels = name.split(".")
    if (len(name) > 253 or len(labels) < 2 or
            any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels)):
        raise ValueError("DNS records require a literal fully qualified hostname")
    return name


def homelab_dns_records(config, domain, vms, services):
    if not isinstance(config, dict) or set(config) - {"records"}:
        raise ValueError("dns must be a mapping containing only records")
    records = config.get("records", [])
    if not isinstance(records, list):
        raise ValueError("dns.records must be a list")
    zone = fqdn(domain)
    generated = {fqdn(f"{name}.{zone}") for name in vms}
    generated.update(fqdn(f"{name}.{zone}") for name, svc in services.items()
                     if svc["target_vm"] in vms)
    result, seen = [], set()
    for record in records:
        if (not isinstance(record, dict) or set(record) - {"name", "type", "value", "ttl"}
                or not {"name", "type", "value"} <= set(record)):
            raise ValueError("DNS records require name, type, value and optional ttl")
        name = fqdn(record["name"])
        if name in generated or zone == name or zone.endswith("." + name):
            raise ValueError("Custom DNS must not replace generated names or their zone")
        kind = record["type"]
        if kind not in ("A", "AAAA"):
            raise ValueError("Only A and AAAA address records are supported")
        value = record["value"]
        if not isinstance(value, str) or "%" in value:
            raise ValueError("DNS value must be a literal unscoped IP address")
        address = ipaddress.ip_address(value)
        if address.version != {"A": 4, "AAAA": 6}[kind]:
            raise ValueError("DNS record type and IP family do not match")
        ttl = record.get("ttl", 300)
        if type(ttl) is not int or not 0 <= ttl <= 2147483647:
            raise ValueError("DNS ttl must be an integer between 0 and 2147483647")
        key = (name, kind, str(address))
        if key in seen:
            raise ValueError("Duplicate custom DNS record")
        if any(r["name"] == name and r["type"] == kind and r["ttl"] != ttl for r in result):
            raise ValueError("Records in one DNS RRset must have the same ttl")
        seen.add(key)
        result.append(dict(name=name, type=kind, value=str(address), ttl=ttl,
                           outside_zone=not name.endswith("." + zone)))
    return sorted(result, key=lambda r: (r["name"], r["type"], r["value"]))


class FilterModule:
    def filters(self):
        return {"homelab_dns_records": homelab_dns_records}
