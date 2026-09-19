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
## Create needed folders for komodo

`komodo-keys` holds the Ed25519 keypair Core generates on first boot. Losing that volume breaks trust with every Periphery agent in the fleet, and each one then has to be re-onboarded by hand. Back it up like the database directories, not like the disposable `komodo-cache`.
