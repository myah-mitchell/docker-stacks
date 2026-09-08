# Bootstrap runbooks

The step-by-step runbooks for standing up each VM in the fleet, and the order they come up in.

Read [Conventions](conventions.md) first if you have not. Every runbook here assumes its naming and secrets rules.

## The pattern every VM follows

Each VM gets its base OS the same way: cloned from the shared `ubuntu-server-2604` cloud-init template, which self-provisions on first boot by running ansible's `provision.yml` against `target: ubuntu_docker`. That installs Docker, the firewall, NTP, swap, node_exporter, and Komodo Periphery with no manual step. Periphery is gated behind `KOMODO: true`, already set on the `ubuntu_docker` inventory entry every Docker VM provisions against.

From that shared starting point, a VM's stack gets deployed one of two ways.

km01 is the one deliberate exception, provisioned and started entirely by hand, because Komodo cannot GitOps-deploy itself the first time. See [km01 bootstrap](komodo-bootstrap.md).

Every other VM is registered as a Komodo Server resource and deployed through Komodo's GitOps flow. Provision the base OS, generate that VM's own Komodo onboarding key, then let Komodo do the rest. That half is the same for every host and is written once, in [Provisioning a VM](provision-a-vm.md). Each host runbook's first step is a pointer to it.

The onboarding key is a permanent per-host step. Under Komodo's PKI auth, each host proves itself to Core once with a single-use key, the same way a new SSH host key gets accepted once, and Core and that host trust each other by their own keypairs from then on.

## Running order

| Order | VM | Role | Doc | Status |
| --- | --- | --- | --- | --- |
| 1 | km01 | Komodo GitOps engine | [km01 bootstrap](komodo-bootstrap.md) | Up and healthy |
| 1.1 | any | Provisioning a VM, the shared first step of every host below | [Provisioning a VM](provision-a-vm.md) | In progress |
| 2 | ci01 | Overview, then the three stacks below | [ci01 bootstrap](ci01-bootstrap.md) | In progress |
| 2.1 | ci01 | traefik-bootstrap, temporary routing so the other two are reachable | [Traefik bootstrap](traefik-bootstrap.md) | Written, not yet run |
| 2.2 | ci01 | Semaphore, ansible's runner | [Semaphore setup](semaphore-setup.md) | In progress |
| 2.3 | ci01 | VictoriaMetrics, the fleet's metrics, logs, and traces backend | [VictoriaMetrics setup](victoriametrics-setup.md) | Written, not yet run |
| 3 | tf01 | Traefik hub, central Redis and traefik-kop | [tf01 bootstrap](tf01-bootstrap.md) | Written, not yet run |
| 4 | id01 | Authentik, identity | [id01 bootstrap](id01-bootstrap.md) | Written, not yet run |
| 5 | pk01 | step-ca, internal PKI | [pk01 bootstrap](pk01-bootstrap.md) | Written, not yet run |
| 6 | bh01 | cloudflared and traefik-dmz, DMZ edge | [bh01 bootstrap](bh01-bootstrap.md) | Written, not yet run |
| 7 | ap01 | Vaultwarden and future replacements | Not written | No stack exists in this repo yet |

Row 1.1 is not a VM of its own. It is the provisioning procedure every host from ci01 down runs before anything else, listed here because it is the first thing you do on each of them.

The 2.x rows are ci01's three stacks. Each needs real work beyond a Komodo Stack resource, so each has a doc rather than a step, and ci01's own runbook is an overview that hands off to them in order.

The order between them is load-bearing. 2.1 is what makes the other two reachable at all, and 2.2's step 13 pushes the real node_exporter password that 2.3 scrapes with.

Row 2.1 is not only ci01's. id01 and pk01 deploy the same stack on their own hosts, from the same doc.

"Written, not yet run" means the page was assembled from the compose files, the `komodo.env` keys, and the generated stack README, and then checked against them. No part of it has been followed against a real host. Treat every UI label and every wait time in those six as needing confirmation on the first real run, and correct the page as you go.

ap01 is the exception in more than status. Vaultwarden has no directory under `containers/`, so there is no stack to point a runbook at. Building the container comes first.

tf01 and bh01 carry one more caveat. Both depend on two directives that are commented out in `containers/traefik/compose.yaml` today, and neither can be enabled from Komodo's UI. See [What has to change in the repo first](tf01-bootstrap.md#what-has-to-change-in-the-repo-first).

Pre-existing hosts (bk01, mx01, vh01, and the PVE hosts themselves) are not covered here. They predate this plan and are not provisioned by these runbooks.

## Reaching a stack before pk01 and id01 exist

Most stacks in this plan are gated behind `chain-authentik@file` and expect a real cert resolver. Neither works until pk01 (step-ca) and id01 (Authentik) are live.

Until then, deploy [Traefik bootstrap](traefik-bootstrap.md) on that VM. It is real Traefik routing on real hostnames, with self-signed TLS and `chain-no-auth@file` instead. Set the stack's `TRAEFIK_AUTH_CHAIN` to `chain-no-auth@file` when you deploy it. [ci01 bootstrap](ci01-bootstrap.md) step 2 works through it for the first real case.

This applies to every VM in the list above, which is why it lives here rather than being repeated in each runbook.

## How the host runbooks are shaped

Anything identical across hosts lives in its own doc, and each host runbook points at it. [Provisioning a VM](provision-a-vm.md) is one, and [Traefik bootstrap](traefik-bootstrap.md) is the other. A host runbook's own pages are spent on what is actually different: the stack, its folders, its firewall, the Secrets it needs, and how to tell whether it worked.

Split a step out into its own doc when a second host will run it, or when a stack has real work after its deploy. Keep it inline when neither is true. ci01 is all pointers because all four of its steps qualify. The other four host runbooks point out once, for provisioning, and then deploy and verify in place, because their remaining steps are one-host-only and have no second reader.

The onboarding key in step 5 of provisioning is required for every future host, permanently. The traefik-bootstrap deploy applies to any VM whose own stack is not itself a Traefik, so id01 and pk01 need it while tf01 and bh01 do not.

Name a runbook after the host once a VM is just "provision, then deploy via Komodo" (`ci01-bootstrap.md`). Name it after the service when something is structurally unique about that bootstrap, which so far means `komodo-bootstrap.md` alone. Name it after the procedure when it is not tied to a host at all (`provision-a-vm.md`).

A page written before its VM exists is a draft, however carefully it was checked against the repo. Correct it while you follow it, and move its status out of "Written, not yet run" when you are done.

## The rest of the docs

Every runbook, stack doc, and shared procedure is in [Running order](#running-order) above. These two are not tied to any host or stack.

| Page | What it covers |
| --- | --- |
| [Conventions](conventions.md) | Naming and secrets rules every other page assumes |
| [Stacks](stacks.md) | What every stack in this repo deploys, independent of bootstrap order |
