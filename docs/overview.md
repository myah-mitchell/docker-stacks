# Bootstrap runbooks overview

An index of the step-by-step runbooks for standing up each VM in the plan. Start with
the root [`README.md`](../README.md) if you haven't already — it covers the plan,
repo layout, and naming/secrets conventions every doc here assumes. This page is
narrower: just "what order do I bring hosts up in, and where's the doc for each one."

## The general pattern

Every VM gets its base OS provisioned the same way: cloned from the shared
`ubuntu-server` cloud-init template, which self-provisions on first boot by running
`ansible`'s `provision.yml` against `target: ubuntu_docker` — Docker, firewall, NTP,
swap, monitoring, and **Komodo Periphery** all install automatically (`ansible`'s
`docker` role, gated by `KOMODO: true`, already set for that whole group — nothing
to build here, it's already there).

From that shared starting point, each VM's *stack* gets deployed one of two ways:

- **`km01` is the one deliberate exception** — provisioned and started entirely by
  hand, because Komodo can't GitOps-deploy itself the first time. See
  [`docs/komodo-bootstrap.md`](komodo-bootstrap.md).
- **Every other VM gets registered as a Komodo Server resource and deployed through
  Komodo's GitOps flow** instead — provision the base OS, fix that one VM's
  Periphery passkey (until Semaphore exists to do it for you — see `ci01` below),
  then let Komodo do the rest. [`docs/ci01-bootstrap.md`](ci01-bootstrap.md) works
  this pattern out in full for the first real case; every doc after it follows the
  same shape.

Docs are named after the **service** when there's something structurally unique about
its bootstrap (`komodo-bootstrap.md` — the one manual exception); named after the
**host** once a VM is just "provision, then deploy via Komodo" like every other one
after it (`ci01-bootstrap.md`, and so on).

**A shared operational tip, not repeated in every doc**: most stacks in this plan are
gated behind `chain-authentik@file` and expect a real cert resolver, neither of which
work until `pk01`/step-ca and `id01`/Authentik exist. Until then, deploy
[`docs/traefik-bootstrap.md`](traefik-bootstrap.md) on that VM — real Traefik
routing, just with self-signed TLS and `chain-no-auth@file` instead — and override
that stack's `TRAEFIK_AUTH_CHAIN` to `chain-no-auth@file`. `docs/ci01-bootstrap.md`
step 9 works through it in full for the first real case.

## Running order and status

| Order | VM | Role | Doc | Status |
|---|---|---|---|---|
| 1 | `km01` | Komodo GitOps engine | [`komodo-bootstrap.md`](komodo-bootstrap.md) | **in progress** — steps 1–11 followed against a real host; not yet confirmed fully healthy end-to-end |
| 2 | `ci01` | Semaphore (ansible runner) first, rest of `core-infra` later | [`ci01-bootstrap.md`](ci01-bootstrap.md) | written, not yet run against a real host |
| 3 | `tf01` | Traefik hub (central Redis + `traefik-kop`) | not written yet | not started — blocked on `ci01`/Semaphore existing to fix its Periphery passkey without another manual step |
| 4 | `id01` | Authentik / identity | not written yet | not started |
| 5 | `pk01` | step-ca / internal PKI | not written yet | not started |
| 6 | `bh01` | `cloudflared` + `traefik-dmz`, DMZ edge | not written yet | not started |
| 7 | `ap01` | Vaultwarden + future self-hosted app replacements | not written yet | not started |

Pre-existing hosts (`bk01`, `mx01`, `vh01`, and the PVE hosts themselves) aren't
covered here — they predate this plan and aren't provisioned by these runbooks.

Write each new doc when you actually reach that VM, not speculatively ahead of
time — `ci01-bootstrap.md`'s closing section explains why (the manual
Periphery-passkey step won't even be needed anymore once Semaphore's `ansible`
Template from its step 13 exists, so a doc written too early would describe a step
that no longer applies by the time it's used).

## See also

- [`komodo-bootstrap.md`](komodo-bootstrap.md) — `km01`, the one manual exception.
- [`ci01-bootstrap.md`](ci01-bootstrap.md) — `ci01`/Semaphore, the template for every
  VM after it.
- [`traefik-bootstrap.md`](traefik-bootstrap.md) — the temporary per-VM Traefik used
  before `pk01`/`id01` exist, referenced from every host doc that needs it.
- [`stacks-overview.md`](stacks-overview.md) — what each individual stack does,
  independent of bootstrap order.
- root [`README.md`](../README.md) — the plan, layout, and naming/secrets
  conventions all of the above assumes.
