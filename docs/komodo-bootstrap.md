# Komodo bootstrap runbook

Komodo GitOps-deploys every other stack in this repo — but it can't GitOps-deploy
*itself* the first time. This is the one deliberate exception: `km01` gets
provisioned and its stack started by hand, start to finish, using this runbook.
Follow it in order; each step assumes only the steps before it. Use it again from
scratch if `km01` is ever lost — this doc plus `ansible`'s `pve` role (which builds
the cloud-init template — the old standalone `proxmox-cloud-init` repo is
deprecated, merged into `ansible` directly) and this repo should be everything
needed to rebuild it.

Everything in `<angle brackets>` is a placeholder — replace with your real values as
you go. Don't commit real values back into this file.

## Prerequisites

Before starting, these must already be true:

- The `ubuntu-server` cloud-init template exists on the target PVE host, built by
  `ansible`'s `pve` role from its own `roles/pve/templates/create-cloud-init-template.sh.j2`
  (installed as `/usr/local/bin/create-cloud-init-template.sh` on the PVE host).
- The `ansible` repo's `pve-cloudinit.yml` task has run against that PVE host at
  least once, so its cloud-init vendor snippet has real
  `short_name`/`abbr_name`/`location_abbr`/`domain_name` values baked in.
- You know the template's VMID: `${VERSION/./}001` from the script — e.g. `26.04` →
  `2604001`.

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <km-vmid> --name km01 --full
```

## 2. Size and network the VM

Komodo core (Komodo + FerretDB + Postgres + postgres-backup) is light — resize down
from the template's generic defaults (4 vCPU / 4GB):

```bash
qm set <km-vmid> --cores 2 --memory 4096
```

`km01` is long-lived and everything else will eventually point at it, so give it
a static IP instead of the template's DHCP default:

```bash
qm set <km-vmid> --ipconfig0 ip=<km-ip>/24,gw=<gateway-ip>
```

Confirm the template's VLAN tag is the right one for an internal-only host —
`km01` is not DMZ.

## 3. Start the VM

```bash
qm start <km-vmid>
```

The vendor cloud-init snippet baked into the template fires automatically on first
boot: it clones the public `ansible` repo (`https://github.com/myah-mitchell/ansible`,
no credential needed — it's public) to `/tmp/ansible`; if the template was built with
a real `ansible_private_repo_token`, it also clones the private `ansible-private`
overlay and copies its `hosts.yml`/`group_vars/all/private.yml` over the public
repo's sanitized placeholders before running. Either way it then runs
`provision.yml` locally against `target: ubuntu_docker`, installing Docker,
firewall, NTP, swap, node_exporter, etc.

Watch it finish through the PVE console (**Datacenter → node → `km01` → Console** in
the web UI) — there's no user account to SSH in as yet, so `ssh`+`tail -f` won't
work until cloud-init finishes creating one. The console shows the same
`/var/log/cloud-init-output.log` output live as it boots.

## 4. Verify base provisioning

SSH in once cloud-init finishes:

```bash
docker version
systemctl status ufw
```

Both should show up and running. If not, stop here and fix it before continuing —
everything below assumes Docker is already working.

## 5. Clone this repo onto the VM

`docker-stacks` is public, so no credential is needed for this clone:

```bash
sudo mkdir -p /opt/docker/stacks
sudo chown $USER /opt/docker/stacks
git clone https://github.com/myah-mitchell/docker-stacks /opt/docker/stacks/docker-stacks
cd /opt/docker/stacks/docker-stacks/stacks/komodo-server
```

Stay in `stacks/komodo-server/` for the rest of this runbook unless a step says
otherwise.

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
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ferretdb-*
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*

mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-backup-*

mkdir -p /opt/docker/volumes/$projectName/komodo-backups
mkdir -p /opt/docker/volumes/$projectName/komodo-sync
mkdir -p /opt/docker/volumes/$projectName/komodo-cache
mkdir -p /opt/docker/volumes/$projectName/komodo-keys
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-*
```

`komodo-keys` matters more than the others: Komodo's Core auto-generates its own PKI
keypair on first boot and writes it there. If that volume is ever lost, every
Periphery agent in the fleet loses trust with Core and has to be re-onboarded — treat
it with the same care as the Postgres/FerretDB data directories, not like the
disposable `komodo-cache`.

## 7. Generate and fill in the stack's `.env`

`stacks/komodo-server/.env` doesn't exist yet — it's generated by `scripts/build.py`
(the same script that generates `komodo.env`/`README.md` in every stack). From the
repo root:

```bash
cd /opt/docker/stacks/docker-stacks
python3 scripts/build.py
```

This creates `.env` for every stack, including `komodo-server`. Any key ending in
`_PASSWORD`/`_PASS` that's still blank (`KOMODO_DB_PASSWORD`, `POSTGRES_PASSWORD`)
gets a random alphanumeric value automatically — leave those as generated.

Now edit `stacks/komodo-server/.env` by hand for the fields that have no default:

```bash
cd stacks/komodo-server
$EDITOR .env
```

Set:

- `SERVER_NAME` — `km01` (this host, not a leftover default from another stack)
- `SUB_DOMAIN_NAME` — this site, **with a trailing dot** — `home.` (Komodo is
  internal-only, so this is never blank here; see the root `README.md`'s naming
  conventions for the full site/role table and why an empty value is safe for
  services that don't use a sub-domain)
- `DOMAIN_NAME` — the real domain, e.g. `myah-mitchell.com`
- `KOMODO_DB_USERNAME` — any username you want (e.g. `komodo-admin`)
- `KOMODO_TITLE` — whatever you want Komodo's UI to display as its title

Nothing to set for Periphery auth here — Komodo v2 uses PKI (Ed25519 keypairs), not a
shared passkey. Core generates its own keypair automatically on first boot (see step
6's `komodo-keys` note); there's no equivalent `.env` field to fill in.

Leave `POSTGRES_USER` and `POSTGRES_BACKUP_DB`/`POSTGRES_BACKUP_USER`/
`POSTGRES_BACKUP_PASSWORD` blank — don't set these by hand:

- `POSTGRES_USER` mirrors `KOMODO_DB_USERNAME` automatically (`komodo.env` defines it
  as a reference to that key) — the next `build.py` run in this step fills it in to
  match.
- The `POSTGRES_BACKUP_*` three are meant to stay blank in `.env`; this stack's
  `compose.yaml` wires them at the Compose level to the same
  `POSTGRES_USER`/`POSTGRES_PASSWORD` FerretDB's own Postgres already uses.

**If you type any password by hand instead of using the auto-generated one, keep it
alphanumeric — no `@`, `:`, `/`, `#`, or `?`.** `containers/ferretdb/compose.yaml`
builds a Postgres connection URL by directly substituting `POSTGRES_PASSWORD` into
it, with no URL-encoding. A symbol in the password breaks that URL's parsing and
fails as a confusing DNS-resolution error against the wrong host, not as an obvious
auth error. See the root `README.md`'s secrets conventions for why this is a
deliberate repo-wide rule, not just a FerretDB quirk.

Rerun `build.py` once more so the `KOMODO_DB_USERNAME` → `POSTGRES_USER` value you
just set actually propagates:

```bash
cd /opt/docker/stacks/docker-stacks && python3 scripts/build.py
```

## 8. Create Komodo's own secrets file

`containers/komodo/compose.yaml` mounts `secrets/core.config.toml` into the Komodo
container. That file doesn't exist yet — if you skip this step, Docker will silently
create an empty *directory* at that path instead of failing, and Komodo will error on
startup. Create it now from the committed template:

```bash
cd /opt/docker/stacks/docker-stacks/containers/komodo
cp config/core.config.toml.example secrets/core.config.toml
```

Leave it as-is for now — `docker-stacks` is public, so Komodo doesn't need a
`[[git_provider]]` credential to clone it. Only come back and add one (see the
commented-out example already in the file) if you later point Komodo at a private
repo.

## 9. Create the `proxy` Docker network

Every stack's `compose.yaml` — including `traefik-server`'s own — declares `proxy` as
`external: true`. No stack owns or creates it, so it must already exist on a host
before the first stack ever starts there, or `docker compose up -d` fails with no
network to attach to. This is a one-time step per host, not just for Komodo — every
other VM in this plan (`tf01`, `ci01`, `id01`, `pk01`, `bh01`, `ap01`) needs it too
before its first stack starts.

Check `PROXY_NETWORK` in the `.env` from step 7 (`proxy` unless you changed it), then:

```bash
docker network create proxy
```

## 10. Open the firewall for Core

Every Periphery agent in the fleet dials **out** to Core (outbound mode, see decision
#19 in `PLAN.md`) — the reverse of the old model, where Core dialed out to each
Periphery and each Periphery's own host needed the inbound UFW rule instead. That
means it's now `km01` itself that needs an inbound allowance, for port 9120, not
every other VM. Nothing provisions this automatically: `km01` is a plain
`ubuntu_docker` host as far as `ansible` is concerned (`KOMODO: true` there only
installs the Periphery *agent*, port 8120, no longer even inbound — see
`roles/docker/tasks/komodo.yml`), and Core itself is this hand-bootstrapped compose
stack, not anything `ansible` manages:

```bash
sudo ufw allow 9120/tcp comment 'Komodo Core'
sudo ufw status
```

This also covers your own browser reaching `http://<km-ip>:9120` directly in step 12
below — that direct access was never firewalled for either, this is the first point
in the runbook it actually matters.

## 11. Bring the stack up

From `stacks/komodo-server/`:

```bash
docker compose up -d
docker compose ps
```

All four containers (`komodo`, `ferretdb`, `postgres`, `postgres-backup`) should show
as running/healthy. If `ferretdb` is stuck failing to reach Postgres, re-check the
password characters from step 7.

## 12. First access

`tf01` doesn't exist yet — Komodo is what will deploy it — so Komodo's UI
isn't reachable through Traefik. Its container publishes its own port directly for
exactly this bootstrap reason:

```
http://<km-ip>:9120
```

Open that and create the initial admin account when prompted.

## 13. Get Core's public key for `ansible`

Every other host's Periphery agent needs to trust this specific Core, via its public
key (`ansible`'s `komodo_core_public_key`, see `roles/docker/defaults/main.yml`).
Unlike the old passkey, this value **isn't secret** — commit the real one directly
once you have it, no `CHANGEME` placeholder needed.

**Not yet verified against a live instance**: exactly where Komodo's UI/API surfaces
Core's own public key for copying out. Check Komodo's Settings/Servers screens (or
`docker exec` into the container and read `/config/keys/core.key`'s public
counterpart directly) once this stack is actually up, and update this step with the
real answer.

## What's next

`km01` is up, but still alone — no other VM exists yet, so there's nothing for it to
GitOps-deploy, and its own UI still sits on the direct `:9120` port rather than
behind Traefik+Authentik. The rest of the fleet gets bootstrapped one host at a time
from here, starting with `ci01` (Semaphore) — see
[`docs/overview.md`](overview.md) for the running order and links to each host's own
bootstrap doc as they get written.

Two things about `km01` itself to come back to later, not now:

- **Registering other hosts and deploying stacks to them through Komodo** — the
  general "add a Server resource, add a Stack resource, deploy" pattern isn't
  described here in the abstract. It's worked out for real, against `ci01`'s first
  stack, in [`docs/ci01-bootstrap.md`](ci01-bootstrap.md) — that's the reference to
  follow for every VM after it too.
- **Folding `km01`'s own UI behind Traefik + Authentik.** Needs `ci01`
  (monitoring), `id01` (the auth chain), and `pk01` (internal certs) all live first,
  plus `stacks/system-agent` — every VM's own local Traefik — fixed and proven on a
  less-critical host before it's retrofitted onto `km01` last. Until then, the direct
  `:9120` port is `km01`'s real, current access path, not just a documented
  fallback.
