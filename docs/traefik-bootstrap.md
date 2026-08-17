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

Same pattern as any other Komodo-driven stack (see `docs/ci01-bootstrap.md` steps
8–11 for the full walkthrough of registering a Server and creating a Stack
resource) — the specifics for this stack:

- **Run Directory**: `stacks/traefik-bootstrap`.
- **File Path**: `compose.yaml`.
- **Environment**: `stacks/traefik-bootstrap/komodo.env`. Set `SERVER_NAME` /
  `SUB_DOMAIN_NAME` / `DOMAIN_NAME` the same way every stack needs. `CF_API_EMAIL`,
  `CF_DNS_API_TOKEN`, `CROWDSEC_LAPI_KEY`, and `AUTHENTIK_HOST` can all stay blank —
  they're inherited from the base `containers/traefik/` config template but this
  stack's `compose.yaml` deliberately doesn't reference any of them (no ACME
  resolver, no CrowdSec plugin wiring, no Authentik forward-auth).
- Runtime folders: same as any Traefik-based stack — see the generated
  `stacks/traefik-bootstrap/README.md` for the exact `mkdir`/`chown` block.

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
