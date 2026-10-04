# Initial Deployment Requirements
## Prerequisites for using komodo

`core.config.toml` is seeded from the tracked example before the first start, and only when it is not already there. Docker silently creates an empty directory in place of a missing bind-mount file, which makes Komodo fail at startup.

It lives on the host rather than in the checkout so the checkout stays disposable, the same rule every other stack follows.

Leave the copy as it is for this repo. fleet-stacks is public, so Komodo needs no `[[git_provider]]` credential to clone it.

Add one, using the commented-out example already in the file, only when you point Komodo at a private repo. Scope the token to that repo, read-only, so a leak grants nothing more than repo access already does:

```toml
[[git_provider]]
domain = "github.com"
accounts = [
  { username = "<github-username>", token = "<fine-grained-read-only-pat>" },
]
```

Add a `[secrets]` block in the same file for any `[[VAR]]` reference used across this repo's `komodo.env` files that you would rather Komodo resolve centrally than set per stack.

The checkout only ever holds the `.example`. The filled-in copy stays under `/opt/docker/volumes`, which nothing in this repo can commit, matching every other container here that handles a real credential. See cloudflared or mailrise.

# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/komodo` | Logs the stack's containers write to files |
| `/opt/docker/volumes/komodo` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="komodo"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for ferretdb

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/komodo/ferretdb-data` | `101000:101000` | Not set |
| `/opt/docker/volumes/komodo/postgres-data` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="komodo"
mkdir -p /opt/docker/volumes/$projectName/ferretdb-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ferretdb-data
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-data
```

</details>

## Create needed folders for postgres-backup

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/komodo/postgres-backup-data` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="komodo"
mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-backup-data
```

</details>

## Restore from a dump

List available dumps (daily/weekly/monthly subfolders, gzip-compressed SQL):

```bash
docker exec -it ${projectName}-postgres-backup ls -la /backups
```

Restore into a *scratch* postgres instance first, never directly into the live one, to confirm the dump is actually valid before trusting it:

```bash
gunzip -c /opt/docker/volumes/$projectName/postgres-backup-data/daily/<dump-file>.sql.gz \
  | docker exec -i <scratch-postgres-container> psql -U <user> -d <db>
```

## Create needed folders for komodo

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/komodo/komodo-keys` | `101000:101000` | Not set |
| `/opt/docker/volumes/komodo/komodo-backups` | `101000:101000` | Not set |
| `/opt/docker/volumes/komodo/komodo-sync` | `101000:101000` | Not set |
| `/opt/docker/volumes/komodo/komodo-cache` | `101000:101000` | Not set |
| `/opt/docker/volumes/komodo/komodo-secrets` | `101000:101000` | `0700` |

| Seed file | Copied from | Owner | Mode |
| --- | --- | --- | --- |
| `/opt/docker/volumes/komodo/komodo-secrets/core.config.toml` | `containers/komodo/config/core.config.toml.example` | `101000:101000` | `0600` |

A seed file is copied only when the target does not exist.

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="komodo"
mkdir -p /opt/docker/volumes/$projectName/komodo-keys
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-keys
mkdir -p /opt/docker/volumes/$projectName/komodo-backups
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-backups
mkdir -p /opt/docker/volumes/$projectName/komodo-sync
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-sync
mkdir -p /opt/docker/volumes/$projectName/komodo-cache
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-cache
mkdir -p /opt/docker/volumes/$projectName/komodo-secrets
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-secrets
sudo chmod 700 /opt/docker/volumes/$projectName/komodo-secrets
sudo test -e /opt/docker/volumes/$projectName/komodo-secrets/core.config.toml \
  || sudo curl -fsSL -o /opt/docker/volumes/$projectName/komodo-secrets/core.config.toml \
  https://raw.githubusercontent.com/myah-mitchell/fleet-stacks/main/containers/komodo/config/core.config.toml.example
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-secrets/core.config.toml
sudo chmod 600 /opt/docker/volumes/$projectName/komodo-secrets/core.config.toml
```

</details>

`komodo-keys` holds the Ed25519 keypair Core generates on first boot. Losing that volume breaks trust with every Periphery agent in the fleet, and each one then has to be re-onboarded by hand. Back it up like the database directories, not like the disposable `komodo-cache`.

## Open the firewall for komodo

The host's NixOS configuration opens these when the host is deployed.

| Port | Protocol | Allowed from | Used for |
| --- | --- | --- | --- |
| `9120` | tcp | Any address | Komodo Core |
