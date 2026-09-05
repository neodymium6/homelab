# Personal Site Role

Deploys a personal-site container image and keeps it updated with a systemd timer using rolling zero-downtime style updates.

## Purpose

- Create `/opt/stacks/personal-site`
- Run one container per backend port via Docker Compose
- Periodically run rolling updates (`pull` then one backend at a time with readiness checks)
- Optionally allow only proxy host access with UFW

## Defaults

- `personal_site_state`: `present` (`absent` retires this role's deployment)
- `personal_site_image`: `ghcr.io/neodymium6/profile.neodymium6.net:latest`
- `personal_site_backend_ports`: `[8080, 8081]`
- `personal_site_dir`: `/opt/stacks/personal-site`
- `personal_site_compose_path`: `/opt/stacks/personal-site/docker-compose.yml`
- `personal_site_update_enable`: `true`
- `personal_site_update_on_boot_sec`: `2m`
- `personal_site_update_unit_active_sec`: `1h`
- `personal_site_update_cleanup_enable`: `false`
- `personal_site_update_cleanup_until`: `168h`
- `personal_site_update_timeout_start_sec`: `10min`
- `personal_site_ready_path`: `/`
- `personal_site_ready_retries`: `300`
- `personal_site_ready_sleep_seconds`: `0.2`

## Firewall Behavior

- If `personal_site_enable_ufw: true` and `personal_site_allow_from_proxy_only: true`,
  only `personal_site_proxy_ip` is allowed to access all `personal_site_backend_ports`.

## Declarative Retirement

Set `state: absent` on the `personal-site` entry in the ignored `cluster.yaml`.
Keep `target_vm`, image, proxy hostnames, and backend ports: these identify the
cleanup target and retain the information needed to restore the deployment.
Do not simply delete the service entry; that only skips the application role.

The absent path stops the update timer and any running update first, then runs
Compose down for the dedicated `personal-site` project. It removes the two
update unit files, the managed Compose file, and the specified proxy UFW rules.
Images, volumes, other Compose projects, and user files such as a legacy `html/`
directory are preserved. Unexpected services, symlinked target paths, and
containers without a Compose configuration cause retirement to stop for review.
Only the default dedicated paths are supported for automatic retirement.

Shared Traefik, Homepage, and internal DNS generation omits absent services.
This is not a generic teardown implementation for other application roles.
Cloudflare remotely managed tunnel routes and public DNS are **not** managed
by this state; review and remove only the old hostname route separately, after
confirming that public DNS points to the replacement origin. Never delete a
shared tunnel or modify other hostname routes.

From the bastion's `bastion/ansible` directory, preview the scoped changes:

```sh
ansible-playbook -i localhost, site_internal.yaml --check \
  --tags personal-site,service-routing,homepage-links,service-dns
```

Review target hosts and changed tasks before removing `--check`. Avoid `--diff`
on production configuration: shared files can contain credentials. Unbound
reloads through its existing restart handler if internal DNS records change;
Traefik watches the mounted dynamic directory without restarting its container.
No shared Docker installation, image pruning, or other application rollout is
included in these tags. Repeat the command to verify no further changes.

For restoration, set `state: present` and apply the same tags. Restore the old
tunnel route only if required, verify the old origin, and only then consider
reverting public DNS. DNS reversal alone cannot restore a retired application.

Run the non-mutating regression tests with Python, PyYAML, and Jinja2 installed:

```sh
python3 -m unittest discover -s tests
```
