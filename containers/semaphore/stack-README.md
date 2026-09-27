# Initial Deployment Requirements
## Prerequisites for using semaphore

# Create and Setup Required Folders
## Create needed folders for semaphore

Semaphore runs as the image's own UID 1001, so its directories belong to host UID `101001` rather than `101000`.

`nix-data` is mounted at `/nix`. The `nix` service fills it on the first deploy and hands every file in it to the folder's owner, which lets Semaphore run nix as its own user with no daemon.

## Generate the cookie/encryption secrets once

```bash
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_HASH
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_ENCRYPTION
head -c32 /dev/urandom | base64  # SEMAPHORE_ACCESS_KEY_ENCRYPTION
```

Set these as Komodo Secrets, and keep them stable across restarts. Rotating any of them invalidates every stored SSH key, every stored vault secret, and every active session.

## Give the runs nix

The playbooks that install and deploy a NixOS host call `nix`. A run sees only the variables Semaphore hands it, so set these three in the Variable Group of every Template that runs those playbooks.

| Variable | Tab | Value |
| --- | --- | --- |
| `PATH` | *Variables* | The container's own `PATH`, then `:/nix/var/nix/profiles/default/bin` |
| `NIX_CONFIG` | *Variables* | The two lines below |
| `SOPS_AGE_KEY` | *Secrets* | The age private key that decrypts the fleet's secrets |

All three go in the *Environment Variables* section of their tab.

A `PATH` set here replaces the one a run would otherwise get, so it has to repeat the container's. Read that one from the running container:

```bash
docker exec semaphore-semaphore printenv PATH
```

`NIX_CONFIG` holds two settings, one on each line:

```ini
experimental-features = nix-command flakes
sandbox = false
```

The first turns on the flake commands. The second turns off the build sandbox, which a container without privileges cannot set up.

The container's `PATH` names the version of Ansible in the image. Read it again after the image changes.

## Wiring it to the ansible repo after deploy

Full walkthrough in [The Semaphore project](https://myah-mitchell.github.io/docs/fleet-bootstrap/foundation/semaphore-project/): the Project, the SSH credential, the repos, the inventory, the run's secrets, and a Template that runs against the fleet.

Two points worth knowing before you start.

The ansible repo is public, so its Repository entry needs no credential. Set *Access Key* to **None** rather than creating a deploy key. The dotfiles repo needs no Repository entry at all, because its own Ansible role clones it directly over plain HTTPS.

Semaphore reaches every host with a static SSH key trusted by the `ansible` service account. That is the same kind of bootstrap exception as Komodo's own manual first start. Once step-ca's SSH CA is live on pk01, replace it with a dedicated service principal on a short-lived, auto-renewed certificate.
