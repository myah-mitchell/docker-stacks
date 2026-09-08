# Provisioning a VM

Every VM in the fleet except km01 is provisioned this way: cloned from the cloud-init template, given one onboarding key by hand, and left to join Komodo on its own. km01 is the exception because it is the Komodo Core that the rest of this depends on, and it was built before any of this existed.

Nothing here is host-specific. Each host's own runbook supplies the values in [Placeholders](#placeholders) and any caveat particular to it, then sends you here.

This ends when the host shows connected and healthy under *Resources > Servers*. Everything after that is that host's own stacks.

Read [Conventions](conventions.md) first. This doc assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Clone the template into a VM](#1-clone-the-template-into-a-vm)
- [2. Size and network the VM](#2-size-and-network-the-vm)
- [3. Start the VM](#3-start-the-vm)
- [4. Verify base provisioning](#4-verify-base-provisioning)
- [5. Give the host an onboarding key](#5-give-the-host-an-onboarding-key)
- [6. Create the proxy Docker network](#6-create-the-proxy-docker-network)
- [7. Confirm the host shows as a Komodo Server](#7-confirm-the-host-shows-as-a-komodo-server)
- [What's next](#whats-next)

## Prerequisites

- km01 is finished, through step 14 of [km01 bootstrap](komodo-bootstrap.md). Its four containers are healthy, its admin account exists, its firewall allows inbound 9120, and its global `[[GLOBAL_...]]` Variables are created.
- The real Komodo Core address and public key are committed and pushed in ansible-private's `group_vars/all/private.yml`. That is step 13 of the km01 runbook, and the new host reads both at first boot.
- The `ubuntu-server-2604` cloud-init template exists on the target PVE host, the same one km01 was cloned from.
- You can open Komodo's UI when you reach step 5. The onboarding key is single-use and short-lived, so there is nothing to prepare ahead of time.

## Placeholders

The first five come from the host's own runbook. The rest are the same for every host.

| Placeholder | Value |
| --- | --- |
| `<host>` | The hostname being built, for example `ci01` |
| `<vmid>` | VMID to give the new VM |
| `<ip>` | Static address for it |
| `<cores>` | Core count, sized for the stacks that host carries |
| `<memory>` | Memory in MB, sized the same way |
| `<template-vmid>` | VMID of the cloud-init template, the same one km01 used |
| `<gateway-ip>` | Gateway for that subnet |
| `<km-ip>` | km01's address, from its own runbook |
| `<same>` | The value cloud-init already used, recovered in step 5 rather than guessed |
| `<ansible-private-url>` | Clone URL for ansible-private, from the ansible repo's README |

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <vmid> --name <host> --full
```

## 2. Size and network the VM

```bash
qm set <vmid> --cores <cores> --memory <memory>
qm set <vmid> --ipconfig0 ip=<ip>/24,gw=<gateway-ip>
```

Size for every stack the host will end up carrying, rather than resizing later. Each host's runbook gives the numbers and says what drives them.

Confirm the VLAN tag the template carries is the one that host belongs on. Every VM in the running order is internal-only except bh01, which is the DMZ edge.

## 3. Start the VM

```bash
qm start <vmid>
```

Cloud-init provisions the host on first boot the same way km01 was, installing Docker, the firewall, NTP, swap, node_exporter, and Komodo Periphery with no manual step. See [what the vendor snippet does](komodo-bootstrap.md#what-the-vendor-snippet-does) if you need the internals.

In the PVE web UI, expand *Datacenter* to the new VM and open its *Console*. There is no account to SSH in as until cloud-init creates one.

## 4. Verify base provisioning

SSH in once cloud-init finishes:

```bash
docker version
systemctl status ufw
sudo -u komodo XDG_RUNTIME_DIR=/run/user/$(id -u komodo) systemctl --user status periphery.service
```

All three should be up and running.

The last command needs that exact shape. Periphery runs as a `--user` systemd service under a dedicated `komodo` OS account, so a plain `systemctl status periphery` from your own login finds nothing. Ansible's docker role is what creates that account.

## 5. Give the host an onboarding key

This is the one manual step, and it is permanent. Every future host needs its own fresh onboarding key at provision time, the same way every new host needs its own SSH host key accepted.

The ansible repo ships `komodo_onboarding_key` blank in the docker role's defaults, because a real value is single-use and must never be committed. Periphery needs one to make its first outbound connection to Core. After that, Core and the new host trust each other by their own Ed25519 keypairs and the onboarding key is discarded.

In Komodo's UI on km01, at `http://<km-ip>:9120`, go to *Settings > Onboarding* and click **New Onboarding Key**.

### Recover the original provisioning arguments

The re-run below has to pass the same four identity values cloud-init used the first time. Read them off the VM rather than guessing:

```bash
sudo grep -o "\-e '{[^']*}'" /var/lib/cloud/instance/scripts/runcmd
```

If that file is gone, the same values are in the vendor snippet on the PVE host, at `/var/lib/vz/snippets/cloudinit-vendor.yml`. Snippets live on the `local` storage.

### Re-run provisioning with the key

```bash
cd /tmp/ansible
ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' \
  -e '{"komodo_onboarding_key":"<the key you just generated>"}' \
  --tags docker
```

The `--tags docker` scoping keeps this from repeating the whole provisioning run.

`/tmp/ansible` is still the checkout cloud-init made in step 3, with the private overlay's real `hosts.yml` and `group_vars/all/private.yml` already copied in. Re-run in place.

> [!WARNING]
> Do not `git pull` that checkout first. Those two files are locally modified relative to git, because the overlay copies over them rather than committing. Pulling either refuses outright or silently reverts them to the public repo's sanitised placeholders.

If `/tmp/ansible` really is gone, re-clone the public repo and re-apply the overlay before provisioning:

```bash
git clone https://github.com/myah-mitchell/ansible /tmp/ansible
cd /tmp/ansible && ./scripts/bootstrap-private.sh <ansible-private-url>
```

Get that URL from the [ansible repo's README](https://github.com/myah-mitchell/ansible). Never paste a credentialed clone URL into docker-stacks, which is public.

### Confirm it connected

On the new host:

```bash
sudo -u komodo grep -A1 'core_address\|connect_as' /home/komodo/.config/komodo/periphery.config.toml
```

## 6. Create the proxy Docker network

```bash
docker network create proxy
```

Same one-time-per-host step as km01's step 9. Nothing creates this network, and every deployable stack's `compose.yaml` declares it `external: true`.

## 7. Confirm the host shows as a Komodo Server

Step 5's onboarding key created the Server resource the moment Periphery made its first outbound connection. There is nothing to add by hand.

In Komodo's UI on km01, check *Resources > Servers* and confirm the host shows connected and healthy before continuing. Re-check step 5 if it is not listed at all.

## What's next

Go back to the host's own runbook. What comes next is that host's stacks, which is the part no two hosts share.
