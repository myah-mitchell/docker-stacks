# `traefik-bootstrap` — temporary per-VM Traefik for the pre-`pk01`/`id01` window

Most stacks in this plan are only reachable two ways: through a real Traefik
instance, gated behind `chain-authentik@file` (Authentik forward-auth) and TLS
issued by step-ca. Until `pk01` (step-ca) and `id01` (Authentik) both exist, neither
of those work — which is why `docs/ci01-bootstrap.md` originally had to reach
Semaphore's UI through an SSH tunnel straight to its container IP, bypassing Traefik
entirely.

`stacks/traefik-bootstrap` replaces that workaround: a real Traefik, on the real
`proxy` network, with real hostnames — just with **self-signed TLS instead of a real
cert resolver**, and **`chain-no-auth@file` instead of `chain-authentik@file`**
(`containers/traefik/rules/chain-no-auth.yaml` already existed before this doc —
rate-limit/secure-headers/compress, no Authentik dependency). Every other stack's
Traefik labels already default to `chain-authentik@file` via
`${TRAEFIK_AUTH_CHAIN:-chain-authentik@file}` — deploying under `traefik-bootstrap`
means setting that one variable to `chain-no-auth@file` for the stacks you want
reachable during the bootstrap window, nothing else about them changes.

**This is temporary, per VM, by design — not a permanent stack.** Once a VM's real
`system-agent` (decision #14) is fixed and deployable (needs `pk01`/`id01` live),
tear `traefik-bootstrap` down on that VM and deploy `system-agent` in its place
rather than running both.

## When to deploy it

Any VM that needs to serve stacks with real Traefik routing before `pk01`/`id01`
exist. `ci01` is the first case — see `docs/ci01-bootstrap.md`.

## How to deploy it

The target VM must already exist as a Komodo Server resource (its own bootstrap doc
covers that) and already have the `proxy` Docker network created on it — every VM
needs that once regardless of Traefik (see `docs/komodo-bootstrap.md` step 9).

1. Create the runtime folders on the target VM:

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

2. In Komodo's UI, go to **Resources → Stacks** and create a new one — name it
   `traefik-bootstrap`. Set its target **Server** to the VM you're deploying onto.
3. Under **Choose Mode**, choose **Git Repo**:
   - **Repo**: `myah-mitchell/docker-stacks` — no credential needed, the repo is
     public.
   - **Branch**: `main`.
4. Under **Files**:
   - **Run Directory**: `stacks/traefik-bootstrap`.
   - **File Path**: `compose.yaml`, relative to that run directory.
5. Under **Environment**, there's no "point at a file" option — it's a plain text
   editor field (`environment`), plus a separate `env_file_path` field that's just
   where Komodo writes the resolved result on the target VM before running compose
   (leave it at its default, `.env` — nothing to change there). Open
   `stacks/traefik-bootstrap/komodo.env` in this repo, copy its full contents, and
   paste them directly into that editor — Komodo's parser accepts the same
   `KEY: value` lines this repo's `komodo.env` already uses (as well as `KEY = value`,
   comments, and quoted values), so it pastes in as-is, no reformatting needed. Then
   edit the pasted text in place for the handful of keys that need a real value;
   everything else is fine left exactly as pasted. It has three kinds of values in
   it — only the first kind needs editing here:
   - **No default, must set**: `SERVER_NAME` / `SUB_DOMAIN_NAME` / `DOMAIN_NAME` —
     the same way every stack needs (see the root `README.md`'s naming
     conventions). `PROJECT_NAME` needs no edit either, even though it drives
     every hostname/label in the stack — it's already committed as `traefik`
     directly in `komodo.env`, not left blank like the three above.
   - **Has a working default, leave as-is**: `TRAEFIK_HOSTNAME` (`traefik` —
     only change it if you want the dashboard reachable under a different
     hostname) and `ERROR_PAGES_HOSTNAME`/`SOCKET_PROXY_HOSTNAME`/
     `LOGROTATE_HOSTNAME` (their container hostnames — no reason to touch these).
     `TRAEFIK_EXTRA_COMMAND` is also fine left blank; it's a passthrough for
     extra Traefik CLI flags you don't need for this stack.
   - **`[[GLOBAL_...]]` references, resolved automatically**: `PUID`/`PGID`/`TZ`/
     `DOCKER_VOLUMES`/`DOCKER_LOGS`/`PROXY_NETWORK` and the resource-limit/
     logging/health-check block below them. These pull from Komodo's own global
     Variables (set once for the whole Komodo instance, shared by every stack) —
     don't edit them per-stack here. **These must actually exist first** — see
     `docs/komodo-bootstrap.md` step 14. If you deploy before creating them, Compose
     fails trying to interpolate the literal string `[[GLOBAL_CPUS_LIMIT]]` (etc.)
     into a numeric field; go create the Variables, then hit Deploy again.
   - Leave `CF_API_EMAIL`, `CF_DNS_API_TOKEN`, `CROWDSEC_LAPI_KEY`, and
     `AUTHENTIK_HOST` blank regardless of what their `[[...]]` references resolve
     to — this stack's `compose.yaml` deliberately doesn't reference any of them
     (no ACME resolver, no CrowdSec plugin wiring, no Authentik forward-auth), so
     it doesn't matter whether a real value exists for them elsewhere.
6. Save the Stack resource, then click **Deploy**. Watch the deploy log — it clones
   the repo, reads the compose file, and runs the Compose equivalent of
   `docker compose up -d` on the target VM via Periphery.

Confirm `traefik`, `error-pages`, `socket-proxy`, `socket-proxy-rw`, and
`logrotate` all show running/healthy — either in Komodo's own container view for
the resource, or `docker compose ps` on the target VM.

For any *other* stack you want reachable through it (Semaphore, etc.), set that
stack's `TRAEFIK_AUTH_CHAIN` to `chain-no-auth@file` when you deploy it — see the
comment above that key in its own `komodo.env`.

**Not yet verified against a live Traefik**: omitting the cert-resolver directives
entirely (rather than setting them blank) is expected, per Traefik's documented
behavior, to fall back to its own auto-generated self-signed cert. Reasoned through,
never actually run — no Docker daemon existed anywhere this was written. If it
doesn't come up cleanly the first time you deploy it, that's the first thing to
double-check.

## Accessing a stack through it

Browse to the stack's normal hostname over HTTPS — e.g.
`https://semaphore.ci01.home.myah-mitchell.com`. **Your browser will warn about the
certificate** — it's self-signed, not issued by a CA your browser trusts. That's
expected here, not a misconfiguration; accept it and continue. This is real routing
through real Traefik, not the SSH-tunnel-to-container-IP workaround it replaces.

## Tearing it down

Once `system-agent` is fixed and deployed on this VM for real (decision #14), delete
the `traefik-bootstrap` Stack resource in Komodo (or `docker compose down` it
directly) and flip every stack that was overridden to `chain-no-auth@file` back to
the default by clearing that override — they'll pick up `chain-authentik@file`
automatically. Don't run both Traefik instances on the same VM at once — they'd
fight over the same `:80`/`:443`/`:8443` host ports.
