# Initial Deployment Requirements
## Prerequisites for using komodo

Copy `config/core.config.toml.example` to `secrets/core.config.toml` before the first start. The compose file mounts that exact path, and Docker silently creates an empty directory there when the file is missing, which makes Komodo fail at startup.

```bash
cp config/core.config.toml.example secrets/core.config.toml
```

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

`secrets/core.config.toml` is gitignored and never committed, matching every other container here that handles a real credential. See cloudflared or mailrise.

# Create and Setup Required Folders
## Create needed folders for komodo

```bash
mkdir -p /opt/docker/volumes/$projectName/komodo-keys
mkdir -p /opt/docker/volumes/$projectName/komodo-backups
mkdir -p /opt/docker/volumes/$projectName/komodo-sync
mkdir -p /opt/docker/volumes/$projectName/komodo-cache
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-*
```

`komodo-keys` holds the Ed25519 keypair Core generates on first boot. Losing that volume breaks trust with every Periphery agent in the fleet, and each one then has to be re-onboarded by hand. Back it up like the database directories, not like the disposable `komodo-cache`.
