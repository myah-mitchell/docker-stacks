# ci01 bootstrap runbook

ci01 is the first VM deployed by Komodo rather than built by hand. It is the first real use of the pattern every host after it follows, so read it as a template even when the host you are building is not ci01.

ci01 carries two stacks. `stacks/semaphore-server` goes first on purpose: once it is up and wired to the ansible repo, it becomes the way real shared secrets reach every other server, instead of being fixed by hand host by host.

`stacks/victoriametrics-server` follows. It is the metrics, logs, and traces backend every VM after this one writes to, which is why ci01 sits second in the running order rather than later.

Steps 1 to 8 provision the VM and are the template the later host runbooks reuse. Steps 9 and 10 hand off to a doc each, because both stacks need more than a Komodo Stack resource to be useful.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Clone the template into a VM](#1-clone-the-template-into-a-vm)
- [2. Size and network the VM](#2-size-and-network-the-vm)
- [3. Start the VM](#3-start-the-vm)
- [4. Verify base provisioning](#4-verify-base-provisioning)
- [5. Give ci01 an onboarding key](#5-give-ci01-an-onboarding-key)
- [6. Create the proxy Docker network](#6-create-the-proxy-docker-network)
- [7. Confirm ci01 shows as a Komodo Server](#7-confirm-ci01-shows-as-a-komodo-server)
- [8. Deploy traefik-bootstrap onto ci01](#8-deploy-traefik-bootstrap-onto-ci01)
- [9. Deploy Semaphore](#9-deploy-semaphore)
- [10. Deploy the VictoriaMetrics backend](#10-deploy-the-victoriametrics-backend)
- [What's next](#whats-next)

## Prerequisites

- km01 is finished, through step 14 of [km01 bootstrap](komodo-bootstrap.md). Its four containers are healthy, its admin account exists, its firewall allows inbound 9120, and its global `[[GLOBAL_...]]` Variables are created. Step 3 of [Semaphore setup](semaphore-setup.md) fails without those Variables.
- The real Komodo Core address and public key are committed and pushed in ansible-private's `group_vars/all/private.yml`. That is step 13 of the km01 runbook, and ci01 reads both at first boot.
- The `ubuntu-server-2604` cloud-init template exists on the target PVE host, the same one km01 was cloned from.
- You can open Komodo's UI when you reach step 5. The onboarding key is single-use and short-lived, so there is nothing to prepare ahead of time.

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<template-vmid>` | VMID of the cloud-init template, the same one km01 used |
| `<ci-vmid>` | VMID to give the new VM |
| `<ci-ip>` | Static address for ci01 |
| `<gateway-ip>` | Gateway for that subnet |
| `<km-ip>` | km01's address, from its own runbook |
| `<cephfs>` | Name of the PVE CephFS storage holding the snippets, if that host keeps them there |
| `<same>` | The value cloud-init already used, recovered in step 5 rather than guessed |
| `<ansible-private-url>` | Clone URL for ansible-private, from the ansible repo's README |
| `<internal-subnet>` | The internal VLAN's CIDR, the one every fleet VM sits on |

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <ci-vmid> --name ci01 --full
```

## 2. Size and network the VM

Size for both stacks now rather than resizing later. Semaphore, Postgres, and postgres-backup are light on their own, but `stacks/victoriametrics-server` adds twelve more services, including Grafana and three VictoriaMetrics databases.

```bash
qm set <ci-vmid> --cores 4 --memory 8192
qm set <ci-vmid> --ipconfig0 ip=<ci-ip>/24,gw=<gateway-ip>
```

Four cores and 8 GB is a floor rather than a target. Metrics and log retention both grow on disk, so watch `/opt/docker/volumes/victoriametrics` once it exists.

Confirm the template's VLAN tag is the internal-only one. ci01 is not in the DMZ.

## 3. Start the VM

```bash
qm start <ci-vmid>
```

Cloud-init provisions the host on first boot the same way km01 was, installing Docker, the firewall, NTP, swap, node_exporter, and Komodo Periphery with no manual step. See [what the vendor snippet does](komodo-bootstrap.md#what-the-vendor-snippet-does) if you need the internals.

In the PVE web UI, expand *Datacenter* to ci01 and open its *Console*. There is no account to SSH in as until cloud-init creates one.

## 4. Verify base provisioning

SSH in once cloud-init finishes:

```bash
docker version
systemctl status ufw
sudo -u komodo XDG_RUNTIME_DIR=/run/user/$(id -u komodo) systemctl --user status periphery.service
```

All three should be up and running.

The last command needs that exact shape. Periphery runs as a `--user` systemd service under a dedicated `komodo` OS account, so a plain `systemctl status periphery` from your own login finds nothing. Ansible's docker role is what creates that account.

## 5. Give ci01 an onboarding key

This is the one manual step, and it is permanent. Every future host needs its own fresh onboarding key at provision time, the same way every new host needs its own SSH host key accepted.

The ansible repo ships `komodo_onboarding_key` blank in the docker role's defaults, because a real value is single-use and must never be committed. Periphery needs one to make its first outbound connection to Core. After that, Core and ci01 trust each other by their own Ed25519 keypairs and the onboarding key is discarded.

In Komodo's UI on km01, at `http://<km-ip>:9120`, go to *Settings > Onboarding* and click **New Onboarding Key**.

### Recover the original provisioning arguments

The re-run below has to pass the same four identity values cloud-init used the first time. Read them off the VM rather than guessing:

```bash
sudo grep -o "\-e '{[^']*}'" /var/lib/cloud/instance/scripts/runcmd
```

If that file is gone, the same values are in the vendor snippet on the PVE host, at `/mnt/pve/<cephfs>/snippets/cloudinit-vendor.yml` or `/var/lib/vz/snippets/cloudinit-vendor.yml`.

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

On ci01:

```bash
sudo -u komodo grep -A1 'core_address\|connect_as' /home/komodo/.config/komodo/periphery.config.toml
```

## 6. Create the proxy Docker network

```bash
docker network create proxy
```

Same one-time-per-host step as km01's step 9. Nothing creates this network, and every deployable stack's `compose.yaml` declares it `external: true`.

## 7. Confirm ci01 shows as a Komodo Server

Step 5's onboarding key created the ci01 Server resource the moment Periphery made its first outbound connection. There is nothing to add by hand.

In Komodo's UI on km01, check *Resources > Servers* and confirm ci01 shows connected and healthy before continuing. Re-check step 5 if it is not listed at all.

## 8. Deploy traefik-bootstrap onto ci01

`stacks/semaphore-server` publishes no port directly, and its Traefik labels are gated behind `chain-authentik@file`. Neither Traefik nor Authentik exists anywhere in the plan yet, so without this step there is no way to reach Semaphore's UI once it deploys.

`stacks/traefik-bootstrap` is a real Traefik with self-signed TLS and `chain-no-auth@file` in place of a cert resolver and Authentik. See [Traefik bootstrap](traefik-bootstrap.md) for what it does and when it gets torn down.

Create its runtime folders first, following [step 1 of Traefik bootstrap](traefik-bootstrap.md#1-create-the-runtime-folders).

Then follow [How to deploy it](traefik-bootstrap.md#how-to-deploy-it) for the Stack resource itself. Set its target *Server* to **ci01**. Set `SERVER_NAME` to `ci01`. Use the same `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you will use for every stack on this host.

Confirm all five services show running and healthy before continuing:

```text
traefik
error-pages
socket-proxy
socket-proxy-rw
logrotate
```

## 9. Deploy Semaphore

Semaphore goes first on purpose. Once it is up and wired to the ansible repo, it becomes the way real shared secrets reach every other server, instead of being fixed by hand host by host.

Follow [Semaphore setup](semaphore-setup.md), fourteen steps covering `stacks/semaphore-server` from its runtime folders to a Template that runs against the fleet.

Only its last step can be left: replacing the bootstrap SSH key waits on pk01. Everything before it should be done before the next step here, because step 13 there is what replaces the committed `CHANGEME` node_exporter password.

## 10. Deploy the VictoriaMetrics backend

`stacks/victoriametrics-server` is the fleet's metrics, logs, and traces backend, and it lands on ci01 alongside Semaphore. Every VM after this one runs vmagent, vlagent, and vector as sidecars in its traefik stack, all pointed here, so building it now is what lets those hosts ship from their first deploy.

Follow [VictoriaMetrics setup](victoriametrics-setup.md), which is seven steps from host prep to Grafana.

## What's next

ci01 is finished once both linked docs are, apart from [step 14 of Semaphore setup](semaphore-setup.md#14-replace-this-key-once-step-ca-is-live), which waits on pk01.

tf01 is the next VM. See [Running order](README.md#running-order), and [How the host runbooks are shaped](README.md#how-the-host-runbooks-are-shaped) for which parts of this runbook the later ones reuse.
