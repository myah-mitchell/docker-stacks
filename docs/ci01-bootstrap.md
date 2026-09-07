# ci01 bootstrap runbook

`ci01` is the first VM deployed by Komodo rather than built by hand. It is the first real use of the pattern every host after it follows, so read it as a template even when the host you are building is not `ci01`.

Its first stack is `stacks/semaphore-server`. Semaphore goes first on purpose: once it is up and wired to the ansible repo, it becomes the way real shared secrets reach every other server, instead of being fixed by hand host by host.

This runbook ends when Semaphore's UI loads. Wiring Semaphore to ansible is a separate job, in [Semaphore setup](semaphore-setup.md).

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules.

## Prerequisites

- `km01` is finished, through step 14 of [km01 bootstrap](komodo-bootstrap.md). Its four containers are healthy, its admin account exists, its firewall allows inbound 9120, and its global `[[GLOBAL_...]]` Variables are created. Step 11 below fails without those Variables.
- The real Komodo Core address and public key are committed and pushed in ansible-private's `group_vars/all/private.yml`. That is step 13 of the `km01` runbook, and `ci01` reads both at first boot.
- The `ubuntu-server` cloud-init template exists on the target PVE host, the same one `km01` was cloned from.
- You can open Komodo's UI when you reach step 5. The onboarding key is single-use and short-lived, so there is nothing to prepare ahead of time.

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<template-vmid>` | VMID of the `ubuntu-server` template |
| `<ci-vmid>` | VMID to give the new VM |
| `<ci-ip>` | Static address for `ci01` |
| `<gateway-ip>` | Gateway for that subnet |
| `<km-ip>` | `km01`'s address, from its own runbook |

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <ci-vmid> --name ci01 --full
```

## 2. Size and network the VM

Semaphore, Postgres, and postgres-backup are light, so resize down from the template's generic defaults the same way `km01` was:

```bash
qm set <ci-vmid> --cores 2 --memory 4096
qm set <ci-vmid> --ipconfig0 ip=<ci-ip>/24,gw=<gateway-ip>
```

Confirm the template's VLAN tag is the internal-only one. `ci01` is not in the DMZ.

## 3. Start the VM

```bash
qm start <ci-vmid>
```

Cloud-init provisions the host on first boot the same way `km01` was, installing Docker, the firewall, NTP, swap, node_exporter, and Komodo Periphery with no manual step. See [what the vendor snippet does](komodo-bootstrap.md#what-the-vendor-snippet-does) if you need the internals.

Watch it finish in *Datacenter > node > ci01 > Console*. There is no account to SSH in as until cloud-init creates one.

## 4. Verify base provisioning

SSH in once cloud-init finishes:

```bash
docker version
systemctl status ufw
sudo -u komodo XDG_RUNTIME_DIR=/run/user/$(id -u komodo) systemctl --user status periphery.service
```

All three should be up and running.

The last command needs that exact shape. Periphery runs as a `--user` systemd service under a dedicated `komodo` OS account, created by ansible's `roles/docker/tasks/komodo.yml`, so a plain `systemctl status periphery` from your own login finds nothing.

## 5. Give ci01 an onboarding key

This is the one manual step, and it is permanent. Every future host needs its own fresh onboarding key at provision time, the same way every new host needs its own SSH host key accepted.

The ansible repo ships `komodo_onboarding_key` blank in the docker role's defaults, because a real value is single-use and must never be committed. Periphery needs one to make its first outbound connection to Core. After that, Core and `ci01` trust each other by their own Ed25519 keypairs and the onboarding key is discarded.

Generate one in Komodo's UI on `km01`, at `http://<km-ip>:9120`, under *Settings > Onboarding > New Onboarding Key*.

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

On `ci01`:

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

Unlike `km01`, you do not clone docker-stacks onto `ci01` yourself. Periphery clones it into `/opt/docker/repos/` once you point a Stack resource at it in step 11. The folders above still have to exist with the right ownership before that first deploy, because neither Periphery nor Compose creates host bind-mount directories.

This list mirrors the [generated README for semaphore-server](../stacks/semaphore-server/README.md), which `scripts/build.py` rebuilds. That file wins if the two disagree.

## 7. Create the proxy Docker network

```bash
docker network create proxy
```

Same one-time-per-host step as `km01`'s step 9. Nothing creates this network, and every stack's `compose.yaml` declares it `external: true`.

## 8. Confirm ci01 shows as a Komodo Server

Step 5's onboarding key created the `ci01` Server resource the moment Periphery made its first outbound connection. There is nothing to add by hand.

In Komodo's UI on `km01`, check *Resources > Servers* and confirm `ci01` shows connected and healthy before continuing. Re-check step 5 if it is not listed at all.

## 9. Deploy traefik-bootstrap onto ci01

`stacks/semaphore-server` publishes no port directly, and its Traefik labels are gated behind `chain-authentik@file`. Neither Traefik nor Authentik exists anywhere in the plan yet, so without this step there is no way to reach Semaphore's UI once it deploys.

`stacks/traefik-bootstrap` is a real Traefik with self-signed TLS and `chain-no-auth@file` in place of a cert resolver and Authentik. See [Traefik bootstrap](traefik-bootstrap.md) for what it does and when it gets torn down.

Create its runtime folders first:

```bash
projectName="traefik"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/logs/$projectName/traefik
sudo chown 101000:101000 /opt/docker/logs/$projectName/traefik

mkdir -p /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-*
```

Then follow [How to deploy it](traefik-bootstrap.md#how-to-deploy-it) for the Stack resource itself. Target *Server* `ci01`, set `SERVER_NAME` to `ci01`, and use the same `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you will use in step 11.

Confirm `traefik`, `error-pages`, `socket-proxy`, `socket-proxy-rw`, and `logrotate` all show running and healthy before continuing.

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
| *Repo* | `myah-mitchell/docker-stacks`. No credential needed, the repo is public |
| *Branch* | `main` |
| *Run Directory* | `stacks/semaphore-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

### Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/semaphore-server/komodo.env` in this repo, copy its full contents, and paste them into that field.

Four values in the pasted text have no default and must be edited here:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, for example `myah-mitchell.com` |
| `TRAEFIK_AUTH_CHAIN` | `chain-no-auth@file`, so it routes through `traefik-bootstrap` rather than the nonexistent `chain-authentik@file` |

Clear that `TRAEFIK_AUTH_CHAIN` override later, once `id01` and Authentik exist and `system-agent` has replaced `traefik-bootstrap` here.

Leave every `[[...]]` reference in the pasted text exactly as it is. Komodo resolves them at deploy time from its own Variables and Secrets, which is the next step.

### Create the nine Semaphore Secrets

The `[[GLOBAL_...]]` references already resolve, from `km01`'s step 14. The `[[SEMAPHORE_...]]` ones do not exist yet.

Go to *Settings > Secrets* on `km01` and create all nine by name. These are real credentials, so Secrets rather than Variables: Komodo resolves both identically, but Secrets stay masked in the UI.

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

Save the Stack resource, then click **Deploy**. Watch the deploy log. Komodo clones the repo onto `ci01`, reads the compose file, and runs the equivalent of `docker compose up -d` through Periphery.

## 12. Verify

Confirm `semaphore`, `postgres`, and `postgres-backup` all show running and healthy, either in Komodo's container view for the resource or by SSHing to `ci01` and running `docker compose ps` under `/opt/docker/repos/`.

## 13. First access

Browse to `https://semaphore.ci01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you actually set. This is real Traefik routing, through `traefik-bootstrap` from step 9.

Your browser will warn about the certificate. That is expected: it is self-signed, not issued by a CA your browser trusts. Accept it and continue.

Log in with the `SEMAPHORE_ADMIN_USER` and `SEMAPHORE_ADMIN_PASSWORD` you set in step 11.

If the page does not load at all, the likeliest causes are step 9 not actually healthy, or `TRAEFIK_AUTH_CHAIN` not overridden in step 11. See [Traefik bootstrap](traefik-bootstrap.md).

## What's next

Semaphore is running but not yet connected to anything. Wire it to the ansible repo next, in [Semaphore setup](semaphore-setup.md). That is where the fleet's real shared secrets stop being hand-edited per host.

After that, `tf01` is the next VM. See [Running order](README.md#running-order), and [Writing the next host's doc](README.md#writing-the-next-hosts-doc) for which parts of this runbook to copy.
