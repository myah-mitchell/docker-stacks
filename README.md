# Hosting cluster container stacks

Compose-based container definitions for a self-hosted homelab and colo cluster, deployed through [Komodo](https://github.com/moghtech/komodo) GitOps. Every service in the fleet is defined here; nothing here provisions an operating system.

Read [Conventions](docs/conventions.md) before adding or changing anything. Every other page assumes its naming rules, and `scripts/build.py` assumes its secrets rules.

## What this repo is part of

The buildout spans three repos, plus a docs site for everything that crosses them.

| Repo | Holds | Visibility |
| --- | --- | --- |
| docker-stacks (this one) | Every container and stack definition | Public |
| [ansible](https://github.com/myah-mitchell/ansible) | OS-level provisioning for every VM, plus the pve role that builds the cloud-init template | Public |
| [opentofu](https://github.com/myah-mitchell/opentofu) | The OpenTofu configuration that creates VMs by cloning the pve role's template, run by ansible's `site.yml` | Public |
| [docs](https://github.com/myah-mitchell/docs) | The [docs site](https://myah-mitchell.github.io/docs/): the fleet bootstrap runbooks and the Markdown style guide | Public |
| fleet-private | The real inventory and private values (`hosts.yml`, `group_vars/all/private.yml`), the VMs for OpenTofu (`opentofu/prod.tfvars`), and each host's generated Komodo Stacks (`komodo/stacks/`). Ansible runs against its inventory | Private |

The pve role's cloud-init template turns a freshly cloned Proxmox VM into a fully provisioned Docker host on first boot, with no manual SSH step.

## Where to start

Every VM is created by OpenTofu, provisioned by ansible, and given its stacks by Komodo, in one run. Komodo Core on km01 is the one thing started by hand, one time, because Komodo cannot deploy the stack it runs in before it has started.

1. [Conventions](docs/conventions.md) for naming and secrets.
2. [Fleet bootstrap](https://myah-mitchell.github.io/docs/fleet-bootstrap/) on the docs site, for the order VMs come up in and the page for each one.
3. [The foundation](https://myah-mitchell.github.io/docs/fleet-bootstrap/foundation/) to build km01 and ci01, the first two hosts.
4. [Stacks](docs/stacks.md) for what each stack in this repo actually deploys.
5. [Project layout](scripts/project-layout.md) if you are editing a container or adding a stack.

## Repo layout

| Path | Contents |
| --- | --- |
| `containers/<name>/` | One container definition: `compose.yaml`, `komodo.env`, `testing.env`, `README.md`, and `stack-README.md`, plus `config/` or `rules/` where needed |
| `stacks/<name>/` | A deployable composition of containers via Compose `extends` and `include`. Only `compose.yaml` is hand-written |
| `scripts/build.py` | Regenerates every stack's `komodo.env`, `.env`, and `README.md` from the base templates plus each container's fragments |
| `scripts/project-layout.md` | The full mechanics of `build.py` and the generated-file conventions |

A container's `config/` is always safe to commit and never holds a real credential. It holds `.example` templates and non-sensitive files only. A real credential lives on the host instead, under `${DOCKER_VOLUMES}/${PROJECT_NAME}/<container>-secrets/`, bind-mounted in by the compose file, so a checkout stays disposable. See cloudflared, mailrise, komodo, or step-ca for the pattern.

Run `scripts/build.py` after adding a container to a stack, or after editing one of a container's own fragments. Those are its `komodo.env`, `stack-README.md`, and `testing.env`.

Never hand-edit a stack's generated `komodo.env`, `.env`, or `README.md`. The next run overwrites them.

## License

Copyright (C) 2026 Myah Mitchell. Licensed under the [GNU Affero General Public License v3.0 or later](LICENSE). You can use, modify, and share this code, but any modified version you distribute or offer over a network must be released under the same license with this notice kept.

The VictoriaMetrics, VictoriaLogs, and VictoriaTraces Grafana dashboards in `containers/grafana/config/dashboards/` come from [VictoriaMetrics](https://github.com/VictoriaMetrics/VictoriaMetrics) and keep their original Apache-2.0 license.
