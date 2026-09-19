# Initial Deployment Requirements
## Prerequisites for using komodo

The generated folder commands for komodo seed `core.config.toml` from the tracked example before the first start, and only when it is not already there. Docker silently creates an empty directory in place of a missing bind-mount file, which makes Komodo fail at startup.

It lives on the host rather than in the checkout so the checkout stays disposable, the same rule every other stack follows.

Leave the copy as it is for this repo. docker-stacks is public, so Komodo needs no `[[git_provider]]` credential to clone it.

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
## Create Stack Folders

```bash
projectName="komodo"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

## Create needed folders for ferretdb

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/ferretdb-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ferretdb-data
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-data
```

## Create needed folders for postgres-backup

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-backup-data
```

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

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
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
  https://raw.githubusercontent.com/myah-mitchell/docker-stacks/main/containers/komodo/config/core.config.toml.example
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-secrets/core.config.toml
sudo chmod 600 /opt/docker/volumes/$projectName/komodo-secrets/core.config.toml
```

`komodo-keys` holds the Ed25519 keypair Core generates on first boot. Losing that volume breaks trust with every Periphery agent in the fleet, and each one then has to be re-onboarded by hand. Back it up like the database directories, not like the disposable `komodo-cache`.

## Open the firewall for komodo

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
sudo ufw allow 9120/tcp comment 'Komodo Core'
```
