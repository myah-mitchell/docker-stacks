# Conventions

The naming and secrets rules every stack, runbook, and script in this repo assumes. Read this before adding a container, adding a stack, or provisioning a host.

## Naming

Every stack resolves its identity from four variables, set per deployment in Komodo and never hardcoded in this repo.

| Variable | Meaning | Example |
| --- | --- | --- |
| `PROJECT_NAME` | The stack's own short name | `komodo` |
| `SERVER_NAME` | This VM's hostname, `<role><NN>`, no site prefix | `km01` |
| `SUB_DOMAIN_NAME` | The site this VM lives at, with a trailing dot | `home.` |
| `DOMAIN_NAME` | The real domain | `myah-mitchell.com` |

`myah-mitchell.com` is the literal example domain throughout this repo's documentation. It is safe to commit here: it is the same name as the GitHub account the repo lives under.

### The trailing dot

The dot is part of `SUB_DOMAIN_NAME`'s own value. Nothing adds or strips it anywhere else.

Every hostname and URL in this repo is built by concatenating `${SUB_DOMAIN_NAME}${DOMAIN_NAME}` directly. To drop the sub-domain for a public hostname, set `SUB_DOMAIN_NAME` to an empty string and you get `myah-mitchell.com`, not a stray leading dot. That works everywhere the variable is used, so no template needs conditional logic to strip a dot that was never there.

### Sites

| Site | `SUB_DOMAIN_NAME` |
| --- | --- |
| Home | `home.` |
| Cloud (colo) | `cloud.` |

### Roles

The two-letter prefix in `SERVER_NAME`.

| Abbr | Role |
| --- | --- |
| `km` | Komodo GitOps engine |
| `tf` | Traefik hub |
| `ci` | Core infra: VictoriaMetrics, Semaphore, ntfy, mailrise, blackbox-exporter, uptime-kuma |
| `id` | Authentik, identity |
| `pk` | step-ca, internal PKI |
| `bh` | Bastion and edge, in the DMZ |
| `ap` | Apps, Vaultwarden and future replacements |
| `md` | Media |
| `bk` | Backup, PBS (pre-existing) |
| `mx` | Mail gateway (pre-existing) |
| `vh` | Hypervisor, PVE (pre-existing) |

### Worked examples

| FQDN | What it is |
| --- | --- |
| `km01.home.myah-mitchell.com` | Komodo, home site, internal only |
| `pk01.home.myah-mitchell.com` | step-ca, home site, internal only |
| `bk01.cloud.myah-mitchell.com` | Offsite backup target at the colo site |
| `ntfy.home.myah-mitchell.com` | A service on `ci01`, resolvable only inside the home site |
| `vault.myah-mitchell.com` | Vaultwarden, public, no `SUB_DOMAIN_NAME` at all |

A handful of services are reached from the internet through a Cloudflare Tunnel rather than a site sub-domain. Those use the bare domain, with `SUB_DOMAIN_NAME` empty, and they reach the internet through `cloudflared` plus `traefik-dmz` on `bh01`. Vaultwarden is the only one today.

## Secrets

| Kind of value | Rule |
| --- | --- |
| Database username | `<service>-admin`, for example `komodo-admin` |
| Database password | Random 48-character alphanumeric string |
| Other application secrets | Random 96-character alphanumeric string |
| Credentials issued by an external service | Never generated, left blank until you paste the real one in |

`scripts/build.py` fills the first three automatically. Any `komodo.env` key ending in `_PASSWORD` or `_PASS` that is left blank gets a 48-character value; any key ending in `_PASSKEY`, `_SECRET_KEY`, or `_LAPI_KEY` gets a 96-character one. See `DB_PASSWORD_SUFFIXES` and `OTHER_SECRET_SUFFIXES` in that script for the exact rules.

Two categories are excluded on purpose. A credential issued by an external service, such as a Cloudflare API token or a MaxMind license key, would silently look filled in while not working, so it stays blank. A secret with a format restriction, such as `SEMAPHORE_ACCESS_KEY_ENCRYPTION` needing a base64-encoded 32-byte key, stays a documented manual step instead.

### Alphanumeric only

> [!WARNING]
> Never hand-type a password containing `@`, `:`, `/`, `#`, `?`, or any other symbol, and do not extend the generator to add them.

This is not about entropy. A 48-character alphanumeric password is about 286 bits, already past AES-256's 256-bit benchmark, and the 96-character secrets are about 571 bits. Nothing in any threat model gets meaningfully safer past that point.

It is about breakage that has already happened. Those five characters are all syntactically meaningful somewhere a password ends up: URL and connection-string delimiters, TOML and YAML string syntax, shell quoting. This repo does not escape generated values for whatever context they land in, so a symbol in the wrong place fails as something else entirely rather than failing loudly. A hand-typed password containing `@` broke `FERRETDB_POSTGRESQL_URL`'s interpolated connection URL and surfaced as a DNS resolution failure against the wrong hostname, not as an auth error. Some applications also reject specific symbols outright, which alphanumeric-only sidesteps by construction.

### config/ and secrets/

A container's `config/` never holds a real secret. It holds `.example` templates and non-sensitive files, and it is always safe to commit.

When a container's real config would contain a credential, such as a tunnel credentials file or an API token baked into a config file, the real file goes in that container's `secrets/` folder instead. That folder is gitignored with a tracked `.gitkeep` so the folder itself exists. See `cloudflared`, `mailrise`, or `komodo` for the pattern.
