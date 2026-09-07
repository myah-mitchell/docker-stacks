# ci01 bootstrap runbook

`ci01` is the first VM in the plan brought up *through* Komodo rather than by hand —
the first real use of the pattern `docs/komodo-bootstrap.md` only sketched. Its first
stack is `stacks/semaphore-server`, deliberately chosen to go first: once Semaphore
is up and wired to the `ansible` repo, it becomes the way real secrets
(`node_exporter_password`, and anything else `ansible` needs that shouldn't be a
plain committed default) get pushed to every other server in the plan, instead of
fixing them by hand host-by-host.

Komodo's own Core↔Periphery trust is a separate, already-solved problem now — it uses
v2 PKI (Ed25519 keypairs), not a shared passkey, so there's no fleet-wide secret for
Semaphore to push for Komodo specifically. `ci01` still needs one manual, one-time
step (generating its own onboarding key, step 5 below) — that's just how PKI
onboarding works for every host, permanently, not a bootstrap-phase gap Semaphore
later closes.

See [`docs/overview.md`](overview.md) for how this doc fits into the overall running
order, and [`docs/komodo-bootstrap.md`](komodo-bootstrap.md) if `km01` itself isn't
up yet — this doc assumes it already is.

Everything in `<angle brackets>` is a placeholder — replace with your real values as
you go. Don't commit real values back into this file.

## Prerequisites

Before starting, these must already be true:

- `km01` is up and reachable, through step 14 of `docs/komodo-bootstrap.md` at
  least (its own `docker compose ps` shows all four containers healthy, you've
  created the initial admin account in Komodo's UI at `http://<km-ip>:9120`, its
  firewall allows inbound 9120 per that doc's step 10, you've committed its real
  Core public key into `ansible`'s `komodo_core_public_key`, and you've created its
  global Variables per that doc's step 14 — step 9 below fails without them).
- You're ready to generate `ci01` a fresh onboarding key in Komodo's UI right before
  step 5 below — it's single-use and short-lived, so there's nothing to have on hand
  ahead of time, just the ability to open Komodo's UI when you get there.
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
clones the public `ansible` repo (and the private `ansible-private` overlay too, if
the template was built with a real `ansible_private_repo_token` — see
`docs/komodo-bootstrap.md` step 3), and runs `provision.yml` locally against
`target: ubuntu_docker` — Docker, firewall, NTP, swap, node_exporter, **and Komodo
Periphery** all get installed without any manual step (see the note in step 5 about
why Periphery alone isn't usable yet).

Watch it finish through the PVE console (**Datacenter → node → `ci01` → Console** in
the web UI) — same as `km01`, there's no user account to SSH in as until cloud-init
finishes, so `ssh`+`tail -f` isn't an option here.

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

## 5. Give `ci01` an onboarding key — the one manual step

`ansible`'s `roles/docker/defaults/main.yml` ships `komodo_onboarding_key: ""` —
deliberately blank, since a real value is single-use and shouldn't ever be committed.
Periphery needs one to make its first outbound connection to Core; after that,
Core and `ci01` trust each other by their own PKI keypairs and the onboarding key is
discarded.

Generate one now, in Komodo's UI on `km01` (`http://<km-ip>:9120`) — Settings →
Onboarding -> New Onboarding Key.

Then re-run the same provisioning command cloud-init used, scoping it to just the
`docker` role tag so it doesn't repeat the entire provisioning, passing the
onboarding key as a one-off override:

```bash
cd /tmp/ansible
ansible-playbook -i hosts.yml -c local provision.yml -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same as originial run>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' -e '{"komodo_onboarding_key":"<the key you just generated>"}' --tags docker
```

`/tmp/ansible` should still be the same checkout cloud-init made in step 3, with the
private overlay's real `hosts.yml`/`group_vars/all/private.yml` already copied in —
just re-run in place, no re-clone needed. **Don't `git pull` it first**: those two
files are locally modified relative to git (the overlay copies over them, it doesn't
commit), so pulling risks Git either refusing (local changes would be overwritten)
or, worse, silently reverting them to the public repo's sanitized placeholders if
upstream `ansible` ever touches those same paths.

If `/tmp/ansible` really is gone, re-clone the public repo fresh (no credential
needed, it's public: `git clone https://github.com/myah-mitchell/ansible /tmp/ansible`)
and re-run `./scripts/bootstrap-private.sh <ansible-private-url>` to re-apply the
overlay before provisioning — **don't paste the private repo's own credentialed
clone URL/token into this repo**, `docker-stacks` is public; point at
`ansible`'s own `README.md`/`scripts/bootstrap-private.sh` instead.

Confirm it landed and connected — in Komodo's UI, the `ci01` Server resource (which
the onboarding key should have created automatically) should show connected/healthy.
On `ci01` itself:

```bash
sudo -u komodo grep -A1 'core_address\|connect_as' /home/komodo/.config/komodo/periphery.config.toml
```

This is a **permanent** part of onboarding every future host, not a bootstrap-phase
gap that goes away once Semaphore exists — every new server gets its own fresh
onboarding key at provision time, the same way every new host needs its own SSH host
key accepted. What Semaphore *does* remove is the equivalent manual step for
`node_exporter_password` and similar real shared secrets — see step 14.

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

## 8. Confirm `ci01` shows as a Komodo Server resource

Step 5's onboarding key should already have created the `ci01` Server resource the
moment Periphery made its first outbound connection — nothing left to add by hand
here, unlike the old inbound/enrollment-token model. In Komodo's UI (`http://<km-ip>:9120`,
on `km01`): check **Resources → Servers** and confirm `ci01` shows connected/healthy
before continuing. If it doesn't show up at all, re-check step 5's onboarding key
first — that's the most likely reason.

## 9. Deploy `stacks/traefik-bootstrap` onto `ci01`

`stacks/semaphore-server` has no direct published port and its Traefik labels are
gated behind `chain-authentik@file` — neither Traefik nor Authentik exist anywhere
in the plan yet, so without this step there'd be no working way to reach its UI at
all once it's deployed in step 11. `stacks/traefik-bootstrap` is a real Traefik,
just with self-signed TLS and `chain-no-auth@file` instead of a real cert resolver
and Authentik — see [`docs/traefik-bootstrap.md`](traefik-bootstrap.md) for the full
explanation and its eventual teardown (once `system-agent` replaces it here, later).

Create the runtime folders for it:

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

Then follow [`docs/traefik-bootstrap.md`](traefik-bootstrap.md)'s "How to deploy it"
section for the Komodo Stack-resource setup itself — target **Server** `ci01`,
`SERVER_NAME` `ci01`, same `SUB_DOMAIN_NAME`/`DOMAIN_NAME` as step 11 below. Deploy
it and confirm `traefik`/`error-pages`/`socket-proxy`/`socket-proxy-rw`/`logrotate`
all show running/healthy before continuing — `docker compose ps` on `ci01`, or
Komodo's own container view for the resource.

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
SSH key/vault secret and active session. `stacks/semaphore-server/komodo.env`
already references them as `[[SEMAPHORE_COOKIE_HASH]]` etc. — Komodo-wide Secrets,
not something typed into this stack's Environment text — so create each one now in
Komodo's UI (**Settings → Secrets**, on `km01`) with these values, under exactly
those names. **Never commit real values for these into `komodo.env`.**

## 11. Create the Stack resource for `stacks/semaphore-server`

1. In Komodo's UI, go to **Resources → Stacks** and create a new one — name it
   `semaphore-server`. Set its target **Server** to the `ci01` resource from step 8.
2. Under **Choose Mode**, **choose Git Repo**:
   - **Repo**: `myah-mitchell/docker-stacks` (or the full
     `https://github.com/myah-mitchell/docker-stacks` URL) — no credential needed,
     the repo is public.
   - **Branch**: `main`.
3. Under **Files**:
   - **Run Directory**: `stacks/semaphore-server`.
   - **File Path**: `compose.yaml`, relative to that run directory.
4. Under **Environment**, there's no "point at a file" option — it's a plain text
   editor field. Open `stacks/semaphore-server/komodo.env` in this repo, copy its
   full contents, and paste them directly into that editor. It has three kinds of
   values in it:
   - **No default, must hand-edit here**: `SERVER_NAME` (`ci01`), `SUB_DOMAIN_NAME`
     (this site, with a trailing dot, e.g. `home.` — see the root `README.md`'s
     naming conventions), `DOMAIN_NAME` (the real domain, e.g. `myah-mitchell.com`),
     and `TRAEFIK_AUTH_CHAIN` — set to `chain-no-auth@file` so it routes through
     `traefik-bootstrap` (step 9) instead of the still-nonexistent
     `chain-authentik@file`. Clear this override later once `id01`/Authentik exists
     and `system-agent` replaces `traefik-bootstrap` here.
   - **`[[GLOBAL_...]]` references, resolved automatically**: same as every other
     stack — see `docs/komodo-bootstrap.md` step 14. Don't edit these.
   - **`[[SEMAPHORE_...]]` references, resolved the same way — but as
     Semaphore-specific Secrets, not global ones**: `SEMAPHORE_ADMIN_USER`,
     `SEMAPHORE_ADMIN_NAME`, `SEMAPHORE_ADMIN_EMAIL`, `SEMAPHORE_ADMIN_PASSWORD`,
     `SEMAPHORE_COOKIE_HASH`, `SEMAPHORE_COOKIE_ENCRYPTION`,
     `SEMAPHORE_ACCESS_KEY_ENCRYPTION`, `SEMAPHORE_POSTGRES_USER`, and
     `SEMAPHORE_POSTGRES_PASSWORD` (this last pair feeds `POSTGRES_USER`/
     `POSTGRES_PASSWORD` in the pasted text — don't touch those two lines
     themselves). All nine are already committed as `[[NAME]]` references, exactly
     like `[[GLOBAL_...]]` — leave them as pasted. Instead, go create each one in
     Komodo's UI under **Settings → Secrets** (real credentials, so Secrets rather
     than Variables — Komodo resolves both the same way, but Secrets stay masked),
     name-for-name:
     - `SEMAPHORE_ADMIN_USER` / `SEMAPHORE_ADMIN_NAME` / `SEMAPHORE_ADMIN_EMAIL` —
       your choice.
     - `SEMAPHORE_COOKIE_HASH` / `SEMAPHORE_COOKIE_ENCRYPTION` /
       `SEMAPHORE_ACCESS_KEY_ENCRYPTION` — the three values from step 10.
     - `SEMAPHORE_ADMIN_PASSWORD` / `SEMAPHORE_POSTGRES_USER` /
       `SEMAPHORE_POSTGRES_PASSWORD` — your choice; same alphanumeric-only rule as
       always applies (no `@`, `:`, `/`, `#`, or `?`; see the root `README.md` for
       why).
     If you deploy before creating all nine, Compose fails the same way missing
     `GLOBAL_*` ones do — trying to interpolate the literal string
     `[[SEMAPHORE_ADMIN_PASSWORD]]` (etc.) into the container's environment; go
     create the Secrets, then hit Deploy again.
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

This is the actual point of bringing `ci01` up first — closing the loop for real
shared secrets like `node_exporter_password`, which (unlike Komodo's own PKI trust)
genuinely do need a fleet-wide push mechanism.

1. **Bootstrap-phase SSH key**: generate a keypair Semaphore will use to reach every
   host's `ansible` service account (created by `ansible`'s `users` role — see
   `roles/users/defaults/main.yml`, `ansible_account: "ansible"`):

   ```bash
   ssh-keygen -t ed25519 -C "semaphore-bootstrap" -f ./semaphore-bootstrap -N ""
   ```

   Add the **public** half to `ansible-private`'s `group_vars/all/private.yml` under
   `ansible_ssh_public_keys` (a list — append to it, don't replace an existing key),
   commit, and push. Every host that's *already* been provisioned (`ci01` itself, at
   minimum) won't pick this up until you re-run the `users` tag against it by hand one
   more time — the same manual-SSH pattern as step 5 above, since Semaphore doesn't
   exist yet to do it for you:

   ```bash
   cd /path/to/ansible && ./scripts/bootstrap-private.sh <ansible-private-url>
   ansible-playbook -i hosts.yml -c local provision.yml -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same as original run>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' --tags users
   ```

   Every host provisioned *after* this point picks the key up automatically from
   `ansible-private`, no extra step needed. This whole key is the same
   necessary-bootstrap-exception category as Komodo's own manual first start —
   nothing better exists yet at this point in the sequence.

2. Create a Semaphore **Project** (top-level container — Key Store, Repository,
   Inventory, Variable Groups, and Templates all live inside one). Name it
   `fleet-provisioning`, not `ansible` — the Project itself isn't the `ansible` repo,
   it's Semaphore's own container for the things that run it, and naming it `ansible`
   would collide with three other things named `ansible` one level down inside it:
   the `ansible` Repository (step 4), the `ansible` service account it connects as,
   and the `ansible-bootstrap-key` credential (step 3).

3. Inside that Project, go to **Key Store → New Key**:
   - **Name**: `ansible-bootstrap-key`.
   - **Type**: `SSH Key`.
   - **Username**: `ansible` (the service account from step 1).
   - **Private Key**: paste the *private* half generated in step 1.

4. Go to **Repository → New Repository**:
   - **Name**: `ansible`.
   - **URL**: `https://github.com/myah-mitchell/ansible`.
   - **Branch**: `main`.
   - **Access Key**: `None` — `ansible` is public now (unlike when this doc was first
     written), so no deploy key is needed, the same as `docker-stacks`'s own
     Repository entry in step 11. `dotfiles` doesn't need a Repository entry at all —
     its own Ansible role clones it directly over plain HTTPS, no credential needed,
     since `myah-mitchell/dotfiles` is public too.

5. Go to **Inventory → New Inventory**:
   - **Name**: `ansible-fleet`.
   - **User Credentials**: `ansible-bootstrap-key` from step 3.
   - **Type**: `Static YAML`.
   - Paste `ansible-private`'s real `hosts.yml` content directly into the editor —
     Semaphore stores it inline, it doesn't clone it from a repo. This is the *real*
     inventory (the one with your actual hosts/IPs), not the sanitized example that
     ships inside the public `ansible` repo.

6. Go to **Variable Groups → New Group** (labeled "Environment" in older
   Semaphore versions/docs — same `{}`-icon resource, same underlying API, just
   renamed in the sidebar). Name it `ansible-private`. It has two tabs (**Variables**,
   **Secrets**), and **each of those tabs is itself split in two** — read this part
   carefully, it's not obvious from the UI alone:
   - **Extra Variables** (top section of each tab, with a JSON/Table toggle): passed
     to `ansible-playbook` as `--extra-vars` — real Ansible variables, exactly like
     what `group_vars/all/private.yml` provides today. **This is where everything
     from that file goes.**
   - **Environment Variables** (bottom section of each tab): set as plain OS
     environment variables on the `ansible-playbook` process — a completely
     different namespace that Ansible never sees as a Jinja variable unless a role
     explicitly calls `lookup('env', ...)`. None of `provision.yml`'s roles do that
     for these values (they reference `{{ node_exporter_password }}` etc. directly).
     **Leave this section empty.** Anything put here silently does nothing — the
     playbook run won't error, it'll just keep using the `CHANGEME`/blank defaults
     as if the value was never set.

   With that distinction clear, split `ansible-private`'s
   `group_vars/all/private.yml` content across the two tabs' **Extra Variables**
   sections only:
   - **Secrets tab → Extra Variables**: everything that's an actual credential —
     `ansible_private_repo_token`, and, once you've picked a real value,
     `node_exporter_password` (see step 7). Add each as a name/value pair.
   - **Variables tab → Extra Variables**: everything else from that same file that
     isn't sensitive — `admin_ssh_public_keys`, `ansible_ssh_public_keys`,
     `client_ssh_public_keys`, `komodo_core_address`, `komodo_core_public_key`,
     `ca_certificates`, `client_account`, etc. Easiest done via the **JSON** editor
     toggle rather than re-entering every field as a table row:
     1. On the machine where `ansible-private` is checked out, convert
        `group_vars/all/private.yml` to JSON and drop the two keys that belong in
        the Secrets tab instead (`ansible_private_repo_token`,
        `node_exporter_password`) — `yq` does both in one pass:

        ```bash
        cd /path/to/ansible-private
        yq -o=json 'del(.ansible_private_repo_token, .node_exporter_password)' \
          group_vars/all/private.yml
        ```

        No `yq`? Use Python instead:

        ```bash
        python3 -c "
        import yaml, json
        data = yaml.safe_load(open('group_vars/all/private.yml'))
        data.pop('ansible_private_repo_token', None)
        data.pop('node_exporter_password', None)
        print(json.dumps(data, indent=2))
        "
        ```
     2. Check the output: it should be a single JSON object of the remaining
        top-level keys (`admin_ssh_public_keys`, `komodo_core_address`, etc.), and
        it must **not** contain `ansible_private_repo_token` or
        `node_exporter_password` — those two only go in the Secrets tab (above).
     3. Add one more key that isn't in `private.yml` at all:
        `"server_password": ""`. `provision.yml` declares `server_password` as a
        `vars_prompt` (play-level, evaluated before any `--tags` filtering), so
        Semaphore's non-interactive run needs a value for it even though it's only
        ever consumed by `roles/users/tasks/user_root.yml`/`user_client.yml`/
        `user_admin.yml` (`when: server_password | length > 0`), none of which run
        under this template's `monitoring` tag. An empty string matches the same
        re-run convention already used in
        `roles/pve/templates/cloudinit-vendor.yml.j2`.
     4. In Semaphore, open `ansible-private` → **Variables** tab → **Extra
        Variables**, click the **JSON** toggle (next to the Table toggle at the top
        of that field), and paste the object in place of the empty `{}`.
     5. Save the Variable Group.

7. Go to **Task Templates → New Template**, choose the **Ansible Playbook** app:
   - **Name**: `provision-monitoring` (or similar).
   - **Playbook Filename**: `provision.yml`.
   - **Repository**: `ansible` (step 4).
   - **Inventory**: `ansible-fleet` (step 5).
   - **Variable Groups**: `ansible-private` (step 6).
   - **Tags**: `monitoring` — **not** `docker`. `node_exporter_password` is consumed
     by `roles/monitoring/tasks/node-exporter.yml`, gated behind the `monitoring` tag
     in `provision.yml`'s role list, not `docker`. This template does **not** need a
     `komodo_onboarding_key` override baked in: each host's onboarding key is
     single-use and generated fresh right before that host's own provisioning run
     (step 5), never stored in `ansible` or Semaphore itself.
   - **Survey Variables** (Template edit → **Survey Variables** tab): `provision.yml`
     also declares `target`, `short_name`, `abbr_name`, `location_abbr`, and
     `domain_name` as `vars_prompt` — same play-level, before-tag-filtering
     situation as `server_password` above, but these four/five are genuinely
     host-specific, so they don't belong baked into the shared `ansible-private`
     Variable Group (that group should stay reusable across every host you ever
     point this Template at). Add each as a Survey Variable instead — type
     **String**, **Required** — which makes Semaphore prompt for them on every
     run, the same way the interactive CLI prompt already does:
     - `target`: the host or group name from `ansible-fleet`'s `hosts.yml` to run
       against (e.g. `ci01`).
     - `short_name`, `abbr_name`, `location_abbr`, `domain_name`: the same
       identity values used for that host's original provisioning run. None of
       them are actually read by `roles/monitoring/`, but the prompt still fires
       for all four regardless of the `monitoring` tag.
   - Before running it the first time, pick a real `node_exporter_password` and add
     it to the `ansible-private` Variable Group's Secrets tab (step 6) — and, for
     durability across future re-provisions and fresh hosts, commit that same real
     value to `ansible-private`'s `group_vars/all/private.yml` too, the same
     "commit the real value directly to `ansible-private`" pattern used for
     `komodo_core_public_key` in `docs/komodo-bootstrap.md` step 13.

8. **This role is not idempotent for a password rotation — read before running.**
   `roles/monitoring/tasks/node-exporter.yml` only writes `/etc/node-exporter/config.yml`
   `when: not node_exporter_config.stat.exists`. Every host provisioned before this
   point already has that file, baked from the `CHANGEME` default. Running this
   Template against them fixes nothing silently — no error, the task just reports
   "skipped." On each already-provisioned host (`ci01` included), delete the stale
   config first, then run the Template:

   ```bash
   sudo rm -f /etc/node-exporter/config.yml
   sudo systemctl restart node_exporter
   ```

   Hosts provisioned *after* you've fixed `node_exporter_password` in
   `ansible-private` never hit this — they get the real password on their very first
   run, `config.yml` never exists with the `CHANGEME` hash to begin with.

9. **Superseded in Phase 7**: once step-ca's SSH CA is live, switch Semaphore to a
   dedicated `semaphore` service principal using a short-lived, auto-renewed step-ca
   cert instead of the static key from step 1 — don't skip this once that phase
   lands.

## What's next

`ci01` now runs Semaphore, and Semaphore can push real shared secrets
(`node_exporter_password`, anything else added later) to the rest of the fleet
instead of hand-editing `ansible` per host. `tf01` is next; see
[`docs/overview.md`](overview.md) for the running order. Its own bootstrap doc
doesn't exist yet — write it when you get there, following this doc's shape (steps
1–4 provisioning are identical for every VM; step 5's onboarding-key step is required
for *every* future host, not just this one — Semaphore doesn't remove it, since it's
a permanent per-host PKI-onboarding action, not a bootstrap-phase gap; step 9's
`traefik-bootstrap` deploy is the same pattern for every VM until `system-agent`
replaces it fleet-wide; steps 10–12 registering/deploying its specific stack will
differ).
