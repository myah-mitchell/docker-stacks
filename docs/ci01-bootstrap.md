# ci01 bootstrap runbook

`ci01` is the first VM in the plan brought up *through* Komodo rather than by hand —
the first real use of the pattern `docs/komodo-bootstrap.md` only sketched. Its first
stack is `stacks/semaphore-server`, deliberately chosen to go first: once Semaphore
is up and wired to the `ansible` repo, it becomes the way real secrets
(`komodo_passkeys`, `node_exporter_password`, and anything else `ansible` needs that
shouldn't be a plain committed default) get pushed to every other server in the plan,
instead of fixing them by hand host-by-host the way this doc has to for `ci01` itself.

See [`docs/overview.md`](overview.md) for how this doc fits into the overall running
order, and [`docs/komodo-bootstrap.md`](komodo-bootstrap.md) if `km01` itself isn't
up yet — this doc assumes it already is.

Everything in `<angle brackets>` is a placeholder — replace with your real values as
you go. Don't commit real values back into this file.

## Prerequisites

Before starting, these must already be true:

- `km01` is up and reachable, through step 11 of `docs/komodo-bootstrap.md` at
  least (its own `docker compose ps` shows all four containers healthy, and you've
  created the initial admin account in Komodo's UI at `http://<km-ip>:9120`).
- You know `km01`'s real `KOMODO_PASSKEY` value (from
  `stacks/komodo-server/.env` on `km01`, or wherever you recorded it after step 7 of
  `docs/komodo-bootstrap.md`) — needed in step 5 below.
- The `ubuntu-server` cloud-init template exists on the target PVE host (same
  template `km01` was cloned from).

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <ci-vmid> --name ci01 --full
```

## 2. Size and network the VM

Semaphore core (Semaphore + Postgres + postgres-backup) is light — resize down from
the template's generic defaults the same way `km01` was:

```bash
qm set <ci-vmid> --cores 2 --memory 4096
```

Give it a static IP:

```bash
qm set <ci-vmid> --ipconfig0 ip=<ci-ip>/24,gw=<gateway-ip>
```

Confirm the template's VLAN tag is the internal-only one — `ci01` is not DMZ.

## 3. Start the VM

```bash
qm start <ci-vmid>
```

Same as `km01`: the vendor cloud-init snippet fires automatically on first boot,
clones the `ansible` repo, and runs `provision.yml` locally against
`target: ubuntu_docker` — Docker, firewall, NTP, swap, node_exporter, **and Komodo
Periphery** all get installed without any manual step (see the note in step 5 about
why Periphery alone isn't usable yet).

Watch it finish via the VM's console:

```bash
tail -f /var/log/cloud-init-output.log
```

## 4. Verify base provisioning

SSH in once cloud-init finishes:

```bash
docker version
systemctl status ufw
sudo -u komodo XDG_RUNTIME_DIR=/run/user/$(id -u komodo) systemctl --user status periphery.service
```

All three should show up and running. The last command checks Periphery
specifically — it runs as a `--user` systemd service under a dedicated `komodo` OS
account (`ansible`'s `roles/docker/tasks/komodo.yml`), not as root, so a plain
`systemctl status periphery` from your own login won't find it.

## 5. Fix this VM's Periphery passkey — the one manual step

`ansible`'s `roles/docker/defaults/main.yml` ships `komodo_passkeys: ["CHANGEME"]` as
a placeholder. Komodo Core can't authenticate to any Periphery agent still running
with that value, and there's deliberately no automatic override for it yet — real
values get pushed by Semaphore once it exists, which is exactly what this whole doc
is bootstrapping. `ci01` (and `km01` itself, provisioned before its own
`KOMODO_PASSKEY` even existed) both need this fixed by hand, once, right now.

On `ci01`, re-run the same provisioning command cloud-init used
(`/tmp/ansible` from step 3 — if it's gone, re-clone it the same way
`proxmox-cloud-init/cloudinit-vendor.yml` does; **don't paste that command's
credentialed URL into this repo**, `docker-stacks` is public), adding the real
passkey as an override and scoping the re-run to just the `docker` role tag so it
doesn't repeat the entire provisioning:

```bash
cd /tmp/ansible
git pull
ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same as original run>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' \
  -e '{"komodo_passkeys":"<real KOMODO_PASSKEY value, from km01>"}' \
  --tags docker
```

Confirm it landed:

```bash
sudo -u komodo cat /home/komodo/.config/komodo/periphery.config.toml | grep passkeys
```

**Do the same thing on `km01`** if you haven't already — it has the identical
`CHANGEME` problem from its own initial provisioning, before `KOMODO_PASSKEY`
existed. Skipping this on `km01` won't block *this* doc, but leaves Komodo unable to
manage itself as a Server resource later.

Also worth a quick check while you're in `roles/docker/defaults/main.yml`:
`komodo_allowed_ips` should include `km01`'s real static IP — that's the address
Periphery expects Core's authenticated requests to come from.

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
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*

mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-backup-*
```

Unlike `km01`, there's no need to `git clone docker-stacks` onto `ci01` yourself —
Periphery does that itself (into `/opt/docker/repos/`, per `ansible`'s `komodo.yml`
task) once you point a Stack resource at it in step 11. These folders have to exist
with the right ownership *before* that first deploy, though — Periphery doesn't
create host bind-mount directories, only Docker/Compose have.

## 7. Create the `proxy` Docker network

Same one-time-per-host step as `km01`'s step 9 — nothing creates this network
automatically, and every stack's `compose.yaml` declares it `external: true`:

```bash
docker network create proxy
```

## 8. Register `ci01` as a Komodo Server resource

In Komodo's UI (`http://<km-ip>:9120`, on `km01`): go to **Resources → Servers** and
add `ci01` — however Komodo's Server resource asks for it (Periphery's address/port,
or an enrollment token, depending on your Komodo version). Confirm it shows as
connected/healthy before continuing; if it doesn't, re-check step 5's passkey first —
that's the most likely reason.

(The exact menu labels here are based on this repo's own conventions, not a verified
walkthrough of Komodo's UI — adjust to what you actually see.)

## 9. Deploy `stacks/traefik-bootstrap` onto `ci01`

`stacks/semaphore-server` has no direct published port and its Traefik labels are
gated behind `chain-authentik@file` — neither Traefik nor Authentik exist anywhere
in the plan yet, so without this step there'd be no working way to reach its UI at
all once it's deployed in step 11. `stacks/traefik-bootstrap` is a real Traefik,
just with self-signed TLS and `chain-no-auth@file` instead of a real cert resolver
and Authentik — see [`docs/traefik-bootstrap.md`](traefik-bootstrap.md) for the full
explanation and its eventual teardown (once `system-agent` replaces it here, later).

Create the runtime folders for it (its own `mkdir`/`chown` block, generated at
`stacks/traefik-bootstrap/README.md` once you've run `build.py`, or copy it from
`docs/traefik-bootstrap.md`), then register it as a Stack resource in Komodo the
same way as step 11 below — **Run Directory** `stacks/traefik-bootstrap`, **File
Path** `compose.yaml`, **Environment** `stacks/traefik-bootstrap/komodo.env` with
`SERVER_NAME`/`SUB_DOMAIN_NAME`/`DOMAIN_NAME` filled in the same way. Deploy it and
confirm it's healthy before continuing — `docker compose ps` on `ci01`, or Komodo's
own container view for the resource.

## 10. Generate Semaphore's secrets

Three of Semaphore's values aren't auto-generatable by `scripts/build.py` — they have
to be base64-encoded 32-byte keys, not plain alphanumeric, so `build.py`'s password
generator deliberately excludes them (see the root `README.md`'s secrets
conventions). Generate them now, once:

```bash
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_HASH
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_ENCRYPTION
head -c32 /dev/urandom | base64  # SEMAPHORE_ACCESS_KEY_ENCRYPTION
```

Keep these **stable across restarts** — rotating any of them invalidates every stored
SSH key/vault secret and active session. You'll paste these into Komodo's UI in step
11, as resource-level variable overrides — **never commit real values for these into
`komodo.env`.**

## 11. Create the Stack resource for `stacks/semaphore-server`

1. In Komodo's UI, go to **Resources → Stacks** and create a new one — name it
   `semaphore-server`. Set its target **Server** to the `ci01` resource from step 8.
2. Under **Source**, choose Git Repository:
   - **Repo**: `myah-mitchell/docker-stacks` (or the full
     `https://github.com/myah-mitchell/docker-stacks` URL) — no credential needed,
     the repo is public.
   - **Branch**: `main`.
3. Under **Files**:
   - **Run Directory**: `stacks/semaphore-server`.
   - **File Path**: `compose.yaml`, relative to that run directory.
4. Under **Environment**, set the source to the committed
   `stacks/semaphore-server/komodo.env`. Several values in it have no default and
   need filling in as overrides on this resource — never commit real values for any
   of these:
   - `SERVER_NAME` — `ci01`.
   - `SUB_DOMAIN_NAME` — this site, with a trailing dot, e.g. `home.` (see the root
     `README.md`'s naming conventions).
   - `DOMAIN_NAME` — the real domain, e.g. `myah-mitchell.com`.
   - `TRAEFIK_AUTH_CHAIN` — set to `chain-no-auth@file` so it routes through
     `traefik-bootstrap` (step 9) instead of the still-nonexistent
     `chain-authentik@file`. Clear this override later once `id01`/Authentik exists
     and `system-agent` replaces `traefik-bootstrap` here.
   - `SEMAPHORE_ADMIN_USER` / `SEMAPHORE_ADMIN_NAME` / `SEMAPHORE_ADMIN_EMAIL` — your
     choice, no default.
   - `SEMAPHORE_COOKIE_HASH` / `SEMAPHORE_COOKIE_ENCRYPTION` /
     `SEMAPHORE_ACCESS_KEY_ENCRYPTION` — the three values from step 10.
   - `SEMAPHORE_ADMIN_PASSWORD` and `POSTGRES_PASSWORD` are auto-generated by
     `build.py` if you'd rather run that locally and commit the result instead of
     setting them by hand in Komodo — same alphanumeric-only rule as always applies
     if you do type one in yourself (no `@`, `:`, `/`, `#`, or `?`; see the root
     `README.md` for why).
5. Save the Stack resource, then click **Deploy**. Watch the deploy log — it clones
   the repo, reads the compose file, and runs the Compose equivalent of
   `docker compose up -d` on `ci01` via Periphery.

## 12. Verify

Confirm all three containers (`semaphore`, `postgres`, `postgres-backup`) show
running/healthy, either in Komodo's own container view for this resource, or by
SSHing to `ci01` and running `docker compose ps` in
`/opt/docker/repos/<wherever Periphery checked the repo out>/stacks/semaphore-server/`.

## 13. First access

Browse to `https://semaphore.ci01.home.myah-mitchell.com` (or whatever
`SUB_DOMAIN_NAME`/`DOMAIN_NAME` you actually set) — real Traefik routing, through
`traefik-bootstrap` from step 9. **Your browser will warn about the certificate** —
it's self-signed, not issued by a CA your browser trusts, which is expected here, not
a misconfiguration; accept it and continue. See
[`docs/traefik-bootstrap.md`](traefik-bootstrap.md) if this doesn't work — most
likely cause is step 9 not actually healthy, or `TRAEFIK_AUTH_CHAIN` not overridden
in step 11.

## 14. Post-deploy: wire Semaphore to the `ansible` repo

This is the actual point of bringing `ci01` up first — closing the loop back to step
5's manual passkey fix so it doesn't have to happen by hand again.

1. **Bootstrap-phase SSH key**: Semaphore needs a static SSH key trusted by the
   `ansible` service user every host's `users` Ansible role creates. This is the same
   necessary-bootstrap-exception category as Komodo's own manual first start — nothing
   better exists yet at this point in the sequence.
2. In the Semaphore UI: add a **Key Store** entry for that SSH identity, then one
   **Repository** (`ansible`) using a read-only GitHub **deploy key** — not a
   personal access token (a deploy key's blast radius is scoped to just that one
   repo). `dotfiles` doesn't need a Repository entry — its own Ansible role clones it
   directly over plain HTTPS, no credential needed, since `myah-mitchell/dotfiles` is
   public.
3. Create a **Project** wrapping the `ansible` repo + its `hosts.yml` inventory.
4. Create a **Template** that re-runs `provision.yml`'s `docker` tag with a real
   `komodo_passkeys` override — the Semaphore-native equivalent of step 5's manual
   command — and use it against every VM from here on instead of hand-editing
   `ansible` or SSHing in to re-run it manually. Also a good place to finally fix
   `node_exporter_password`'s matching `CHANGEME` placeholder while you're at it.
5. **Superseded in Phase 7**: once step-ca's SSH CA is live, switch Semaphore to a
   dedicated `semaphore` service principal using a short-lived, auto-renewed step-ca
   cert instead of the static key from step 1 — don't skip this once that phase
   lands.

## What's next

`ci01` now runs Semaphore, and Semaphore can push real secrets to the rest of the
fleet — the actual blocker that made `tf01`/`id01`/`pk01` un-bootstrappable through
Komodo before now is gone. `tf01` is next; see
[`docs/overview.md`](overview.md) for the running order. Its own bootstrap doc
doesn't exist yet — write it when you get there, following this doc's shape (steps
1–4 provisioning are identical for every VM; step 5's manual passkey fix is no longer
needed once Semaphore's Template from step 14 above is in place; step 9's
`traefik-bootstrap` deploy is the same pattern for every VM until `system-agent`
replaces it fleet-wide; steps 10–12 registering/deploying its specific stack will
differ).
