# Tailscale

The role configures Tailscale membership and optional subnet/exit routing.
In `cluster.yaml`, set `tailscale.nodes.<host>.advertise_exit_node: true`
and `enable_ip_forward: true` to advertise an exit node. The default is false.
Existing `advertise_routes` can be retained alongside exit-node advertisement.
Keep subnet SNAT enabled when combining the two roles; see the
[Tailscale caveat](https://tailscale.com/docs/features/subnet-routers#disable-snat).

From the bastion's `homelab/bastion/ansible` directory, reconcile only Tailscale:

```sh
~/.venv/ansible/bin/ansible-playbook -i localhost, site_bastion.yaml --tags tailscale
```

The inventory-building play still runs; unrelated SSH-hardening/key-generation
tasks are excluded (automatic fact gathering may still run). This executes the Tailscale role, including package/service
and forwarding configuration. Do not run the repository-wide `make all` merely
to change exit-node advertisement.

Approve exit-node use for the device in the Tailscale admin console, unless an
applicable `autoApprovers.exitNode` policy already approves it. Grant intended
users access to `autogroup:internet`, and select the new exit node on a client.
Test internet/DNS and existing subnet access before retiring an older exit node.
Advertisement alone does not prove administrative approval or client use.

To withdraw advertisement, set `advertise_exit_node: false` and reconcile the
same play. Leave `enable_ip_forward: true` when subnet routing is still needed.
Existing full-flag convergence uses `tailscale up --reset`, so manage the setting
here instead of relying on a one-off manual command. The existing role's
`changed_when` only reports membership transitions, not every preference change;
verify the actual advertised routes after applying. Do not print authentication
keys or an unfiltered `tailscale debug prefs` result into logs.

Read-only regression checks:

```sh
python3 -m unittest discover -s tests
```
