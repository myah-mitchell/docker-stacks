# ci01 bootstrap runbook

ci01 is the first VM deployed by Komodo rather than built by hand. It is the first real use of the pattern every host after it follows, so read it as a template even when the host you are building is not ci01.

Its first stack is `stacks/semaphore-server`. Semaphore goes first on purpose: once it is up and wired to the ansible repo, it becomes the way real shared secrets reach every other server, instead of being fixed by hand host by host.

This runbook ends when Semaphore's UI loads. Wiring Semaphore to ansible is a separate job, in [Semaphore setup](semaphore-setup.md).

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Clone the template into a VM](#1-clone-the-template-into-a-vm)
- [2. Size and network the VM](#2-size-and-network-the-vm)
- [3. Start the VM](#3-start-the-vm)
- [4. Verify base provisioning](#4-verify-base-provisioning)
- [5. Give ci01 an onboarding key](#5-give-ci01-an-onboarding-key)
- [6. Create the runtime folders](#6-create-the-runtime-folders)
- [7. Create the proxy Docker network](#7-create-the-proxy-docker-network)
- [8. Confirm ci01 shows as a Komodo Server](#8-confirm-ci01-shows-as-a-komodo-server)
- [9. Deploy traefik-bootstrap onto ci01](#9-deploy-traefik-bootstrap-onto-ci01)
- [10. Generate Semaphore's three encryption keys](#10-generate-semaphores-three-encryption-keys)
- [11. Create the Stack resource for semaphore-server](#11-create-the-stack-resource-for-semaphore-server)
- [12. Verify](#12-verify)
- [13. First access](#13-first-access)
- [What still lands on ci01](#what-still-lands-on-ci01)
- [What's next](#whats-next)

## Prerequisites

- km01 is finished, through step 14 of [km01 bootstrap](komodo-bootstrap.md). Its four containers are healthy, its admin account exists, its firewall allows inbound 9120, and its global `[[GLOBAL_...]]` Variables are created. Step 11 below fails without those Variables.
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

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <ci-vmid> --name ci01 --full
```

## 2. Size and network the VM

Semaphore, Postgres, and postgres-backup are light, so resize down from the template's generic defaults the same way km01 was:

```bash
qm set <ci-vmid> --cores 2 --memory 4096
qm set <ci-vmid> --ipconfig0 ip=<ci-ip>/24,gw=<gateway-ip>
```

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

## 6. Create the runtime folders

```bash
projectName="semaphore"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/semaphore-data
mkdir -p /opt/docker/volumes/$projectName/semaphore-config
mkdir -p /opt/docker/volumes/$projectName/semaphore-tmp
sudo chown 101000:101000 /opt/docker/volumes/$projectName/semaphore-*

mkdir -p /opt/docker/volumes/$projectName/postgres-data
mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*
```

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

Unlike km01, you do not clone docker-stacks onto ci01 yourself. Periphery clones it into `/opt/docker/repos/` once you point a Stack resource at it in step 11. The folders above still have to exist with the right ownership before that first deploy, because neither Periphery nor Compose creates host bind-mount directories.

This list mirrors the [generated README for semaphore-server](../stacks/semaphore-server/README.md), which `scripts/build.py` rebuilds. That file wins if the two disagree.

## 7. Create the proxy Docker network

```bash
docker network create proxy
```

Same one-time-per-host step as km01's step 9. Nothing creates this network, and every deployable stack's `compose.yaml` declares it `external: true`.

## 8. Confirm ci01 shows as a Komodo Server

Step 5's onboarding key created the ci01 Server resource the moment Periphery made its first outbound connection. There is nothing to add by hand.

In Komodo's UI on km01, check *Resources > Servers* and confirm ci01 shows connected and healthy before continuing. Re-check step 5 if it is not listed at all.

## 9. Deploy traefik-bootstrap onto ci01

`stacks/semaphore-server` publishes no port directly, and its Traefik labels are gated behind `chain-authentik@file`. Neither Traefik nor Authentik exists anywhere in the plan yet, so without this step there is no way to reach Semaphore's UI once it deploys.

`stacks/traefik-bootstrap` is a real Traefik with self-signed TLS and `chain-no-auth@file` in place of a cert resolver and Authentik. See [Traefik bootstrap](traefik-bootstrap.md) for what it does and when it gets torn down.

Create its runtime folders first, following [step 1 of Traefik bootstrap](traefik-bootstrap.md#1-create-the-runtime-folders).

Then follow [How to deploy it](traefik-bootstrap.md#how-to-deploy-it) for the Stack resource itself. Set its target *Server* to **ci01**. Set `SERVER_NAME` to `ci01`. Use the same `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you will use in step 11.

Confirm all five services show running and healthy before continuing:

```text
traefik
error-pages
socket-proxy
socket-proxy-rw
logrotate
```

## 10. Generate Semaphore's three encryption keys

Three of Semaphore's values are base64-encoded 32-byte keys rather than plain passwords, so `scripts/build.py` deliberately does not generate them. Generate them once, now:

```bash
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_HASH
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_ENCRYPTION
head -c32 /dev/urandom | base64  # SEMAPHORE_ACCESS_KEY_ENCRYPTION
```

> [!IMPORTANT]
> These three must stay stable across restarts. Rotating any of them invalidates every stored SSH key, every stored vault secret, and every active session.

They go into Komodo Secrets in step 11, not into any file in this repo.

## 11. Create the Stack resource for semaphore-server

In Komodo's UI, go to *Resources > Stacks* and create a new Stack named `semaphore-server`. Set its target *Server* to **ci01**, the resource from step 8.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/semaphore-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/semaphore-server/komodo.env` in this repo, copy its full contents, and paste them into that field.

Four keys in the pasted text need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |
| `TRAEFIK_AUTH_CHAIN` | `chain-no-auth@file`, so it routes through traefik-bootstrap |

Authentik does not exist yet, so the real `chain-authentik@file` default has nothing behind it. Clear that override later, once id01 is live and system-agent has replaced traefik-bootstrap here.

Three more keys are blank and stay that way: `POSTGRES_BACKUP_DB`, `POSTGRES_BACKUP_USER`, and `POSTGRES_BACKUP_PASSWORD`. This stack's `compose.yaml` points all three at the same database, user, and password its own Postgres service already resolves.

Leave every `[[...]]` reference in the pasted text exactly as it is. Komodo resolves them at deploy time from its own Variables and Secrets, which is the next step.

### Create the nine Semaphore Secrets

The `[[GLOBAL_...]]` references already resolve, from km01's step 14. The `[[SEMAPHORE_...]]` ones do not exist yet.

Go to *Settings > Secrets* on km01 and create all nine by name. These are real credentials, so Secrets rather than Variables: Komodo resolves both identically, but Secrets stay masked in the UI.

| Secret | Value |
| --- | --- |
| `SEMAPHORE_ADMIN_USER` | Your choice |
| `SEMAPHORE_ADMIN_NAME` | Your choice |
| `SEMAPHORE_ADMIN_EMAIL` | Your choice |
| `SEMAPHORE_ADMIN_PASSWORD` | Your choice, alphanumeric only |
| `SEMAPHORE_COOKIE_HASH` | First value from step 10 |
| `SEMAPHORE_COOKIE_ENCRYPTION` | Second value from step 10 |
| `SEMAPHORE_ACCESS_KEY_ENCRYPTION` | Third value from step 10 |
| `SEMAPHORE_POSTGRES_USER` | Your choice |
| `SEMAPHORE_POSTGRES_PASSWORD` | Your choice, alphanumeric only |

The last two feed the `POSTGRES_USER` and `POSTGRES_PASSWORD` lines in the pasted text. Do not edit those two lines themselves.

The alphanumeric-only rule matters here for the same reason it does everywhere else. See [Conventions](conventions.md#alphanumeric-only).

Deploying before all nine exist fails the same way a missing `GLOBAL_*` does, with Compose trying to interpolate the literal string `[[SEMAPHORE_ADMIN_PASSWORD]]` into the container's environment. Create the Secrets and click **Deploy** again.

### Deploy

Save the Stack resource, then click **Deploy**. Watch the deploy log. Komodo clones the repo onto ci01, reads the compose file, and runs the equivalent of `docker compose up -d` through Periphery.

## 12. Verify

Confirm all three services show running and healthy, in Komodo's container view for the resource:

```text
semaphore
postgres
postgres-backup
```

To check from the host instead, SSH to ci01 and run `docker compose ps` in the stack's own directory under `/opt/docker/repos/`, where Periphery cloned it.

## 13. First access

Browse to `https://semaphore.ci01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you actually set. This is real Traefik routing, through traefik-bootstrap from step 9.

Your browser will warn about the certificate. That is expected: it is self-signed, not issued by a CA your browser trusts. Accept it and continue.

Log in with the `SEMAPHORE_ADMIN_USER` and `SEMAPHORE_ADMIN_PASSWORD` you set in step 11.

If the page does not load at all, the likeliest causes are step 9 not actually healthy, or `TRAEFIK_AUTH_CHAIN` not overridden in step 11. See [Traefik bootstrap](traefik-bootstrap.md).

## What still lands on ci01

Semaphore is the first stack on ci01, not the only one. The plan puts the rest of core-infra here alongside it, and that is a real dependency for every other VM rather than a nice-to-have.

### victoriametrics-server, ready now

`stacks/victoriametrics-server` is already assembled and deployable. It is the fleet's metrics, logs, and traces backend, and every other VM is already trying to write to it: vmagent, vlagent, and vector run as sidecars in each traefik stack, buffer to their own data folders, and retry.

That is why every runbook after this one tells you to clear three keys. Deploying this stack is what makes them real.

Create them in Komodo when you do, `GLOBAL_VMAUTH_PASS` on *Settings > Secrets* and the other two on *Settings > Variables*:

| Name | Value |
| --- | --- |
| `GLOBAL_VMAUTH_USER` | Your choice |
| `GLOBAL_VMAUTH_PASS` | Your choice, alphanumeric only |
| `GLOBAL_VMAUTH_HOST` | `vmauth.ci01.home.myah-mitchell.com` |

`GLOBAL_VMAUTH_HOST` is a hostname with no scheme. Each agent builds its own URL around it, so vmagent posts to `/api/v1/write` and vlagent to `/insert/native`, both over HTTPS.

Then go back through every stack that had those three cleared and let them resolve instead. Each one starts shipping on its next deploy.

Size ci01 for this before you deploy it. Step 2 gave the VM two cores and 4 GB for Semaphore alone, and this stack adds twelve more services including Grafana and three VictoriaMetrics databases.

### The four with no stack yet

ntfy, mailrise, blackbox-exporter, and uptime-kuma each have a container directory in this repo and no stack. Assembling them is a repo change rather than a runbook step, and there is nothing to deploy until someone does it.

They are worth knowing about because two of them are referenced elsewhere. mailrise is the plausible SMTP relay behind Authentik's email settings, and ntfy is where vmalert's alerts are meant to land. See [step 4 of id01 bootstrap](id01-bootstrap.md#4-create-the-komodo-secrets-and-variables).

## What's next

Semaphore is running but not yet connected to anything. Wire it to the ansible repo next, in [Semaphore setup](semaphore-setup.md). That is where the fleet's real shared secrets stop being hand-edited per host.

After that, tf01 is the next VM. See [Running order](README.md#running-order), and [How the host runbooks are shaped](README.md#how-the-host-runbooks-are-shaped) for which parts of this runbook the later ones reuse.
