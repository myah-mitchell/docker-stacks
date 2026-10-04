# Hosting cluster container stacks

Compose-based container definitions for a self-hosted homelab and colo cluster, deployed through [Komodo](https://github.com/moghtech/komodo) GitOps. Every service in the fleet is defined here; nothing here provisions an operating system.

Read [Conventions](docs/conventions.md) before adding or changing anything. Every other page assumes its naming rules, and `scripts/build.py` assumes its secrets rules.

## What this repo is part of

The buildout spans four repos, plus a docs site for everything that crosses them.

| Repo | Holds | Visibility |
| --- | --- | --- |
| fleet-stacks (this one) | Every container and stack definition | Public |
| [fleet-nixos](https://github.com/myah-mitchell/fleet-nixos) | The flake every VM's NixOS configuration is built from: the modules, the installer ISO, and the install and deploy commands | Public |
| [fleet-ansible](https://github.com/myah-mitchell/fleet-ansible) | The roles for the Proxmox hosts, and `site.yml`, the one run that builds the fleet | Public |
| [fleet-opentofu](https://github.com/myah-mitchell/opentofu) | The OpenTofu configuration that creates each VM blank, set to boot the installer ISO. Run by fleet-ansible's `site.yml` | Public |
| [docs](https://github.com/myah-mitchell/docs) | The [docs site](https://myah-mitchell.github.io/docs/): the fleet bootstrap runbooks and the Markdown style guide | Public |
| fleet-private | The real inventory and private values (`hosts.yml`, `group_vars/all/private.yml`), the VMs for OpenTofu (`opentofu/prod.tfvars`), each host's generated Komodo Stacks (`komodo/stacks/`) and NixOS values (`nixos/hosts/`), and the sops secrets. Ansible runs against its inventory | Private |

Every VM runs NixOS. Its configuration installs Docker and Komodo Periphery, creates the folders its stacks need, and opens their ports, so a new VM is a working Docker host with nothing done on it by hand.

## Where to start

Every VM is created by OpenTofu, installed from the fleet-nixos flake, and given its stacks by Komodo, in one run of fleet-ansible's `site.yml`. Komodo Core on km01 is the one thing started by hand, one time, because Komodo cannot deploy the stack it runs in before it has started.

1. [Conventions](docs/conventions.md) for naming and secrets.
2. [Fleet bootstrap](https://myah-mitchell.github.io/docs/fleet-bootstrap/) on the docs site, for the order VMs come up in and the page for each one.
3. [The foundation](https://myah-mitchell.github.io/docs/fleet-bootstrap/foundation/) to build km01 and ci01, the first two hosts.
4. [Stacks](docs/stacks.md) for what each stack in this repo actually deploys.
5. [Project layout](scripts/project-layout.md) if you are editing a container or adding a stack.

## Repo layout

| Path | Contents |
| --- | --- |
| `containers/<name>/` | One container definition: `compose.yaml`, `komodo.env`, `testing.env`, `README.md`, and `stack-README.md`, plus `setup.yaml`, `config/`, or `rules/` where needed |
| `stacks/<name>/` | A deployable composition of containers via Compose `extends` and `include`. Only `compose.yaml` is hand-written |
| `scripts/build.py` | Regenerates every stack's `komodo.env`, `.env`, `README.md`, and `setup.yaml` from the base templates plus each container's fragments |
| `scripts/project-layout.md` | The full mechanics of `build.py` and the generated-file conventions |

A container's `config/` is always safe to commit and never holds a real credential. It holds `.example` templates and non-sensitive files only. A real credential lives on the host instead, under `${DOCKER_VOLUMES}/${PROJECT_NAME}/<container>-secrets/`, bind-mounted in by the compose file, so a checkout stays disposable. See cloudflared, mailrise, komodo, or step-ca for the pattern.

Run `scripts/build.py` after adding a container to a stack, or after editing one of a container's own fragments. Those are its `komodo.env`, `stack-README.md`, `testing.env`, and `setup.yaml`.

Never hand-edit a stack's generated `komodo.env`, `.env`, `README.md`, or `setup.yaml`. The next run overwrites them.

## License

Copyright (C) 2026 Myah Mitchell. Licensed under the [GNU Affero General Public License v3.0 or later](LICENSE). You can use, modify, and share this code, but any modified version you distribute or offer over a network must be released under the same license with this notice kept.

The VictoriaMetrics, VictoriaLogs, and VictoriaTraces Grafana dashboards in `containers/grafana/config/dashboards/` come from [VictoriaMetrics](https://github.com/VictoriaMetrics/VictoriaMetrics) and keep their original Apache-2.0 license.
