# Bootstrap runbooks

The step-by-step runbooks for standing up each VM in the fleet, and the order they come up in.

Read [Conventions](conventions.md) first if you have not. Every runbook here assumes its naming and secrets rules.

## The pattern every VM follows

Each VM gets its base OS the same way: cloned from the shared `ubuntu-server` cloud-init template, which self-provisions on first boot by running ansible's `provision.yml` against `target: ubuntu_docker`. That installs Docker, the firewall, NTP, swap, node_exporter, and Komodo Periphery with no manual step. Periphery is gated behind `KOMODO: true`, already set for the whole `ubuntu_docker` group.

From that shared starting point, a VM's stack gets deployed one of two ways.

`km01` is the one deliberate exception, provisioned and started entirely by hand, because Komodo cannot GitOps-deploy itself the first time. See [km01 bootstrap](komodo-bootstrap.md).

Every other VM is registered as a Komodo Server resource and deployed through Komodo's GitOps flow. Provision the base OS, generate that VM's own Komodo onboarding key, then let Komodo do the rest. [ci01 bootstrap](ci01-bootstrap.md) works the pattern out in full for the first real case, and every doc after it follows the same shape.

The onboarding key is a permanent per-host step. Under Komodo's PKI auth, each host proves itself to Core once with a single-use key, the same way a new SSH host key gets accepted once, and Core and that host trust each other by their own keypairs from then on.

## Running order

| Order | VM | Role | Doc | Status |
| --- | --- | --- | --- | --- |
| 1 | `km01` | Komodo GitOps engine | [km01 bootstrap](komodo-bootstrap.md) | Up and healthy |
| 2 | `ci01` | Semaphore first, rest of core-infra later | [ci01 bootstrap](ci01-bootstrap.md) | In progress |
| 3 | `tf01` | Traefik hub, central Redis and `traefik-kop` | Not written | Blocked on Semaphore pushing `node_exporter_password` |
| 4 | `id01` | Authentik, identity | Not written | Not started |
| 5 | `pk01` | step-ca, internal PKI | Not written | Not started |
| 6 | `bh01` | `cloudflared` and `traefik-dmz`, DMZ edge | Not written | Not started |
| 7 | `ap01` | Vaultwarden and future replacements | Not written | Not started |

Pre-existing hosts (`bk01`, `mx01`, `vh01`, and the PVE hosts themselves) are not covered here. They predate this plan and are not provisioned by these runbooks.

## Reaching a stack before pk01 and id01 exist

Most stacks in this plan are gated behind `chain-authentik@file` and expect a real cert resolver. Neither works until `pk01` (step-ca) and `id01` (Authentik) are live.

Until then, deploy [Traefik bootstrap](traefik-bootstrap.md) on that VM. It is real Traefik routing on real hostnames, with self-signed TLS and `chain-no-auth@file` instead. Set the stack's `TRAEFIK_AUTH_CHAIN` to `chain-no-auth@file` when you deploy it. [ci01 bootstrap](ci01-bootstrap.md) step 9 works through it for the first real case.

This applies to every VM in the list above, which is why it lives here rather than being repeated in each runbook.

## Writing the next host's doc

Write a host's runbook when you actually reach that VM, not ahead of time. A doc written early describes steps that no longer apply by the time anyone follows it.

Name it after the host once a VM is just "provision, then deploy via Komodo" (`ci01-bootstrap.md`). Name it after the service only when something is structurally unique about that bootstrap, which so far means `komodo-bootstrap.md` alone.

Steps 1 to 4 of [ci01 bootstrap](ci01-bootstrap.md) are identical for every VM. Step 5's onboarding key is required for every future host. Step 9's `traefik-bootstrap` deploy applies until `system-agent` replaces it fleet-wide. Only the stack-specific steps after that differ.

## The rest of the docs

| Page | What it covers |
| --- | --- |
| [Conventions](conventions.md) | Naming and secrets rules every other page assumes |
| [km01 bootstrap](komodo-bootstrap.md) | `km01`, the one host built by hand |
| [ci01 bootstrap](ci01-bootstrap.md) | `ci01` and Semaphore, the template for every VM after it |
| [Semaphore setup](semaphore-setup.md) | Wiring Semaphore to the ansible repo and pushing the first real secret |
| [Traefik bootstrap](traefik-bootstrap.md) | The temporary per-VM Traefik used before `pk01` and `id01` exist |
| [Stacks](stacks.md) | What every stack in this repo deploys, independent of bootstrap order |
