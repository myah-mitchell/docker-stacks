# Start here

Compose-based container definitions for a self-hosted homelab/cloud hosting
cluster, deployed via [Komodo](https://github.com/moghtech/komodo) GitOps. Read this
before touching anything else in the repo — this doc covers the plan, the layout,
and the naming/secrets conventions everything else builds on;
[`docs/overview.md`](docs/overview.md) covers the order VMs get bootstrapped in and
links each host's own runbook; [`docs/stacks-overview.md`](docs/stacks-overview.md)
covers what each individual stack does.

## What this repo is part of

The buildout spans three repos:

- **`docker-stacks`** (this one) — every container/stack definition.
- **`ansible`** — OS-level provisioning (Docker, firewall, NTP, users, etc.) for
  every VM before any stack lands on it.
- **`proxmox-cloud-init`** — the cloud-init template + vendor script that turns a
  freshly-cloned Proxmox VM into a fully-provisioned host on first boot, no manual
  SSH step required.

The `km01` VM is the one deliberate exception to "everything is GitOps" — it has to
be provisioned and started by hand, since Komodo can't GitOps-deploy itself the first
time. Start there: **[`docs/komodo-bootstrap.md`](docs/komodo-bootstrap.md)** is the
concrete, step-by-step runbook for it. Every VM after that gets provisioned with
Ansible, then deployed through Komodo instead — see
**[`docs/overview.md`](docs/overview.md)** for the running order and each host's own
runbook.

## Repo layout

- **`containers/<name>/`** — one container definition per folder: `compose.yaml`,
  `komodo.env` (Komodo-specific env/secrets template), `testing.env` (non-sensitive
  local-testing defaults), `README.md` (this container on its own), `stack-README.md`
  (the fragment merged into every stack that includes it), and optionally
  `config/` (non-secret files, always safe to commit) and `secrets/` (real
  credentials, always gitignored — see below).
- **`stacks/<name>/`** — a deployable composition of containers via Compose's
  `extends`. `compose.yaml` is hand-written; `komodo.env`, `.env`, and `README.md`
  are generated — don't hand-edit those, see `scripts/build.py` below.
- **`scripts/build.py`** — regenerates every stack's `komodo.env`/`.env`/`README.md`
  from the base templates plus each container's fragments. Run it after editing any
  container's `komodo.env`/`stack-README.md`/`testing.env`, or after adding a
  container to a stack. See `scripts/project-layout.md` for the full mechanics.

## Naming conventions

Every stack resolves its identity from four variables, set per-deployment in Komodo
(never hardcoded in this repo):

| Variable | Meaning | Example |
|---|---|---|
| `PROJECT_NAME` | The stack's own short name | `komodo` |
| `SERVER_NAME` | This VM's hostname — `<two-letter role><NN>`, no site prefix | `km01` |
| `SUB_DOMAIN_NAME` | The site this VM lives at, **with a trailing dot** | `home.` |
| `DOMAIN_NAME` | The real domain | `myah-mitchell.com` |

`myah-mitchell.com` is used as the literal example domain throughout this repo's
documentation — it's safe to have here, it's the same name as the GitHub account this
repo lives under.

**The trailing dot is part of `SUB_DOMAIN_NAME`'s own value, not added anywhere
else.** Every hostname/URL in this repo is built by directly concatenating
`${SUB_DOMAIN_NAME}${DOMAIN_NAME}` — no template strips or conditionally adds a dot.
To drop the sub-domain entirely for a public/external hostname (see below), just set
`SUB_DOMAIN_NAME` to an empty string — you get `myah-mitchell.com`, not a stray
leading dot. This is safe everywhere the variable is used (`compose.yaml`,
`komodo.env`, generated `.env`) since there's no place in this repo it would be easy
to special-case away a leftover dot if the variable were blank in a way that left one
behind.

**Sites** — `SUB_DOMAIN_NAME` is one of:

| Site | Sub-domain |
|---|---|
| Home | `home.` |
| Cloud (colo) | `cloud.` |

**Roles** — the two-letter prefix in `SERVER_NAME`:

| Abbr | Role |
|---|---|
| `km` | Komodo GitOps engine |
| `tf` | Traefik hub |
| `ci` | Core infra (VictoriaMetrics, Semaphore, ntfy, mailrise, blackbox-exporter, uptime-kuma) |
| `id` | Authentik / identity |
| `pk` | step-ca / internal PKI |
| `bh` | Bastion / edge (DMZ) |
| `ap` | Apps (Vaultwarden, etc.) |
| `bk` | Backup (PBS) |
| `mx` | Mail gateway |
| `vh` | Hypervisor (PVE) |

**Worked examples**, combining a hostname with a site:

- `km01.home.myah-mitchell.com` — Komodo, home site, internal-only.
- `pk01.home.myah-mitchell.com` — step-ca, home site, internal-only.
- `bk01.cloud.myah-mitchell.com` — offsite backup target at the cloud site.

**External/public** — a handful of services (Vaultwarden today) are reached from the
internet through a Cloudflare Tunnel rather than a site subdomain. These use the bare
domain, no `SUB_DOMAIN_NAME` at all:

- `vault.myah-mitchell.com` — Vaultwarden, public, via `cloudflared` + `traefik-dmz`.

Contrast with something that's never public, like `ntfy` on `ci01`:
`ntfy.home.myah-mitchell.com` — same domain, but only resolvable/reachable inside the
home site, never through the tunnel.

## Secrets conventions

- **Database username**: `<service>-admin` — e.g. `komodo-admin`, `authentik-admin`.
- **Database password**: a random 48-character alphanumeric string. Any `komodo.env`
  key ending in `_PASSWORD` or `_PASS` that's left blank gets one generated
  automatically by `scripts/build.py`.
- **Other application secrets** (API passkeys, internal signing/session keys,
  inter-service shared secrets): a random 96-character alphanumeric string. Any key
  ending in `_PASSKEY`, `_SECRET_KEY`, or `_LAPI_KEY` that's left blank gets one
  generated the same way — *unless* something about that specific secret restricts
  its format (e.g. `SEMAPHORE_ACCESS_KEY_ENCRYPTION` must be a base64-encoded 32-byte
  key, not plain alphanumeric), in which case it stays a documented manual step
  instead. See `DB_PASSWORD_SUFFIXES`/`OTHER_SECRET_SUFFIXES` in `scripts/build.py`
  for the exact rules.
- **Credentials issued by an external service** (a Cloudflare API token, a MaxMind
  GeoIP license key, etc.) are never auto-generated — they stay blank until you paste
  in the real one. A random value there would silently look "filled in" without
  actually working.
- **Alphanumeric-only is deliberate — never hand-type a password with `@`, `:`, `/`,
  `#`, `?`, or any other symbol in it, and don't "improve" the generator to add
  them.** Two separate reasons:
  - **We don't need the extra entropy.** 48 random alphanumeric characters
    (`a-zA-Z0-9`, a 62-character alphabet) is `log2(62) × 48 ≈ 286 bits` — already
    past AES-256's 256-bit standard, the benchmark for "secure against any
    conceivable brute-force attack." The 96-character secrets are `~571 bits`.
    Adding symbols raises the entropy-per-character, but there's no threat model
    where a password already hundreds of bits past uncrackable becomes meaningfully
    more secure by adding more — it's a number that's already larger than the atom
    count of the observable universe getting larger still.
  - **Symbols actively break things, and we've already hit it.** `@`, `:`, `/`, `#`,
    and `?` are all syntactically meaningful somewhere a password ends up:
    URL/connection-string delimiters, TOML/YAML string syntax, shell quoting. This
    repo doesn't escape generated values for whatever context they land in, so a
    symbol in the wrong spot doesn't just fail loudly — it fails as something else
    entirely. This isn't hypothetical: a hand-typed password containing `@` broke
    `FERRETDB_POSTGRESQL_URL`'s raw string-interpolated connection URL and failed as
    a confusing DNS-resolution error against the wrong hostname, not an obvious auth
    failure. Some applications also outright reject specific symbols in a password
    field, which alphanumeric-only sidesteps by construction rather than by luck.

  In short: length already buys effectively-infinite security margin, and symbols
  would only add fragility on top of a problem that's already solved.
- **`config/` never holds a real secret, ever.** If a container's real config would
  need one (a tunnel credentials file, an API token baked into a config file), the
  real file goes in that container's `secrets/` folder instead (gitignored,
  `.gitkeep`-tracked so the folder itself exists) — `config/` only ever holds
  `.example` templates and non-sensitive files, always safe to commit. See
  `cloudflared`, `mailrise`, or `komodo` for the pattern.

## Where to go next

- **[`docs/komodo-bootstrap.md`](docs/komodo-bootstrap.md)** — the first real step:
  standing up `km01` by hand.
- **[`docs/overview.md`](docs/overview.md)** — the running order for every VM after
  `km01`, and a link to each one's own bootstrap runbook.
- **`scripts/project-layout.md`** — the full mechanics of `build.py` and the
  generated-file conventions, if you're editing a container or adding a stack.
- **[`docs/stacks-overview.md`](docs/stacks-overview.md)** — what each individual
  stack does.
