# Initial Deployment Requirements
## Prerequisites for using komodo

Copy `config/core.config.toml.example` (the unmodified upstream default, kept in git
purely as field-reference documentation) to `secrets/core.config.toml` and fill in a
real `[[git_provider]]` entry — this is what lets Komodo clone this (and any other
private) repo directly, without you ever pasting a token into the UI:

```toml
[[git_provider]]
domain = "github.com"
accounts = [
  { username = "<your-github-username>", token = "<fine-grained PAT, read-only, scoped to just this repo>" },
]
```

Same reasoning as the `ansible`/`proxmox-cloud-init` PAT already in use elsewhere in
this build: fine-grained, read-only, scoped to exactly the repo(s) it needs — if it
leaks, it only grants read access to something already readable by anyone with repo
access. Add a `[secrets]` block in the same file for any `[[VAR]]` reference used
across this repo's `komodo.env` files (`KOMODO_DB_PASSWORD`, `GLOBAL_PUID`, etc.) that
you want resolved centrally by Komodo rather than set per-stack.

`secrets/core.config.toml` is git-ignored — never committed, matches every other
container in this repo that handles a real credential (see `cloudflared`,
`mailrise`).

# Create and Setup Required Folders
## Create needed folders for komodo

```bash
mkdir -p /opt/docker/volumes/$projectName/komodo-backups
mkdir -p /opt/docker/volumes/$projectName/komodo-sync
mkdir -p /opt/docker/volumes/$projectName/komodo-cache
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-*
```