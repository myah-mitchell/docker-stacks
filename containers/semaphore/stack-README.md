# Initial Deployment Requirements
## Prerequisites for using semaphore

# Create and Setup Required Folders
## Create needed folders for semaphore

```bash
mkdir -p /opt/docker/volumes/$projectName/semaphore-data
mkdir -p /opt/docker/volumes/$projectName/semaphore-config
mkdir -p /opt/docker/volumes/$projectName/semaphore-tmp
sudo chown 101000:101000 /opt/docker/volumes/$projectName/semaphore-*
```

## Generate the cookie/encryption secrets once

```bash
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_HASH
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_ENCRYPTION
head -c32 /dev/urandom | base64  # SEMAPHORE_ACCESS_KEY_ENCRYPTION
```

Set these as Komodo Secrets, and keep them stable across restarts. Rotating any of them invalidates every stored SSH key, every stored vault secret, and every active session.

## Wiring it to the ansible repo after deploy

Full walkthrough in [docs/semaphore-setup.md](../../docs/semaphore-setup.md): the Project, the SSH credential, the repo, a real inventory, the private variables, and a Template that runs against the fleet.

Two points worth knowing before you start.

The ansible repo is public, so its Repository entry needs no credential. Set *Access Key* to **None** rather than creating a deploy key. The dotfiles repo needs no Repository entry at all, because its own Ansible role clones it directly over plain HTTPS.

Semaphore reaches every host with a static SSH key trusted by the `ansible` service account. That is the same kind of bootstrap exception as Komodo's own manual first start. Once step-ca's SSH CA is live on pk01, replace it with a dedicated service principal on a short-lived, auto-renewed certificate.
