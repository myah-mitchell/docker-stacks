# Hosting Cluster Buildout — Plan & Status

**Purpose of this file**: a single, cold-start-readable status document for the
multi-repo infrastructure buildout described in full detail in the working plan at
`C:\Users\MyahMitchell\.claude\plans\i-want-work-out-zippy-iverson.md` (that file has
the complete phase-by-phase design rationale — "What got cut and why", full
architecture diagrams, verification steps per phase; this file is the **status
tracker + decisions log + handoff notes**, not a replacement for it). If you're
picking this project up with zero prior context, read this file top to bottom before
touching anything.

Spans **three repos**: `docker-stacks` (this one), `ansible` (`/opt/ansible` — moved
here from `C:\Users\MyahMitchell\GitHub\ansible`, and now **public**, see decision
#20), and `ansible-private` (`C:\Users\MyahMitchell\GitHub\ansible-private` — a small
private overlay of just `hosts.yml`/`group_vars/all/private.yml`, new as of decision
#20). The old standalone `proxmox-cloud-init` repo is **deprecated** — its
cloud-init template/vendor-script content is now templated directly inside
`ansible`'s `pve` role; nothing in this plan references it as a live dependency
anymore.

**Nothing has been deployed to a real server yet.** Everything below marked "built"
is committed-or-committable code/config, validated as far as YAML/syntax parsing and
(where possible) actually running the repo's own tooling — never against a live
host, live Docker daemon, or live Ansible run. See "How this was validated" near the
bottom.

---

## ⚠️ Uncommitted work — read this before doing anything else

As of this pass: **`docker-stacks` is clean and pushed (`PLAN.md` itself stays
untracked/unpushed, deliberately, per your standing instruction); `ansible` is clean
and pushed, now living at `/opt/ansible` and public, with a fair number of commits
since this file last looked (warning cleanup, node-exporter FQDN fix, docker apt
cache fix, ssh figlet dependency, komodo remote_tmp fix — none of those needed a
`docker-stacks` doc change, only decision #20's ansible-public/cloud-init-merge work
did); `ansible-private` is clean; `proxmox-cloud-init` has real, genuinely
uncommitted local changes rewriting it into a deprecation stub (README pointing at
`ansible`, `cloudinit-vendor.yml`/`create-cloud-init-template.sh` reduced to
Jinja-templated versions of what `ansible`'s `pve` role now renders) — **not made by
this session**, found already sitting in the working tree; not committed on your
behalf, flag it back to you rather than assume the wording's final; `dotfiles` still
has real uncommitted work (`install.sh`'s `cargo-binstall` fix, `CLAUDE.md`), from a
much earlier session, still unreviewed.** If you're resuming cold, still check
`git status`/`git log origin/main..HEAD` in each repo before assuming the state
described here matches HEAD — this note is a snapshot, not a guarantee:

- **`docker-stacks`**: clean, pushed to `origin/main` at `0bf6e3a` before this
  session's decision #20 doc edits (`README.md`, `containers/komodo/stack-README.md`
  + regenerated `stacks/komodo-server/README.md`, `docs/komodo-bootstrap.md`,
  `docs/ci01-bootstrap.md`) — those are made, not yet committed as of this note; see
  decision #20 above for exactly what changed and why.
- **`ansible`**: clean, pushed to `origin/main` at `7751723`, now **public** (see
  decision #20) and checked out at `/opt/ansible`, not the old
  `C:\Users\MyahMitchell\GitHub\ansible`.
- **`ansible-private`**: clean, pushed — new as of decision #20, holds the real
  `hosts.yml`/`group_vars/all/private.yml` that used to live directly in `ansible`.
- **`proxmox-cloud-init`**: **deprecated as of decision #20**, superseded by
  `ansible`'s `pve` role. Has real uncommitted local changes right now (see above) —
  not this session's doing, not committed by this session either.
- **`dotfiles`**: modified `install.sh` (the `cargo-binstall` fix) and `CLAUDE.md` —
  **still uncommitted**, untouched since the session first described below.

`dotfiles`'s pending changes still haven't been reviewed/committed. **Real
infrastructure now exists**, unlike when most of this doc was written: a PVE host is
up with storage configured, `ansible` has been run against it, and its cloud-init
Ubuntu template has been built. **2026-08-23: all VMs were wiped and the fleet is
being rebuilt from scratch** — PVE host/storage/template are assumed to still stand
(not confirmed), but no VM currently exists, `km01` included. This is a clean restart
of `docs/komodo-bootstrap.md` with the v2 PKI auth flow (decision #19) already in
place from the start, not a migration — nothing to reconcile from the old passkey
model. User is running the bootstrap by hand and will report issues as they come up;
see the latest session log entry for whatever's been debugged so far this pass.

### Session log — 2026-08-15/16

Picked up cold via this file, then went spelunking in `proxmox-cloud-init` (not
previously covered by this doc) and found/fixed several real bugs, plus updated SSH
keys across both `ansible` and `proxmox-cloud-init`:

- **`proxmox-cloud-init`** (2 commits, pushed):
  - `create-cloud-init-template.sh`: added `set -euo pipefail` (a failed `wget`/`qm`
    step was silently continuing all the way to `qm template`, turning a broken VM
    into a "template"); made `qm destroy $VMID` explicitly tolerate failure (expected
    on a VMID's first-ever build, would otherwise now abort under `set -e`); `rm -f`
    on the stale-image cleanup.
  - Same file: added the `morsadmin` key alongside the legacy `m0rsla-20240421` key
    in the baked-in cloud-init root `SSHKeys`, matching what Ansible's
    `user_root.yml` sets **exclusively** on root right after first boot — they'd
    drifted out of sync.
  - `cloudinit-vendor.yml`: the commented-out second `runcmd` line wasn't actually a
    comment — it was YAML-folded into the `git clone` item's plain scalar (only
    harmless by accident, since it starts with `#`, a shell comment). Moved to a
    real top-level comment so a future edit can't silently corrupt the clone command.
  - **Considered, then explicitly rejected**: initially "fixed" the committed
    GitHub PAT in `cloudinit-vendor.yml` by swapping it for a deploy key +
    split tracked-template/gitignored-real-file setup. Reverted in full — the PAT
    is fine as-is (fine-grained, scoped to exactly the two repos it needs, private
    repos, no write access, "if you can read the repo you can already see what it
    unlocks"). The file this deploys **must** stay byte-identical between git and
    Proxmox's snippet storage; there's no human in the loop to run a render step.
    Don't re-litigate this without new information (e.g. the PAT actually leaking
    outside your control, or these repos going public — see next point).
  - Noted for later, not acted on: you're considering eventually making `ansible`
    and `proxmox-cloud-init` public, at which point the PAT goes away entirely
    (public read access needs no credential).
- **`ansible`** (2 commits, pushed):
  - `roles/pve/tasks/pve-cloudinit.yml`: the weekly "Recreate Cloud-Init Template"
    cron job ran `/usr/local/bin/create-templates.sh`, but the same playbook installs
    the script as `/usr/local/bin/create-cloud-init-template.sh` (post-rename). This
    mismatch existed since the cron task was first added — it has never once run
    successfully. Fixed.
  - `roles/dotfiles/defaults/main.yml` (part of the same first-ever commit of this
    role, so no "buggy then fixed" history): repo URL pointed at `MyahMitchell`
    (no hyphen) — not a real GitHub account, confirmed 404. Real one is
    `myah-mitchell`. Also switched from SSH+deploy-key to plain HTTPS with no
    credential at all, since `myah-mitchell/dotfiles` is actually **public** — the
    deploy-key machinery this role's comment and `semaphore/stack-README.md`
    described was unnecessary complexity for a repo that needs zero auth. And
    `dotfiles_target_user` now resolves through `{{ client_account|lower }}` at its
    one source point, matching `user_client.yml`'s account-creation casing (was
    previously only correct by coincidence, since the default happens to already be
    lowercase).
- **`docker-stacks`** (`containers/semaphore/stack-README.md`, now committed):
  simplified to match — only `ansible` needs a Semaphore Repository/deploy-key
  entry, `dotfiles` needs none. `stacks/semaphore-server/README.md` regenerated to
  match via `scripts/build.py`.

### `docker-stacks` code review + full commit-out — same session, later pass

Ran a high-effort `/code-review` pass (2 background sub-agents, ~16 min, 77 tool
calls) across everything that was sitting uncommitted in `docker-stacks`. Verified
the sharpest findings against primary sources (upstream Dockerfiles, cloudflared's
own GitHub issue/PR history) rather than guessing. 9 findings, all fixed:

- **`containers/cloudflared/config/config.yml.example`** — the example ingress rule
  pointed at `http://traefik-dmz-traefik:80`, but every `traefik-*` stack's
  `komodo.env` templates `PROJECT_NAME` to the literal `traefik` (safe since these
  stacks never share a Docker host), not a folder-matching name — real container is
  `traefik-traefik`. Would have 502'd every request through the tunnel. **Most
  severe finding — would have broken the entire public edge.**
- **`containers/cloudflared/compose.yaml`** — healthcheck used `wget`; the official
  image ships neither `wget` nor `curl`. Switched to the native
  `cloudflared tunnel --metrics <addr> ready` subcommand (confirmed against
  cloudflared PR #1135, which added it for exactly this reason).
- **`containers/mailrise/compose.yaml`** — healthcheck used `nc`; the image is built
  FROM `python:3-slim`, no netcat. Switched to a `python3` socket check for the SMTP
  220 greeting.
- **`containers/uptime-kuma/compose.yaml`** — healthcheck used `wget`; the
  non-alpine 1.23.16 image's Debian base only installs `curl` (confirmed against
  upstream `debian-base.dockerfile`). Switched.
- **`containers/ntfy/compose.yaml`** — `NTFY_BASE_URL` omitted `${SUB_DOMAIN_NAME}`,
  inconsistent with this stack's own Traefik `Host()` rules and the repo's
  established pattern (e.g. komodo's `KOMODO_HOST`). Fixed.
- **`containers/vector/stack-README.md`** — a stray, unfenced duplicate block
  referencing a `WebProxy` UFW app that's never defined anywhere in the fragment
  (leftover copy-paste; an earlier `WebProxy`→`Node-Exporter` rename missed this
  second occurrence). Removed; regenerated the merged `victoriametrics-agent`/
  `victoriametrics-server` READMEs to match.
- **`docs/build-guide/00-overview.md`** — still said to register both `ansible` and
  `dotfiles` as Semaphore Repository entries, contradicting the
  `semaphore/stack-README.md` fix above. Corrected.
- **3 hand-edited stack `compose.yaml` files** (`authentik-server`, `komodo-server`,
  `traefik-dmz`) — still carried CRLF under `core.autocrlf=input` while every other
  stack in the repo is plain LF, burying real logical changes (~9-12 lines each)
  under ~150-line line-ending noise in any diff. Normalized to LF.
- **`stacks/step-ca-server/compose.yaml`** — declared an unused `frontend` Docker
  network that no service attaches to, unlike `backend`/`socket_proxy` which were
  already correctly commented out in the same file. Commented out too.

**Commit history note, in case it looks unusual in `git log`**: the first attempt at
committing all this split each component's fix from "the rest of its files" (e.g.
cloudflared's bugfixed `compose.yaml` in one commit, its `README.md`/`komodo.env`/etc.
in a separate later one) and grouped the remaining leftovers into ad-hoc
"Phase N: ..." commits, including one for `stacks/system-agent` that didn't actually
belong to any phase. Both were correctly called out as bad history and undone via
`git reset --soft` back to the pre-session baseline (nothing had been pushed yet, so
this was safe) and redone as this final set of 19 commits — one per
container/stack/concern, each containing that component's complete, already-correct
state, no phase numbers, messages describing the actual reasoning. `git log
--oneline` from `cab0ede` (add blackbox-exporter) through `805add9` (add
system-agent) is the real, final history.

### Session log — 2026-08-16/17 (continued)

Picked back up cold via this file. Two distinct passes:

**Domain scrub + secrets restructuring.** Real domain names (`mors.io`/`sokep.com`)
had leaked into several committed files' comments/prose. Rewrote history with
`git filter-branch` (non-interactive — `git rebase -i` isn't supported in this
sandbox) across every commit since the 19-commit baseline, replacing them with
`example.internal`/`example.com` and deleting `docs/build-guide/00-overview.md`
entirely (per your instruction — it just needed to go, not be genericized).
Force-pushed the rewritten history. Separately, audited the blanket
`containers/*/config/*` `.gitignore` rule added earlier — found it had never actually
protected anything real (the one file that would've held a real secret, `mailrise`'s
`mailrise.conf`, was already never committed) while silently breaking `git add` on
dozens of already-tracked legitimate files. Removed the rule; restructured
`cloudflared`, `mailrise`, and (in the second pass, below) `komodo` to keep real
secrets in a dedicated `secrets/` folder instead — `config/` now never holds one, by
construction, not by `.gitignore`.

**`vm-komodo` bootstrap — the first real deployment this whole plan has had.** You
got a PVE host up with storage configured, ran `ansible` against it, and built its
cloud-init Ubuntu template — the actual trigger for this pass. Wrote
`docs/komodo-bootstrap.md`, the step-by-step runbook for the one stack that has to be
brought up by hand (Komodo can't GitOps-deploy itself the first time), then
iterated on it against your real host as you actually worked through it — several
real gaps/bugs only surfaced this way, not from a syntax-level read of the repo:
- The `proxy` Docker network is declared `external: true` in *every* stack's
  `compose.yaml`, including `traefik-server`'s own — nothing creates it, so it has to
  exist on a host before that host's first stack can start. Wasn't documented
  anywhere.
- `containers/komodo/config/core.config.toml` was mounted straight from the
  git-tracked `config/` folder, but pointing Komodo at a private repo means putting a
  real token in it — same class of bug as the cloudflared/mailrise one above, found
  by actually trying to do it. Moved to `secrets/core.config.toml`
  (`config/core.config.toml.example` kept as the unmodified upstream reference).
- A hand-typed password containing `@` broke `FERRETDB_POSTGRESQL_URL`'s raw
  string-interpolated connection string and failed as a confusing DNS-resolution
  error against the wrong host, not an obvious auth error — root-caused live, not
  guessed at. Directly motivated the alphanumeric-only rule now spelled out (with the
  actual entropy math for why it costs nothing) in the root `README.md`.
- `POSTGRES_USER`/`KOMODO_DB_USERNAME` and `POSTGRES_BACKUP_*`'s blank-vs-set rules
  in the generated `.env` weren't obvious from reading the files — confirmed the
  actual `build.py` cross-reference behavior by testing it directly rather than
  trusting a read of the code, since a first pass at reasoning through it turned out
  wrong.
The runbook was rewritten at least twice for ordering/clarity after you flagged steps
that referenced things not yet introduced — final version is strictly linear, each
step assumes only the steps before it. `vm-komodo` bootstrap is **in progress**, not
complete — last known state is the `@`-in-password bug found and understood; not yet
confirmed the stack is fully up and healthy end-to-end.

**Naming convention overhaul.** The placeholder domain from the history rewrite
(`example.internal`/`example.com`) got superseded by your real one —
`myah-mitchell.com` is explicitly safe to commit (same name as the GitHub account
this repo lives under). Replaced the old `h1`/`d1`-site-prefixed hostname pattern
(`h1km01.h1.mors.io`) with a simpler one: `<role><NN>` hostnames with no site prefix
(`km01`), site encoded separately as a sub-domain (`home.`/`cloud.`), see the table
below. Swept every committed doc/example config that referenced the old pattern.
Also documented (in `scripts/base-komodo.env`'s field comment, propagating to every
stack's `komodo.env`) that `SUB_DOMAIN_NAME`'s trailing dot is part of the value
itself, not templated in anywhere — leaving it blank is the correct, safe way to drop
it for a public/external hostname, confirmed by nothing in this repo needing special
logic to strip a dot that was never there.

Also bumped `build.py`'s auto-generated DB passwords from 16 to 48 alphanumeric
characters, and added a second 96-character bucket for other self-issued app secrets
(`_PASSKEY`/`_SECRET_KEY`/`_LAPI_KEY`) that were previously left blank with no
generation logic — deliberately excluding externally-issued credentials
(`_API_KEY`/`_API_TOKEN`/`_LICENSE_KEY`) and format-restricted ones
(`_KEY_ENCRYPTION`), which stay manual. Considered and explicitly rejected adding
randomness to DB usernames (`<service>-admin-<random>`) and adding symbols to
passwords — neither would raise the bar against any real threat model here (DBs
aren't network-exposed; 48 alphanumeric chars is already ~286 bits, past AES-256),
and symbols specifically would reintroduce the exact URL-parsing bug found above.

Finally, added a proper entry-point doc: the repo had none explaining the plan/layout/
conventions to someone landing cold (this file is deliberately uncommitted). The
existing root `README.md` was actually a different, narrower thing — a per-stack
"what does each compose file do" reference — so that got moved to
`docs/stacks-overview.md` as-is, and a new Start Here doc took its place at the root
(where GitHub actually renders it). **Near-miss along the way**: initially drafted
the new doc by overwriting the existing root `README.md` directly without reading it
first — caught before anything was lost, restored from git, redone as described
above. Worth remembering: check what a file actually contains before writing over it,
even when fairly confident it's empty/placeholder.

**`docs/komodo-bootstrap.md` step 12 expanded, and a naming cleanup.** Step 12
("point Komodo at this repo for future deploys") only sketched the idea; expanded it
into a real numbered walkthrough (register the target VM as a Komodo Server resource
via Periphery first, then create the Stack resource, source/files/environment
config, deploy, verify). Also caught and fixed leftover `vm-komodo`/`vm-traefik-hub`/
etc. placeholder names throughout the whole doc (steps 1–13) — these predated the
naming-convention overhaul above and were never actually defined anywhere; replaced
with the real `<role><NN>` hostnames (`km01`, `tf01`, `ci01`, `id01`, `pk01`, `bh01`,
`ap01`) consistently.

**Every-VM-gets-local-Traefik architecture, worked out from your correction.** You
pointed out every VM should run its own Traefik for VM-to-VM TLS, using
`traefik-kop` + `tf01`'s Redis so each host can opt individual services into
central/DMZ visibility rather than everything being centrally routed. This resolved
what had been an open question about `stacks/system-agent`'s purpose (decision #14)
and surfaced two more real decisions: dockns needs to drive internal DNS aliasing
directly (decision #5, corrected), and internal Traefik instances should get their
certs from step-ca rather than Let's Encrypt, with `bh01` as the sole exception since
it's the actual internet-facing host (decision #15). Also corrected a stale claim in
this file's own "known open questions": there is no `internalca` resolver scaffolded
in `containers/traefik/compose.yaml` — checked the file and its full git history,
never existed. That work (the new ACME resolver, making the certresolver per-VM) is
real, not-yet-started follow-up, not something to assume is half-done.

**dockns: Technitium → UniFi provider swap, and a stale-source near-miss.** Initially
looked up `dockns`' supported DNS backends via its Docker Hub page and reported back
that it had no UniFi option — wrong, and corrected directly by you: you wrote the PR
that added UniFi support to `dockns` yourself, and Docker Hub's description was
stale. Found the real source (`codeberg.org/BrenekH/DockNS`) and its
`docs/name-servers/unifi.md` directly rather than continuing to guess, confirmed the
exact env vars (`DOCKNS_NS_UNIFI_SERVICE`/`_HOST`/`_API_KEY`/`_ACCOUNT_ID`), and asked
you to choose between UniFi's local vs. remote (cloud API) connector before writing
anything — you picked local (per-site console, doesn't depend on UniFi's cloud API
for internal DNS). Replaced `containers/dockns/compose.yaml`'s and `komodo.env`'s
Technitium block with the UniFi one (same shape — `RECORD_DEFAULTS_TTL`/
`RECORD_DEFAULTS_CNAME_TARGET_DOMAIN` — swapped provider, not redesigned), documented
per-site setup in `stack-README.md`, and regenerated `stacks/system-agent` (the only
stack that includes `dockns`) via `build.py`. Worth remembering: a package's own
Docker Hub/marketplace description can be stale even when the underlying project has
moved on — check the actual source repo before reporting a capability gap as fact,
especially when the user might know the project better than any doc you can find.

**Periphery investigation — corrected a wrong assumption before building a duplicate,
twice.** Asked to "build Periphery agent into the ansible build," on the assumption
it wasn't there — checked the real `ansible` repo on disk first instead of assuming:
it's already there, `roles/docker/tasks/komodo.yml`, gated by `KOMODO: true`, already
set for every VM in the `ubuntu_docker` group every VM in this plan provisions from.
Reported that back; asked again anyway in a follow-up message, so re-confirmed and
pointed at the exact file/line rather than just re-asserting it. Never built anything
duplicate. What's actually real: `roles/docker/defaults/main.yml`'s
`komodo_passkeys: ["CHANGEME"]` has no override mechanism (no `group_vars/` directory
exists in that repo yet, despite a comment elsewhere implying one was intended), and
`km01` itself was provisioned before its real `KOMODO_PASSKEY` existed — so its live
Periphery almost certainly still has the placeholder baked in.

**Resolved into decisions #16/#17** (both finalized this pass, not left open):
`CHANGEME` stays a permanent committed placeholder in `ansible` — no vault
infrastructure gets built — and real values get pushed by Semaphore once it exists.
Getting Semaphore up hits its own chicken-and-egg (deploying it *through* Komodo onto
`ci01` needs `ci01`'s passkey already fixed, but fixing passkeys fleet-wide was the
whole point of standing Semaphore up) — resolved by fixing `ci01`'s passkey by hand,
once, the same way `km01`'s needs fixing too, rather than building vault
infrastructure just to avoid that one manual step. Wrote
[`docs/ci01-bootstrap.md`](../docs/ci01-bootstrap.md) covering the whole thing for
real: provisioning, the manual passkey fix, registering `ci01` as a Komodo Server,
deploying `stacks/semaphore-server` (including its own not-auto-generatable secrets —
`SEMAPHORE_COOKIE_HASH`/`_ENCRYPTION`/`_ACCESS_KEY_ENCRYPTION`, base64 32-byte keys,
excluded from `build.py`'s generator by design), a first-access method for a stack
with no direct port and no working auth chain yet (SSH tunnel straight to the
container's own Docker-network IP — general enough to note as the fallback for
*any* stack before `id01` exists, not just this one), and wiring Semaphore to the
`ansible` repo per `containers/semaphore/stack-README.md`'s already-existing
Key-Store/Repository/Project/Template instructions, ending in a Semaphore Template
that becomes the real fix for every `CHANGEME` after `ci01`.

Split the documentation to match: `docs/komodo-bootstrap.md` now covers only `km01`'s
own steps 1–11 — its old step 12 (the generic "register a Server, deploy a Stack"
walkthrough, written in the abstract for a `tf01` that doesn't exist yet) and step 13
(folding `km01`'s own UI behind Traefik+Authentik, still genuinely future work) were
replaced with a short closing section pointing forward instead. Added
[`docs/overview.md`](../docs/overview.md) as the index — running order, one row per
VM, links to each host's doc as it gets written — linked from both
`docs/komodo-bootstrap.md`'s new closing section and the root `README.md`.

**Swept for the naming-convention overhaul's stragglers while in here.** The repo-wide
`vm-komodo`/`vm-traefik-hub`/etc. → `<role><NN>` rename from the earlier session
turned out to have missed a few spots outside `docs/komodo-bootstrap.md`: the root
`README.md` itself (twice — its own "Where to go next" section and the
external-vs-internal-hostname example), `containers/cloudflared/stack-README.md` and
`compose.yaml` (`vm-edge` → `bh01`), and `containers/step-ca/README.md`
(`vm-pki-stepca` dropped as redundant with the hostname already given). Re-ran
`build.py` afterward and re-grepped the whole repo for every old `vm-*` name — clean
outside `PLAN.md` itself, where they're accurate as historical narration, not current
state.

### Session log — 2026-08-22

Started from a plain question — does Komodo support certificate verification instead
of the Komodo Passkey — which turned into checking upstream directly rather than
answering from memory: `ghcr.io/moghtech/komodo-core:latest` (already pinned
everywhere in this repo) shipped v2 back in March 2026, and passkeys are now
explicitly deprecated legacy compatibility, replaced by per-host Ed25519 keypairs +
a Noise-protocol handshake. Confirmed against the real upstream `periphery.config.toml`/
`core.config.toml` and the `komo.do` docs (Advanced Setup, Connect More Servers)
rather than guessing at field names.

Since `km01` has never actually come up successfully (its `.env` on disk was a
leftover from an earlier attempt, gitignored, never pushed anywhere), this was the
moment to switch — before any real secret, host, or fleet-wide value existed to
migrate. You picked the shape directly: **outbound** Periphery→Core connections
(Periphery dials out, no inbound port/UFW rule needed on any VM ever), and **manual,
one-time-per-host key exchange**. That second choice turned out to map onto Komodo's
own documented onboarding-key flow better than the "paste a public key in after the
fact" pattern originally offered as the alternative — a fresh, short-lived onboarding
key generated by hand right before each host's provisioning run, passed as a runtime
Ansible `-e` var, never committed, discarded after first connect. Refined and
confirmed this reconciliation with you before writing anything.

Wrote up the full change as decision #19 (see there for the concrete file list) and
split decisions #16/#17 to separate what's actually resolved by PKI (Komodo's own
Core↔Periphery trust — no more `CHANGEME`-forever placeholder needed at all, since
Core's public key isn't secret) from what's unchanged (`node_exporter_password`
still needs Semaphore's real shared-secret-push mechanism, decision #16's original
reasoning). Rewrote `docs/komodo-bootstrap.md` (new step 10: open the firewall for
Core — outbound mode flips which host needs the inbound rule, from every Periphery
to just `km01`'s port 9120; new step 13: get Core's public key) and
`docs/ci01-bootstrap.md` (step 5's manual passkey fix became generating an
onboarding key; step 8's manual Server-registration became confirming the
onboarding key already created one; step 14's Semaphore Template no longer carries a
`komodo_passkeys` override) to match, plus `ansible`'s `roles/docker/defaults/main.yml`/
`tasks/komodo.yml` (new `komodo_core_address`/`komodo_core_public_key`/
`komodo_onboarding_key`/`komodo_connect_as` vars; dropped `komodo_passkeys`/
`komodo_allowed_ips`/all three UFW tasks) and `containers/komodo/compose.yaml` (added
a persistent `/config/keys` volume — a real, easy-to-miss gap this pass caught: Core's
auto-generated private key had nowhere to survive container recreation, which would
silently break trust with every Periphery agent in the fleet).

**Left deliberately unverified, flagged inline at each spot rather than asserted as
fact** — none of this has ever run against a real Komodo instance: exactly where
Komodo's UI/API surfaces Core's own public key; whether an onboarding key actually
auto-creates its Server resource on first connect, or a Server still needs manual
creation first; whether outbound+onboarding-key periphery needs `core_public_keys`
pinned explicitly too, on top of the onboarding key itself. Confirm and correct these
the first time `km01`/`ci01` are provisioned for real — don't treat the docs' current
wording on these three points as settled.

**Caught in a same-session follow-up, by you, not found independently**: outbound
mode means it's now `km01` that needs an inbound firewall rule (port 9120), not the
other VMs — I'd removed Periphery's now-obsolete inbound UFW rule but hadn't added
one for Core, since Core isn't `ansible`-managed at all (it's the hand-bootstrapped
compose stack). Added as `docs/komodo-bootstrap.md` step 10; while in there, also
noticed and documented that direct browser access to `:9120` was never firewalled
either, before or after this switch — a pre-existing gap, not something this pass
introduced, just more consequential now that every Periphery needs to reach it too.

---

## Naming & domains (use these everywhere, no exceptions)

**Changed this session** — replaced the old `h1`/`d1`-site-prefixed pattern
(`h1km01.h1.mors.io`) with a simpler one, and switched to the real domain
(`myah-mitchell.com` — explicitly confirmed safe to use in public/committed docs,
same as the GitHub account this repo lives under). Also now committed to the repo
itself (root `README.md`), not just this file — see there for the full table with
worked examples.

| What | Value |
|---|---|
| Domain | `myah-mitchell.com` |
| Sub-domain — home site | `home.` |
| Sub-domain — cloud site (colo) | `cloud.` |
| Hostname pattern | `<role><NN>` — **no site prefix**, e.g. `km01`, `bh01`, `md01` |
| Full FQDN pattern | `<role><NN>.<site>.myah-mitchell.com`, e.g. `km01.home.myah-mitchell.com` |
| External/public (no sub-domain) | bare `myah-mitchell.com`, e.g. `vault.myah-mitchell.com` |
| Pre-existing hosts (dashed, confirmed stale, intentionally left alone) | `h1-bk01`, `h1-mx01`, `h1-vh01`, `d1-vh01`/`02`/`03`, `d1-bk01` — **domain for these specifically is unconfirmed against this new convention**, not touched, see decision #13 |

Role abbreviations: `km` Komodo · `tf` Traefik hub · `ci` core-infra · `id` Authentik/identity ·
`pk` step-ca/PKI · `bh` bastion/edge · `ap` apps/Vaultwarden · `md` media ·
`bk` backup (pre-existing) · `mx` mail gateway (pre-existing) · `vh` hypervisor (pre-existing)

### Planned VM placement

Bootstrap docs live in `docs/` — see `docs/overview.md` for the index and running
order. This table is the status summary; that doc is the authoritative running order.

| Hostname | Purpose | Doc | Status |
|---|---|---|---|
| `km01.home.myah-mitchell.com` | Komodo GitOps engine | `docs/komodo-bootstrap.md` | **in progress** — steps 1–13 followed against a real VM, not yet confirmed fully healthy end-to-end |
| `ci01.home.myah-mitchell.com` | Semaphore (`ansible` runner) first, rest of `core-infra` later | `docs/ci01-bootstrap.md` | doc written, not yet run against a real host — decision #16/#17 |
| `tf01.home.myah-mitchell.com` | central Traefik + Redis master | not written yet | not started — blocked on `ci01`/Semaphore existing (decision #17) |
| `id01.home.myah-mitchell.com` | Authentik | not written yet | not started |
| `pk01.home.myah-mitchell.com` | step-ca | not written yet | not started |
| `bh01.home.myah-mitchell.com` | `cloudflared` + `traefik-dmz`, isolated DMZ VLAN | not written yet | not started |
| `ap01.home.myah-mitchell.com` | Vaultwarden (migrated data) + future self-hosted replacements | not written yet | not started |
| `bk01.home.myah-mitchell.com`? | local + S3 backup target (PBS, existing) | n/a — pre-existing, out of scope for these runbooks | existing, unchanged — hostname shown here is the new-convention target, not confirmed as this host's actual current name |
| `bk01.cloud.myah-mitchell.com`? | offsite backup target (colo PBS) | n/a — pre-existing, out of scope for these runbooks | already staged in `ansible/hosts.yml`, needs a real IP once colo networking exists; same caveat as above |

---

## Decisions log (locked — do not re-litigate without a real reason to revisit)

1. **Dropped NetBird entirely.** Its free tier doesn't support OIDC IdPs (Authentik)
   — that's gated to the paid Team plan. Once the DMZ→Traefik-hub hop was recognized
   as same-site VLAN routing (no VPN needed at all), the only remaining connectivity
   needs were home↔colo backup transport and roaming admin access — both covered
   natively by UniFi gateway features already running at both sites: **Site Magic**
   SD-WAN and **UID Teleport**. No new SaaS account, agent, or Ansible role needed.
2. **Public edge lives at home, not colo.** Colo's reliability doesn't actually
   improve availability of home-hosted backends (a home internet outage takes
   everything down either way), and Cloudflare Tunnel already hides the origin IP
   regardless of which site runs the connector. Colo is scoped to offsite PBS backup
   only.
3. **FreeIPA cut entirely** — would have been a third overlapping identity/trust
   system next to Authentik and step-ca. Replaced with: Authentik as sole
   identity/group source, step-ca SSH certs carrying Authentik group claims as
   principals, Ansible-templated local accounts/`sudoers.d` for authorization.
4. **No shared NFS home directories** — Ansible/chezmoi-style dotfiles sync instead
   (no runtime dependency, no stateful service every login needs).
5. **Technitium cut** — `dockns` drives UniFi's own DNS directly (its `unifi`
   provider, added upstream specifically for this — local connector, one console per
   site) instead of running a separate Technitium instance as a second upstream
   resolver. An earlier test running dockns against Technitium alongside UniFi caused
   real problems: hosts ended up with two upstream DNS providers disagreeing.
   UniFi-only avoids that outright; step-ca can still issue wildcard certs without
   needing wildcard DNS either way.
6. **VM-per-concern only for genuinely trust-critical services** (Authentik,
   step-ca, Vaultwarden, Komodo, Traefik hub). DNS/observability/Semaphore share one
   `ci01` VM — none individually hold high-value secrets, Docker already isolates
   them from each other. This is about where *trust-critical* services live, not
   about which VMs get a local Traefik — see decision #14, every VM gets one of
   those regardless.
7. **step-ca: offline root + online intermediate.** Root key lives as **2
   independent encrypted copies in physically separate locations** — deliberately
   simplified from an earlier Shamir's-Secret-Sharing-across-3-YubiKeys draft, which
   was judged to be insider-threat-grade overhead for a one-admin threat model where
   simple loss, not coercion, is the realistic risk.
8. **Vaultwarden keeps master-password login alongside SSO, never SSO-only** — don't
   make the password vault depend on the identity stack being fully up. This was a
   bug in an earlier draft, not a judgment call.
9. **Notifications**: self-hosted `ntfy` as the single push destination, `mailrise`
   as an SMTP→Apprise bridge for anything SMTP-only (PBS/PVE) — fixes existing
   PBS/PVE notifications currently landing in spam (SPF/DMARC failures against
   Proton), independent of everything else in this plan.
10. **Security monitoring**: no CrowdSec, no Wazuh. Cloudflare handles edge
    WAF/DDoS/rate-limiting for the one public hostname; UniFi CyberSecure covers
    network-level IDS/IPS; targeted `vmalert` rules against existing
    VictoriaMetrics/Logs data cover detection without a new always-on service.
11. **CI/CD**: Komodo for container GitOps (fresh deploy), Renovate for version-bump
    PRs. The new `lint.yml` GitHub Action is validation-only, deliberately **not** a
    step toward replacing Komodo with Actions-based deploys — handing a CI runner
    standing fleet-wide SSH/deploy credentials would undercut the whole point of
    Phase 7's move to short-lived certs.
12. **Naming**: see the table above — the specific values (real domain, `home`/`cloud`
    sub-domains, `<role><NN>` pattern) were revised in the 2026-08-16/17 session, but
    the general rule is unchanged from when it was first locked: applies to every new
    host/domain reference going forward.
13. **Existing dashed hostnames are wrong, but left alone.** `ansible/hosts.yml` has
    real pre-existing dashed hosts (`h1-bk01`, etc.) that predate and contradict the
    current no-dash convention. Confirmed stale by you directly. Renaming a live host
    is a real-infrastructure action, intentionally out of scope for repo-only work —
    not auto-fixed.
14. **Every VM gets its own local Traefik, not just `tf01`.** `stacks/system-agent`
    (pre-existing, `traefik` + `traefik-kop` + `error-pages`/`logrotate` +
    `vmagent`/`vlagent`/`vector` + `dozzle-agent` + `dockns` + `socket-proxy`) is the
    standard per-VM bundle — **known unfinished, needs fixes before it's actually
    deployed anywhere**, not just an open question about its purpose anymore (see the
    2026-08-16/17 session log). Every VM's local Traefik terminates TLS and runs the
    `chain-authentik@file` auth chain for that VM's own services directly — it
    doesn't need `tf01` for that, only for cross-host visibility. `traefik-kop`
    publishes a router into `tf01`'s shared Redis **only** if that specific service
    also carries a `kop-public.traefik.*` label (`containers/traefik-kop/compose.yaml`'s
    `DOCKER_PREFIX: kop-public`) — that's the per-service opt-in for "should this be
    reachable from `tf01`/`bh01`," not a per-VM setting. `bh01` reads everything
    published to that Redis and is the only VM that decides what actually reaches the
    internet.
15. **Internal Traefik certs come from step-ca, not Let's Encrypt — `bh01` is the one
    exception.** Today `containers/traefik/compose.yaml` only has a single hardcoded
    `letsencrypt` resolver (Cloudflare DNS challenge), used unconditionally — verified
    by reading the file and its full git history, there's no `internalca` resolver
    scaffolded anywhere despite an earlier note in this doc claiming there was (that
    note was wrong, corrected below). Making this real needs: a new ACME resolver
    block pointed at step-ca, and the two hardcoded `certresolver=letsencrypt`
    references (dashboard entrypoint, `defaultGeneratedCert`) turned into a per-VM
    variable so `bh01` — the actual internet-facing host — keeps Let's Encrypt while
    every other VM's `system-agent` Traefik uses step-ca. Not started.
16. **`ansible`'s `node_exporter_password` `CHANGEME` default stays a committed
    placeholder permanently — no vault/group_vars override mechanism gets built into
    `ansible` itself.** Real values get pushed by Semaphore instead, once it exists —
    see decision #17. **Superseded for Komodo specifically by decision #19**: this
    decision originally bundled `komodo_passkeys` in with `node_exporter_password` as
    the same class of problem (a real shared secret, permanently `CHANGEME`, fixed by
    hand until Semaphore exists to push it). Before any real Komodo deploy ever
    happened, Komodo itself moved to v2 PKI auth — its equivalent value (Core's
    public key) isn't secret at all, so it just gets committed for real once known,
    no `CHANGEME`-forever/Semaphore-push pattern needed. `node_exporter_password`
    still works exactly as originally decided here; only Komodo's half of this
    decision was replaced.
17. **Semaphore goes up right after `km01`, before `tf01`/`id01`/`pk01` — and
    `docs/komodo-bootstrap.md` stops at step 13.** Reordered specifically to unblock
    `node_exporter_password`'s secret-distribution problem (decision #16) as early as
    possible, rather than hitting it fresh on every subsequent VM. Concretely: `ci01`
    runs only `stacks/semaphore-server` at first (not the full `core-infra` bundle —
    that's deferred, see the "Next steps" resequencing below), and is the first VM
    registered/deployed through Komodo's normal GitOps flow rather than by hand —
    `docs/ci01-bootstrap.md` works that whole pattern out for real. (Its original
    justification also cited a `komodo_passkeys` chicken-and-egg; decision #19
    resolved that separately, via PKI, not via Semaphore — this decision's real,
    still-standing driver is `node_exporter_password` and general future
    secret-push needs.) Also split documentation to match: `docs/komodo-bootstrap.md`
    covers only `km01`'s own steps (steps 10 and 13 — opening the firewall for Core
    and getting its public key for `ansible` — were added later by decision #19, see
    there); the old, since-removed
    step 12's generic "register a Server, deploy a Stack" content moved into
    `docs/ci01-bootstrap.md` as a worked real example instead of staying abstract; a
    new `docs/overview.md` indexes every
    VM's bootstrap doc and its status, linked from both `docs/komodo-bootstrap.md`'s
    closing section and the root `README.md`. Every VM after `tf01` gets its own doc
    written when its turn
    actually comes, not speculatively ahead of time.
18. **`stacks/traefik-bootstrap`**: a temporary, per-VM, self-signed-TLS +
    `chain-no-auth@file` Traefik, deployed on any VM that needs real Traefik routing
    before `pk01`/`id01` exist — replaces the SSH-tunnel-to-container-IP workaround
    `docs/ci01-bootstrap.md` originally used to reach Semaphore's UI. Deliberately a
    **separate** stack, not `system-agent` deployed with override variables (that
    alternative was considered and rejected) — more isolated, no risk of the
    bootstrap-phase config leaking into the real per-VM Traefik once it's ready, at
    the cost of a second stack definition to eventually retire. Landed alongside it:
    `TRAEFIK_AUTH_CHAIN` as an overridable variable
    (`${TRAEFIK_AUTH_CHAIN:-chain-authentik@file}`) on the 10 `compose.yaml` files
    that previously hardcoded the literal `chain-authentik@file` string
    (`alertmanager`, `blackbox-exporter`, `dozzle`, `semaphore`, `technitium`,
    `uptime-kuma`, `victorialogs`, `victoriametrics`, `victoriatraces`, `vmalert`) —
    `chain-no-auth@file` already existed as a real, defined no-op middleware chain
    (`containers/traefik/rules/chain-no-auth.yaml`, pre-existing, just never wired to
    be switchable) before this pass. Doesn't touch or resolve decision #15
    (`containers/traefik/compose.yaml` itself still hardcodes `letsencrypt`) — that's
    the *real*, permanent per-VM Traefik's cert-resolver problem, still separate,
    still not started.
19. **Komodo switched from v1 shared-passkey auth to v2 PKI, before any real deploy
    ever happened.** Triggered by asking whether Komodo supported certificate
    verification as an alternative to the passkey — the real answer turned out to be
    that `ghcr.io/moghtech/komodo-core:latest` (already pinned everywhere in this
    repo) shipped v2 back in March 2026, which replaced passkeys with per-host
    Ed25519 keypairs and a Noise-protocol handshake; passkeys are now explicitly
    deprecated legacy compatibility, not the current mechanism. Since `km01` has
    never actually come up successfully (its `.env` on disk was a leftover,
    gitignored, never-pushed artifact), this was the moment to switch, before any
    real secret or fleet-wide value existed to migrate. Chosen shape: **outbound**
    Periphery→Core connections (Periphery dials out; no inbound port or UFW rule
    needed on any VM, superseding `komodo_allowed_ips` and the UFW-allow task
    entirely), and **manual, one-time-per-host key exchange** via Komodo's own
    onboarding-key flow — generate a short-lived onboarding key by hand in Komodo's
    UI right before provisioning a new host, pass it as a runtime Ansible `-e` var,
    never commit it. This is deliberately *not* decision #17's "Semaphore pushes a
    fleet-wide secret" pattern — it's a smaller, self-expiring, per-host credential,
    closer to approving a new SSH host key than to distributing a shared password,
    and it stays a permanent per-host step, not a bootstrap-phase gap Semaphore later
    closes (see decisions #16/#17's updates above). Core's own public key, unlike the
    old passkey, isn't secret — it gets committed for real into `ansible`'s
    `komodo_core_public_key` once known, no `CHANGEME`-forever placeholder needed.
    Concrete changes: `ansible`'s `roles/docker/defaults/main.yml`/`tasks/komodo.yml`
    (new `komodo_core_address`/`komodo_core_public_key`/`komodo_onboarding_key`/
    `komodo_connect_as` vars, dropped `komodo_passkeys`/`komodo_allowed_ips`/the UFW
    tasks); `containers/komodo/compose.yaml` (dropped `KOMODO_PASSKEY`, added a
    persistent `/config/keys` volume — Core's auto-generated private key has to
    survive container recreation, or every Periphery loses trust); `komodo.env`,
    `docs/komodo-bootstrap.md`, `docs/ci01-bootstrap.md` updated to match. **Left
    genuinely unverified, since no real `km01` exists yet to check against**: exactly
    where Komodo's UI/API surfaces Core's own public key for copying out; whether an
    onboarding key auto-creates its Server resource on first connect (the docs'
    `copy_server`/`tags` onboarding-key options suggest yes) or a Server still needs
    manual creation first; whether outbound+onboarding-key periphery needs
    `core_public_keys` pinned explicitly too. Flagged inline at each spot in both
    bootstrap docs — confirm and correct them the first time this is actually run.
20. **`ansible` went public; `proxmox-cloud-init` deprecated; real data split into a
    new `ansible-private` overlay repo.** Made ahead of restarting the whole fleet
    build from scratch (all VMs wiped, see the 2026-08-23 session note near the top).
    `ansible` no longer needs to be private at all — nothing left in it is a real
    secret once the private data moves out — so cloning it (both by hand and by every
    VM's cloud-init `runcmd`) needs no PAT/credentialed URL anymore, closing the
    "committed PAT in a public-adjacent doc" concern for good rather than just
    managing it. The old standalone `proxmox-cloud-init` repo is superseded: its
    `cloudinit-vendor.yml`/`create-cloud-init-template.sh` are now
    `ansible`'s own `roles/pve/templates/*.j2`, rendered from real Ansible vars
    (`github_user`, `admin_ssh_public_keys`, `ansible_private_repo_token`, etc. — see
    `roles/pve/defaults/main.yml`) instead of hand-edited with real values baked in.
    That repo can be archived/deleted; nothing in this plan treats it as live anymore
    (its git *history* still has the old real PAT in it — a separate cleanup, not
    done here). The real inventory/keys/certs/banner/PAT `ansible` used to carry
    directly now live in exactly two files (`hosts.yml`,
    `group_vars/all/private.yml`) in a new private `ansible-private` repo, applied
    over the public repo's sanitized placeholders either automatically (cloud-init's
    `runcmd`, gated on a real `ansible_private_repo_token` existing) or by hand
    (`ansible/scripts/bootstrap-private.sh`) before running `ansible-playbook`. The
    replacement credential, `PRIVATE_REPO_TOKEN`/`ansible_private_repo_token`, is a
    fine-grained read-only PAT scoped to just `ansible-private` — never committed,
    same posture as every other credential convention in this build. `ansible`'s dev
    checkout also moved, from `C:\Users\MyahMitchell\GitHub\ansible` to `/opt/ansible`
    (a WSL-native path, not a Windows one under `/mnt/c`) — update any note that still
    points at the old path. Concrete `docker-stacks` changes: `docs/komodo-bootstrap.md`
    and `docs/ci01-bootstrap.md`'s clone/re-clone steps rewritten (no more "don't
    paste the credentialed URL" warning about the `ansible` clone itself — that
    warning now applies only to `ansible-private`'s clone/token, if you ever need to
    reference re-running `bootstrap-private.sh`); `docs/ci01-bootstrap.md` step 5 also
    gained a caution against `git pull`-ing `/tmp/ansible` after the private overlay
    has been copied into it (those two files are locally modified relative to git;
    pulling risks Git refusing, or silently reverting them to the public repo's
    placeholders); root `README.md`'s repo list and `containers/komodo/stack-README.md`'s
    PAT-reasoning paragraph updated to match. **Not yet run for real**: this is a
    clean restart, not a migration — no VM has booted against the new
    public-`ansible`-plus-private-overlay flow yet, so the cloud-init `runcmd` split
    (public clone unconditional, private clone gated on the token) is reasoned
    through from reading `ansible`'s own templates/tasks, not confirmed against a
    live boot.

---

## Status checklist by phase

- [x] **Phase 2 (partial)** — `containers/ntfy/`, `containers/mailrise/`,
      `containers/blackbox-exporter/`, `containers/uptime-kuma/`,
      `containers/semaphore/` + `stacks/semaphore-server/` built.
- [ ] **Phase 2 (remainder)** — `semaphore-server` deploys to `ci01` alone first
      (decision #17, see `docs/ci01-bootstrap.md`); the rest of `stacks/core-infra`
      (victoriametrics-server + ntfy + mailrise + blackbox-exporter + uptime-kuma)
      still isn't assembled as one stack and joins `ci01` later. Komodo/Semaphore UIs
      not yet gated behind Authentik; `vmalert` not yet wired to `ntfy`. **Blocked
      on**: Authentik actually running to test auth-gating against, which needs VM
      provisioning first — **now in progress**, see `km01`'s status above.
- [ ] **Phase 1** — Colo Proxmox bring-up. Independent track, no dependency on
      anything else. Not started. Do whenever colo hardware/hosting allows.
- [ ] **Phase 3** — UniFi-native connectivity (Site Magic + UID Teleport). **Zero
      repo work** — pure UniFi console configuration at both sites. Not started.
- [x] **Phase 4** — `containers/cloudflared/` built, wired into
      `stacks/traefik-dmz`. **Still needed**: real DMZ VLAN + firewall rule (manual,
      network-level), real Cloudflare tunnel creation (see
      `containers/cloudflared/stack-README.md`).
- [x] **Phase 5** — `containers/step-ca/` + `stacks/step-ca-server/` built, full
      root-key extraction/2-copy-custody runbook + sandbox recovery test written.
      **Still needed**: real `step ca init` bootstrap, real root-key extraction, and
      building the internal Traefik ACME resolver against step-ca — not scaffolded
      yet at all (see decision #15), not just unverified.
- [ ] **Phase 6** — Access control (Authentik groups + WebAuthn MFA + Ansible
      sudoers/accounts). Not started. **Blocked on**: Authentik live. You have 1
      YubiKey in hand (backup arriving soon, not a blocker).
- [ ] **Phase 7** — step-ca SSH CA + OIDC SSH login + `pam_u2f`. Not started.
      **Blocked on**: step-ca and Authentik both live.
- [x] **Phase 8** — `dotfiles/install.sh`'s `cargo-binstall` fix +
      `ansible/roles/dotfiles/` sync role, wired into `provision.yml`. **Still
      needed**: a real smoke test (never run end-to-end in this environment — no
      Docker/Ansible available), and adding `DOTFILES: true` to real host-variant
      groups once hosts exist.
- [x] **Phase 9** — `containers/postgres-backup/` built, wired into
      `authentik-server`, `semaphore-server`, `komodo-server`. **Still needed**: a
      real restore test once those stacks are live.
- [ ] **Phase 10** — `containers/vaultwarden/` + `stacks/vaultwarden/` + data
      migration. Not started. Wants Authentik live first for OIDC wiring.
- [ ] **Phase 11** — Cutover (remove WAN port-forward, retire old Vaultwarden).
      Not started. Depends on Phase 10.
- [x] **Phase 12** — `renovate.json` + `.github/workflows/lint.yml` built.
      **Still needed**: install Renovate's hosted GitHub App against the real repo
      (GitHub-side action, not a repo change).
- [ ] **Phase 13** — Build guide & diagrams consolidation. `docs/build-guide/` (the
      version this originally referred to) was deleted entirely in the 2026-08-16/17
      domain-scrub session — it had real domain names baked in and needed to just go,
      not be genericized. Root `README.md` (Start Here) and `docs/komodo-bootstrap.md`
      now partially cover this ground for what's actually been built so far; the rest
      still depends on every other phase being real before it can be finished
      honestly.

---

## What's built — file-level detail

| Area | Files | Notes |
|---|---|---|
| Notifications | `containers/ntfy/`, `containers/mailrise/` | ntfy = push destination; mailrise = SMTP→Apprise bridge for PBS/PVE |
| Uptime/reachability | `containers/blackbox-exporter/`, `containers/uptime-kuma/` | scraped by vmagent, alerted via vmalert |
| Ansible runner | `containers/semaphore/`, `stacks/semaphore-server/` | Postgres-backed |
| DB backups | `containers/postgres-backup/`, wired into `stacks/authentik-server`, `stacks/semaphore-server`, `stacks/komodo-server` | scheduled `pg_dump` + retention, shares each stack's existing `POSTGRES_*` vars — no new secrets |
| Tunnel edge | `containers/cloudflared/`, wired into `stacks/traefik-dmz` | named-tunnel/local-config mode (credentials JSON + git-committed `config.yml`), not dashboard `--token` mode — ingress rules stay in git |
| Internal PKI | `containers/step-ca/`, `stacks/step-ca-server/` | root-key custody runbook + sandbox recovery test fully documented in `stack-README.md` |
| CI | `.github/workflows/lint.yml` | yamllint + `scripts/build.py` regen + `docker compose config` + drift check |
| Dependency bumps | `renovate.json` | `config:recommended` + custom regex manager for future `_VERSION` keys + major-version dashboard gate |
| Docs | root `README.md` (Start Here — plan/layout/naming/secrets conventions), `docs/overview.md` (bootstrap-doc index + running order), `docs/stacks-overview.md` (per-stack "what does each compose file do", the old root README), `docs/komodo-bootstrap.md` (`km01`'s manual-bootstrap runbook, steps 1–13 only now), `docs/ci01-bootstrap.md` (`ci01`/Semaphore — the template every VM after it follows), `docs/traefik-bootstrap.md` (the temporary per-VM bootstrap Traefik, decision #18) | `docs/build-guide/00-overview.md` (an earlier, narrower companion doc) was deleted in the domain-scrub session — had real domain names baked in |
| Bootstrap Traefik | `stacks/traefik-bootstrap/` (new), `TRAEFIK_AUTH_CHAIN` variable added to 10 containers' `compose.yaml`/`komodo.env` | decision #18 — self-signed TLS + `chain-no-auth@file`, real Traefik routing before `pk01`/`id01` exist, replaces the SSH-tunnel workaround `docs/ci01-bootstrap.md` briefly used |
| Dotfiles sync | `ansible/roles/dotfiles/` (defaults/tasks/main.yml/tasks/sync.yml), wired into `ansible/provision.yml` | targets `client_account`, not the `ansible` service account; runs `install.sh --no-windows` remotely |
| cargo-binstall | `dotfiles/install.sh`, `dotfiles/CLAUDE.md` | `cargo_install()` tries `cargo binstall <crate>@<version>` via `CARGO_INSTALL_ROOT` before falling back to `cargo install` |
| Secrets structure | `containers/{cloudflared,mailrise,komodo}/secrets/` (gitignored, real credentials) vs `config/` (git-tracked, never a real secret) | `.gitignore`'s old blanket `containers/*/config/*` rule removed — was breaking `git add` on legitimate tracked files without actually protecting anything |
| Password/secret generation | `scripts/build.py` (`DB_PASSWORD_SUFFIXES` → 48 chars, `OTHER_SECRET_SUFFIXES` → 96 chars) | bumped from a flat 16 chars; deliberately excludes externally-issued credentials and format-restricted secrets, which stay manual |
| Internal DNS automation | `containers/dockns/compose.yaml`, `komodo.env`, `stack-README.md` | swapped its Technitium provider for its `unifi` provider (local connector, per-site) — see decision #5/#14 and the session log entry above |

---

## A real bug found and fixed along the way

`scripts/build.py`'s markdown merger detects headings by scanning every line for a
leading `#`/`##`/etc. + space — **it does not track fenced code-block state.** Any
`stack-README.md`/`README.md` line starting with `#` inside a ` ``` ` fence (a common
shell-comment style) gets misparsed as a real markdown heading, scrambling the
generated README the moment that container's docs get merged into a stack. Found in
`ntfy` and `postgres-backup`'s docs; fixed both by moving inline comments to prose
above smaller fences instead of inside them. **Compounding gotcha**: once corrupted
content lands in an on-disk `README.md`, the merge algorithm treats it as
user-added "stack-only" content and it becomes sticky across regenerations — fixing
the source alone isn't enough, the corrupted `README.md` has to be deleted and
regenerated fresh. Swept the whole repo afterward; confirmed clean elsewhere. **If
you ever hand-write another `stack-README.md`: never start a line with `#` + space
inside a fenced code block.** This is a real footgun in `build.py` itself, worth
fixing properly there at some point — not done here, only worked around in content.

Also patched a `.gitignore` gap found while in the area: `containers/*/config/*` and
`containers/*/secrets/*` had no ignore rule — only `.example`/`.gitkeep` were meant
to be tracked, but nothing enforced it. This retroactively protects files that
already existed with no protection (e.g. `mailrise.conf`, which contains a real ntfy
token), not just new ones.

---

## How this was validated (and what it doesn't prove)

- `scripts/build.py` was actually executed (via `wsl.exe python3` — Python isn't on
  Windows PATH here) against the real repo, regenerating every stack's
  `komodo.env`/`README.md`/`.env`. Proves the templating/merge logic accepts the new
  containers/stacks without error and produces clean markdown post-fix.
- Every `compose.yaml` (50+ files), `lint.yml`, and `renovate.json` parsed with
  PyYAML/`json` — catches syntax errors, not semantic ones.
- `install.sh` was syntax-checked with `bash -n`, **never executed** — it installs
  real packages and would modify this machine's actual environment.
- `ansible/roles/dotfiles/` files were YAML-parsed, not run through
  `ansible-playbook --syntax-check` — Ansible isn't installed in this WSL
  environment.
- **Nothing was deployed, started, or connected to a real service** — in *this*
  sandbox environment. No Docker daemon was ever available here to run
  `docker compose config` or start a container for real.
- **`stacks/traefik-bootstrap`'s self-signed-cert behavior is reasoned through, not
  verified.** Omitting `defaultGeneratedCert.resolver`/the dashboard entrypoint's
  `certresolver` entirely (rather than setting either to a blank value) is expected,
  per Traefik's documented behavior, to fall back to its own auto-generated
  self-signed cert — never actually confirmed against a live Traefik instance, since
  no Docker daemon exists in this environment. Verify this for real the first time
  `docs/traefik-bootstrap.md` gets used.
- **Exception, as of 2026-08-16/17**: `docs/komodo-bootstrap.md` and the
  `komodo-server` stack it covers *have* now been run for real, against your actual
  `vm-komodo` host — not just parsed/reasoned about. That's how the `proxy` network
  gotcha, the `core.config.toml` secrets issue, and the `@`-in-password URL-parsing
  bug got found: by you actually hitting them, not by a read of the code. Still
  **in progress**, not confirmed fully working end-to-end yet.

---

## Prerequisites checklist

1. ~~3 YubiKeys~~ → **1 YubiKey — have it.** Backup arriving soon; Phase 6/7 not
   blocked on the second one showing up.
2. ~~NetBird account~~ → **dropped**, see decision #1.
3. **UniFi console access** at both sites — needed for Phase 3, no repo dependency,
   can happen any time.
4. **DMZ VLAN — done.** Cloudflare account + zone for `myah-mitchell.com` and the
   one-time tunnel-creation steps (`containers/cloudflared/stack-README.md`) still
   needed.
5. **Colo** — after everything home is running and debugged, per your call. Your
   existing 2-backup-set posture already satisfies 3-2-1; nothing to change there.
6. **VM provisioning — in progress.** PVE host up, storage ready, `ansible` run
   against it, cloud-init template built. `km01` (manual Komodo bootstrap, following
   `docs/komodo-bootstrap.md`) is being worked through right now → `ci01` (Semaphore,
   `docs/ci01-bootstrap.md`) next, then `tf01`/`id01`/`pk01` via Komodo GitOps once
   Semaphore can push their `node_exporter_password` fix (decisions #16/#17). Komodo's
   own Core↔Periphery trust no longer waits on Semaphore at all — see decision #19.

---

## Next steps, in the order they unblock the most

1. **Finish provisioning `km01`** — **in progress right now**, following
   `docs/komodo-bootstrap.md` (written and already once-revised for clarity/ordering
   based on actually working through it) against the real PVE host/template. Last
   known blocker found and understood: a hand-typed password containing `@` broke
   the FerretDB→Postgres connection string. Not yet confirmed the stack is fully up
   and healthy end-to-end — confirm that, then point Komodo at this repo.
2. **Provision `ci01` with just `stacks/semaphore-server`** (not the full
   `core-infra` bundle yet), following the now-written
   [`docs/ci01-bootstrap.md`](../docs/ci01-bootstrap.md) — priority right after `km01`,
   specifically to unblock secret distribution: Semaphore becomes the way real values
   (`node_exporter_password`, anything else `ansible` needs that shouldn't be a plain
   committed default) get pushed to every server going forward, instead of
   hand-editing `ansible` per host. Not started against a real host yet — `ci01`
   itself still needs its own one-time onboarding key generated by hand to join
   Komodo (decision #19, step 5 of `docs/ci01-bootstrap.md`), same as every future
   host; that's permanent, not a Semaphore-removable bootstrap gap.
3. **Once Semaphore is up and wired to the `ansible` repo** (step 13 of
   `docs/ci01-bootstrap.md`), use its Template to push real values over the
   `node_exporter_password` `CHANGEME` placeholder fleet-wide (decision #16).
4. **Provision `tf01`**, deploy `stacks/traefik-server` via Komodo — unblocked once
   step 3 is done.
5. **Provision `id01`**, deploy `stacks/authentik-server` (already includes
   `postgres-backup`). Unblocks Phase 2's remaining Authentik-gating work and all of
   Phase 6.
6. **Provision `pk01`**, real step-ca bootstrap (Phase 5: `step ca init`, real
   root-key extraction/2-copy custody). Needed before decision #15's internal-certs
   work and before step 8 below can actually happen.
7. **Assemble and deploy the rest of `core-infra`** onto `ci01` alongside the
   `semaphore-server` already there (victoriametrics-server + ntfy + mailrise +
   blackbox-exporter + uptime-kuma — not yet assembled as one stack).
8. **Fix and deploy `stacks/system-agent` fleet-wide** (decision #14), once
   `ci01`/`id01`/`pk01` all exist — it needs live backends for monitoring
   (`ci01`), the auth chain (`id01`), and internal certs (`pk01`), so there's no
   point deploying it earlier. `km01` deliberately stays on its direct `:9120` port
   until then; retrofit `system-agent` onto it last, not first, once the pattern's
   proven on a less-critical VM.
9. Once Komodo + Authentik are up and `system-agent` is proven: gate their web UIs
   behind `chain-authentik@file` (via each VM's own local Traefik, not `tf01`), wire
   `vmalert` → `ntfy` via Alertmanager's webhook. Closes out Phase 2.
10. **UniFi console** (Phase 3) — no dependency on the above, do in parallel whenever
    convenient. Configure UID Teleport now; Site Magic waits on colo.
11. From there: Phases 6, 7, in sequence (access control, then step-ca SSH CA/OIDC).

**Documentation restructuring — done, see decision #17.** `docs/komodo-bootstrap.md`
now covers only `km01`'s steps (plus steps 10 and 13, opening the firewall for Core
and getting its public key, added by decision #19); its old, since-removed step 12
became
[`docs/ci01-bootstrap.md`](../docs/ci01-bootstrap.md), a real worked example instead
of an abstract walkthrough; [`docs/overview.md`](../docs/overview.md) indexes every
VM's doc and status. `tf01`'s own doc still isn't written — deliberately deferred
until that VM is actually being provisioned, following `docs/ci01-bootstrap.md`'s
shape (its closing section spells out what carries over and what doesn't: `tf01` no
longer needs `ci01`/`km01`'s one-time manual `node_exporter_password` fix once
Semaphore's Template exists, but it still needs its own onboarding key generated by
hand to join Komodo — decision #19, permanent for every host, Semaphore doesn't
remove it).

---

## Known open questions

- **step-ca's Traefik resolver**: exact ACME challenge config for step-ca to issue
  Traefik's internal certs is unconfirmed and, per decision #15, not even scaffolded
  yet — needs real work against a live step-ca before any VM's `system-agent`
  Traefik can actually use it. (An earlier version of this note claimed a scaffolded
  `internalca` block already existed in `containers/traefik/compose.yaml` — checked
  the file and its full git history directly, that was never true. Corrected here.)
- **`system-agent`'s exact fixes** — resolved *what* it's for (decision #14: the
  standard per-VM stack), still open *what specifically* is broken/unfinished about
  it. Needs a real read-through before first deploy.
- **dockns UniFi alias record shape** — the Cloudflare/Technitium-era config used
  CNAME records pointing at each VM's own hostname
  (`DOCKNS_NS_<X>_RECORD_DEFAULTS_CNAME_TARGET_DOMAIN`), which assumes
  `<server>.<site>.myah-mitchell.com` already resolves (an A record from somewhere
  else) before the alias CNAME is useful. The UniFi provider swap kept that same
  shape rather than switching to direct A records — reasonable default, but not
  confirmed as the intended behavior, and doesn't yet address how each VM's own
  hostname A record itself gets created (DHCP static lease in UniFi already does
  this today, separately from dockns — that's plausibly sufficient, not verified).
- **`cargo-binstall` in `install.sh`**: uses `CARGO_INSTALL_ROOT` (documented cargo
  env var, binstall is designed to honor it identically to `cargo install --root`) —
  reasoned through, never run against a real crate.
- **UID's OIDC IdP-binding tier**: Ubiquiti's public docs don't clearly state
  whether binding Authentik as an external IdP to UniFi Identity needs the paid UID
  Enterprise tier. Check directly in the console. If it's gated and not worth the
  per-admin-user cost just for this, UID's own built-in login for the VPN tunnel
  alone is a fine fallback — doesn't conflict with decision #3 (Authentik still owns
  *application* identity; this is narrowly about VPN-tunnel login).

---

## Notes for whoever picks this up cold

- **Repo conventions**: `containers/<name>/` = individual service (compose.yaml +
  komodo.env + testing.env + README.md + stack-README.md). `stacks/<name>/` =
  composition of containers via Compose's `extends`. `scripts/build.py` (run via
  WSL — `wsl.exe bash -c "cd /mnt/c/... && python3 scripts/build.py"`, since Python
  isn't on Windows PATH here) auto-generates each stack's `komodo.env`/`.env`/
  `README.md` by merging the base template with every container fragment it
  extends, using heading-based rules (see the fence-heading bug above for the one
  sharp edge in that process).
- **Komodo's `DOMAIN_NAME`/`SUB_DOMAIN_NAME`/`SERVER_NAME`** are set **per-stack
  deployment** in Komodo itself, not hardcoded anywhere in this repo — so bare
  `myah-mitchell.com` (public stacks) and `home.myah-mitchell.com`/
  `cloud.myah-mitchell.com` (internal, per-site) can coexist without any repo-level
  conflict. Nothing to change here, just know it's a Komodo-side setting — see root
  `README.md` for the full naming-convention writeup, now committed to the repo
  itself rather than only living here.
- **`ansible` repo conventions**: `roles/<name>/tasks/main.yml` conditionally
  `include_tasks` a sub-file gated by `when: FLAG|bool`; `provision.yml`
  unconditionally lists every role, gating happens per-role; `hosts.yml` uses
  boolean host-variant flags per inventory group. `client_account` ("m0rsla") is the
  human admin account; `ansible_account` ("ansible") is the automation service
  account — dotfiles target the former, not the latter.
- **This session's environment had no Docker, no live Ansible, no network path to
  any real host.** Every validation claim above is bounded by that — treat anything
  marked "built" as "compiles/parses cleanly," not "known to work on a real host."
  **Updated 2026-08-17**: the `ansible` repo (now `/opt/ansible`) and
  `ansible-private` are checked out on disk in this environment and readable — used
  to verify Komodo Periphery's real install location directly instead of guessing,
  twice. Still no `ansible-playbook` binary here, so nothing in either repo has
  actually been executed, only read.
- **Komodo Periphery is already installed by `ansible`** — don't re-build it.
  `roles/docker/tasks/komodo.yml`, included from `roles/docker/tasks/main.yml`,
  gated by `KOMODO: true` (already set for the whole `ubuntu_docker` group in
  `hosts.yml`, the group every VM in this plan provisions from). This has been
  mistaken for missing twice in one session — check this file/line directly before
  concluding otherwise.
- **Stale as of decision #20**: `ansible/README.md` and
  `proxmox-cloud-init/cloudinit-vendor.yml` used to both have a real GitHub PAT
  committed in plain text, in a `git clone` URL — confirmed intentional and accepted
  at the time (private repo, read-only, scoped to just those two repos). That PAT is
  now gone: `ansible` is public (no credential needed to clone it at all), and
  `proxmox-cloud-init` is deprecated. The one credential that replaced it,
  `PRIVATE_REPO_TOKEN`/`ansible_private_repo_token` (read-only, scoped to
  `ansible-private` alone), is never committed anywhere, by design — see decision
  #20. **Still never copy a credentialed clone URL into `docker-stacks`** — that repo
  is public — but there's no longer a standing literal secret to avoid quoting; point
  at `ansible`'s own `README.md`/`scripts/bootstrap-private.sh` instead. The
  `proxmox-cloud-init` repo's git *history* still contains the old real PAT from
  before this switch — that's a separate, pre-existing consideration (rotate/revoke
  it if it's genuinely dead now) not addressed here.
- **The unexplained `ansible/hosts.yml` diff from a prior session** (a
  `MONITORING: false` addition under the `wsl` group that wasn't attributable to any
  action taken at the time) turned out to be your own later commit
  (`29665a9 Disabled monitoring flag under WSL`) — resolved, not a loose end
  anymore.
- **If you're an AI picking this up**: the master plan file
  (`i-want-work-out-zippy-iverson.md`, path at the top of this doc) has the full
  design rationale for every decision above — read it before proposing changes to
  anything in the "Decisions log" section, most of those were arrived at after
  cutting something more complex, not the first idea considered.
