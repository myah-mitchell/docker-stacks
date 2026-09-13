# Hosting cluster container stacks

Compose-based container definitions for a self-hosted homelab and colo cluster, deployed through [Komodo](https://github.com/moghtech/komodo) GitOps. Every service in the fleet is defined here; nothing here provisions an operating system.

Read [Conventions](docs/conventions.md) before adding or changing anything. Every other page assumes its naming rules, and `scripts/build.py` assumes its secrets rules.

## What this repo is part of

The buildout spans three repos.

| Repo | Holds | Visibility |
| --- | --- | --- |
| docker-stacks (this one) | Every container and stack definition | Public |
| [ansible](https://github.com/myah-mitchell/ansible) | OS-level provisioning for every VM, plus the pve role that builds the cloud-init template | Public |
| ansible-private | The real inventory and secrets: `hosts.yml` and `group_vars/all/private.yml`, layered over ansible's sanitised placeholders | Private |

The pve role's cloud-init template turns a freshly cloned Proxmox VM into a fully provisioned Docker host on first boot, with no manual SSH step.

## Where to start

km01 is the one deliberate exception to "everything is GitOps": Komodo cannot GitOps-deploy itself the first time, so it gets provisioned and started by hand. Every VM after it is provisioned by cloud-init and deployed through Komodo.

1. [Conventions](docs/conventions.md) for naming and secrets.
2. [Bootstrap runbooks](docs/README.md) for the order VMs come up in and the doc for each one.
3. [km01 bootstrap](docs/komodo-bootstrap.md) to stand up km01, the first host.
4. [Stacks](docs/stacks.md) for what each stack in this repo actually deploys.
5. [Project layout](scripts/project-layout.md) if you are editing a container or adding a stack.

## Repo layout

| Path | Contents |
| --- | --- |
| `containers/<name>/` | One container definition: `compose.yaml`, `komodo.env`, `testing.env`, `README.md`, and `stack-README.md`, plus `config/`, `secrets/`, or `rules/` where needed |
| `stacks/<name>/` | A deployable composition of containers via Compose `extends` and `include`. Only `compose.yaml` is hand-written |
| `scripts/build.py` | Regenerates every stack's `komodo.env`, `.env`, and `README.md` from the base templates plus each container's fragments |
| `scripts/project-layout.md` | The full mechanics of `build.py` and the generated-file conventions |

A container's `config/` is always safe to commit and never holds a real credential. Its `secrets/` holds the real ones and is gitignored, with a tracked `.gitkeep` so the folder exists. See cloudflared, mailrise, or komodo for the pattern.

Run `scripts/build.py` after adding a container to a stack, or after editing one of a container's own fragments. Those are its `komodo.env`, `stack-README.md`, and `testing.env`.

Never hand-edit a stack's generated `komodo.env`, `.env`, or `README.md`. The next run overwrites them.
