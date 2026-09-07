# km01 bootstrap runbook

km01 runs Komodo Core, which GitOps-deploys every other stack in the fleet. It cannot GitOps-deploy itself, so it is the one host built by hand, start to finish.

Follow the steps in order. Each one assumes only the steps before it. Use this doc again from scratch if km01 is ever lost: this page, the ansible repo's pve role, and this repo are everything needed to rebuild it.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Clone the template into a VM](#1-clone-the-template-into-a-vm)
- [2. Size and network the VM](#2-size-and-network-the-vm)
- [3. Start the VM](#3-start-the-vm)
- [4. Verify base provisioning](#4-verify-base-provisioning)
- [5. Clone this repo onto the VM](#5-clone-this-repo-onto-the-vm)
- [6. Create the runtime folders](#6-create-the-runtime-folders)
- [7. Generate and fill in the stack's .env](#7-generate-and-fill-in-the-stacks-env)
- [8. Create Komodo's own secrets file](#8-create-komodos-own-secrets-file)
- [9. Create the proxy Docker network](#9-create-the-proxy-docker-network)
- [10. Open the firewall for Core](#10-open-the-firewall-for-core)
- [11. Bring the stack up](#11-bring-the-stack-up)
- [12. Create the admin account](#12-create-the-admin-account)
- [13. Give ansible Core's address and public key](#13-give-ansible-cores-address-and-public-key)
- [14. Create Komodo's global Variables](#14-create-komodos-global-variables)
- [What's next](#whats-next)

## Prerequisites

- The `ubuntu-server-2604` cloud-init template exists on the target PVE host. The ansible repo's pve role builds it.
- That host's cloud-init vendor snippet has been installed at least once, so it carries real identity values rather than blanks. The pve role's cloud-init task installs it.
- You can reach the PVE web UI and get a shell on the host.

## Placeholders

Replace these as you go. Never commit a real value back into this file.

| Placeholder | Value |
| --- | --- |
| `<template-vmid>` | VMID of the cloud-init template. The pve role derives both it and the template's name from the Ubuntu version, so 26.04 gives VMID `2604001` and name `ubuntu-server-2604` |
| `<km-vmid>` | VMID to give the new VM |
| `<km-ip>` | Static address for km01 |
| `<gateway-ip>` | Gateway for that subnet |

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <km-vmid> --name km01 --full
```

## 2. Size and network the VM

Resize down from the template's generic 4 vCPU and 4 GB defaults. Komodo Core, FerretDB, Postgres, and postgres-backup together are light:

```bash
qm set <km-vmid> --cores 2 --memory 4096
```

Give it a static address rather than the template's DHCP default. km01 is long-lived and every other host will eventually point at it:

```bash
qm set <km-vmid> --ipconfig0 ip=<km-ip>/24,gw=<gateway-ip>
```

Confirm the template's VLAN tag is the internal-only one. km01 is not in the DMZ.

## 3. Start the VM

```bash
qm start <km-vmid>
```

Cloud-init provisions the host on first boot with no input from you. It installs Docker, the firewall, NTP, swap, node_exporter, and Komodo Periphery.

In the PVE web UI, expand *Datacenter* to km01 and open its *Console*. Watch cloud-init finish there. No account exists to SSH in as until cloud-init creates one, so the console is the only view of the boot.

### What the vendor snippet does

Skip this unless something goes wrong.

The snippet clones the public ansible repo to `/tmp/ansible`. If the template was built with a real private-repo token, it also clones the ansible-private overlay and copies its `hosts.yml` and `group_vars/all/private.yml` over the public repo's placeholders. It then runs `provision.yml` locally against `target: ubuntu_docker`.

Without that token the host still comes up provisioned, but with placeholder identity and secret values rather than the real ones.

## 4. Verify base provisioning

SSH in once cloud-init finishes:

```bash
docker version
systemctl status ufw
```

Both should be up and running. Stop here and fix it if not: everything below assumes Docker works.

Periphery is installed on this host too, but km01 runs Core, so it is not doing anything useful yet. Ignore it for now.

## 5. Clone this repo onto the VM

The docker-stacks repo is public, so no credential is needed:

```bash
sudo mkdir -p /opt/docker/stacks
sudo chown $USER /opt/docker/stacks
git clone https://github.com/myah-mitchell/docker-stacks /opt/docker/stacks/docker-stacks
```

## 6. Create the runtime folders

```bash
projectName="komodo"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/ferretdb-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ferretdb-*

mkdir -p /opt/docker/volumes/$projectName/postgres-data
mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*

mkdir -p /opt/docker/volumes/$projectName/komodo-backups
mkdir -p /opt/docker/volumes/$projectName/komodo-sync
mkdir -p /opt/docker/volumes/$projectName/komodo-cache
mkdir -p /opt/docker/volumes/$projectName/komodo-keys
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-*
```

Periphery does not create host bind-mount directories, and neither does Compose, so these have to exist with the right ownership before the first deploy.

This list mirrors the [generated README for komodo-server](../stacks/komodo-server/README.md), which `scripts/build.py` rebuilds from the container fragments. If the two ever disagree, that file is correct and this one is stale.

### Why 100000 and 101000

Base provisioning sets `"userns-remap": "default"` in `/etc/docker/daemon.json`, so container UIDs are offset by 100000 on the host. Container UID 0 becomes host UID 100000, and container UID 1000 becomes 101000.

A directory written by a container running as root takes `100000`. One written by a container running as its own `PUID` takes `101000`. Run `cat /etc/subuid` on the host if the offset ever looks wrong.

> [!IMPORTANT]
> `komodo-keys` holds the Ed25519 keypair Core generates on first boot. Losing that volume breaks trust with every Periphery agent in the fleet, and each one has to be re-onboarded by hand. Treat it like the Postgres and FerretDB data directories, not like the disposable `komodo-cache`.

## 7. Generate and fill in the stack's .env

`stacks/komodo-server/.env` does not exist yet. `scripts/build.py` generates it, along with every other stack's, and it is gitignored so it never reaches the repo.

From the repo root:

```bash
cd /opt/docker/stacks/docker-stacks
python3 scripts/build.py
```

Any key ending in `_PASSWORD` or `_PASS` that was blank now holds a random 48-character value. Leave `KOMODO_DB_PASSWORD` and `POSTGRES_PASSWORD` exactly as generated.

Now edit these five keys:

```bash
$EDITOR stacks/komodo-server/.env
```

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `km01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.`. Komodo is internal only, so it is never blank here |
| `DOMAIN_NAME` | The real domain, for example `myah-mitchell.com` |
| `KOMODO_DB_USERNAME` | Any username, for example `komodo-admin` |
| `KOMODO_TITLE` | What Komodo's UI displays as its title. Falls back to `Komodo` if you leave it blank |

Leave `POSTGRES_USER` and the three `POSTGRES_BACKUP_*` keys blank. `POSTGRES_USER` mirrors `KOMODO_DB_USERNAME` automatically, and this stack's `compose.yaml` wires the backup credentials to the same Postgres user and password FerretDB already uses.

Periphery auth needs nothing here. Komodo v2 uses per-host Ed25519 keypairs, not a shared passkey, and Core generates its own on first boot into the `komodo-keys` volume from step 6.

> [!WARNING]
> If you replace a generated password by hand, keep it alphanumeric. `containers/ferretdb/compose.yaml` substitutes `POSTGRES_PASSWORD` straight into a connection URL with no encoding, so a URL-reserved symbol breaks that URL and surfaces as a DNS resolution failure against the wrong hostname rather than an auth error. See [Conventions](conventions.md#alphanumeric-only).

Run the build again so the username you just set propagates into `POSTGRES_USER`:

```bash
python3 scripts/build.py
```

## 8. Create Komodo's own secrets file

`containers/komodo/compose.yaml` mounts `secrets/core.config.toml` into the container. Docker silently creates an empty directory at that path if the file is missing, and Komodo then fails at startup.

Create it from the committed template:

```bash
cd /opt/docker/stacks/docker-stacks/containers/komodo
cp config/core.config.toml.example secrets/core.config.toml
```

Leave it as it is. The repo is public, so Komodo needs no `[[git_provider]]` credential to clone it. Add one, using the commented-out example already in the file, only if you later point Komodo at a private repo.

## 9. Create the proxy Docker network

```bash
docker network create proxy
```

Every deployable stack's `compose.yaml` declares `proxy` as `external: true`. No stack creates it, so it has to exist on a host before that host's first stack starts, or `docker compose up -d` fails with nothing to attach to.

This is a one-time step on every VM in the plan, not just km01.

## 10. Open the firewall for Core

```bash
sudo ufw allow 9120/tcp comment 'Komodo Core'
sudo ufw status
```

Every Periphery agent in the fleet dials out to Core, so km01 is the only host that needs an inbound allowance. Nothing provisions it: km01 is a plain `ubuntu_docker` host as far as ansible is concerned, and Core is this hand-built Compose stack rather than anything ansible manages.

This also covers reaching `http://<km-ip>:9120` from your own browser in step 12.

## 11. Bring the stack up

```bash
cd /opt/docker/stacks/docker-stacks/stacks/komodo-server
docker compose up -d
docker compose ps
```

All four services should show as running and healthy:

```text
komodo
ferretdb
postgres
postgres-backup
```

If ferretdb cannot reach Postgres, re-check the password characters from step 7.

## 12. Create the admin account

Open `http://<km-ip>:9120` in a browser.

Enter a username and password, then click **Sign Up**. This is the first account on the instance, so it becomes the admin.

km01 is not behind Traefik yet, so this direct port is its real access path rather than a fallback. See [What's next](#whats-next).

## 13. Give ansible Core's address and public key

Every other host's Periphery agent needs to know where Core is and which Core to trust. Both values live in ansible-private's `group_vars/all/private.yml`, not in the public ansible repo, whose `roles/docker/defaults/main.yml` only holds blank defaults.

In Komodo's UI, go to *Settings*. Core's public key is at the top of the page.

Set both keys in ansible-private, then commit and push:

```yaml
komodo_core_address: "http://<km-ip>:9120"
komodo_core_public_key: "<the key from Settings>"
```

Neither is secret. The public key is a public key, and the address is an internal one, so both get committed for real with no `CHANGEME` placeholder.

> [!IMPORTANT]
> Do this before provisioning any other VM. Cloud-init runs `provision.yml` on first boot. A host that boots while `komodo_core_address` is still blank writes an empty `core_address` into its `periphery.config.toml` and never reaches Core.

## 14. Create Komodo's global Variables

Every stack's `komodo.env` references a shared set of `[[GLOBAL_...]]` values for the container user and group, resource limits, and health-check timings. You set them once here and every stack across the fleet picks them up.

Nothing creates them for you. Skip this step and every stack deployed through Komodo fails the same way, with Compose trying to interpolate a literal unresolved string into a numeric field:

```text
error while interpolating services..traefik.cpus: failed to cast to expected type: strconv.ParseFloat: parsing "[[GLOBAL_CPUS_LIMIT]]": invalid syntax
```

In Komodo's UI, go to *Settings > Variables* and create one Variable per row. Name each one exactly as shown, with no `[[` or `]]`: Komodo adds those itself when it interpolates.

| Variable | Value |
| --- | --- |
| `GLOBAL_PUID` | `1000` |
| `GLOBAL_PGID` | `1000` |
| `GLOBAL_TZ` | Your real timezone, for example `America/Chicago` |
| `GLOBAL_DOCKER_VOLUMES` | `/opt/docker/volumes` |
| `GLOBAL_DOCKER_LOGS` | `/opt/docker/logs` |
| `GLOBAL_PROXY_NETWORK` | `proxy` |
| `GLOBAL_MEM_LIMIT` | `2G` |
| `GLOBAL_MEM_SWAP_LIMIT` | `2.5G` |
| `GLOBAL_MEM_RESERVATION` | `64M` |
| `GLOBAL_PIDS_LIMIT` | `200` |
| `GLOBAL_CPUS_LIMIT` | `2` |
| `GLOBAL_RESTART_GRACE` | `1m` |
| `GLOBAL_RESTART_MODE` | `unless-stopped` |
| `GLOBAL_LOG_MAX_SIZE` | `10m` |
| `GLOBAL_LOG_MAX_FILE` | `3` |
| `GLOBAL_HEALTH_INTERVAL` | `60s` |
| `GLOBAL_HEALTH_TIMEOUT` | `10s` |
| `GLOBAL_HEALTH_RETRIES` | `5` |
| `GLOBAL_HEALTH_START` | `10s` |

These are the same values `scripts/base-testing.env` uses for local Compose testing. Adjust to taste.

Leave **Is Secret** unticked on all of them. They are operational defaults, not credentials.

If a stack already failed with the interpolation error above, there is no need to touch its Environment text. Create the Variables and click **Deploy** again: Komodo re-resolves `[[...]]` references at deploy time.

## What's next

km01 is up and alone. Nothing else exists for it to deploy yet, and its UI still sits on the direct `:9120` port.

ci01 is next, running Semaphore. See [ci01 bootstrap](ci01-bootstrap.md), which is also the template every VM after it follows.

Two things about km01 itself to come back to later:

Registering other hosts and deploying stacks to them through Komodo is worked out for real against ci01's first stack in [ci01 bootstrap](ci01-bootstrap.md). That is the reference to follow for every VM after it too.

Folding km01's own UI behind Traefik and Authentik needs ci01, id01, and pk01 all live first, plus system-agent fixed and proven on a less critical host. km01 gets that retrofit last, not first.
