# Initial Deployment Requirements
## Prerequisites for using semaphore

# Create and Setup Required Folders
## Create needed folders for semaphore

Semaphore runs as the image's own UID 1001, so its directories belong to host UID `101001` rather than `101000`.

`nix-data` is mounted at `/nix`. The `nix` service fills it on the first deploy and hands every file in it to the folder's owner, which lets Semaphore run nix as its own user with no daemon.

## Memory

The Semaphore container gets 4G of memory (`SEMAPHORE_MEM_LIMIT`) and 4.5G with swap (`SEMAPHORE_MEM_SWAP_LIMIT`), in place of the stack's `MEM_LIMIT` and `MEM_SWAP_LIMIT`. A run that installs or deploys a NixOS host evaluates the host's system in the container, which takes about 1 GB, and the playbooks run one evaluation at a time. Raise both if a run is killed for running out of memory. The stack's other containers keep the default.

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

### What a compromise reaches

Treat the Semaphore container as holding the keys to the whole fleet, because it does.

- `SOPS_AGE_KEY` is the deploy key. It decrypts every sops file in fleet-private: Ansible's secrets, the fleet's secrets, and every host's SSH private keys.
- The SSH key in the Key Store logs in to the deploy account, which is root on every host through sudo.
- The Proxmox API token can change or delete every VM of the fleet.
- The Nix store at `/nix` is the `nix-data` folder, and the Semaphore user can write to all of it. Code that runs as that user can replace `nix`, `sops`, `ssh` or any other program in the store, and the change outlives a redeploy of the stack and a reinstall of the host.
- With `sandbox = false`, anything nix builds in the container runs as the Semaphore user and can read the run's variables and checkouts. The hosts' systems are built on the hosts, but the flake's own commands and the installer ISO are built here. Every flake input, and every repository a run checks out, is trusted with the run's secrets.

After a suspected compromise, do all of the following before the next run:

1. Stop the stack and empty `nix-data`, then deploy the stack again so that the `nix` container fills the store from its image. Add `sops` again, as below.
2. Make a new deploy age key. Put its public key in `.sops.yaml` in place of the old one, run `sops updatekeys` and then `sops rotate -i` on every sops file in fleet-private, and commit.
3. Make a new SSH key for the deploy account, put its public key in the fleet's values, and deploy to every host from the control shell.
4. Delete the Proxmox API token and make a new one.
5. Make new SSH host keys, since the old ones could be read. For each host, remove `secrets/host-keys/<host>.yaml` from fleet-private, run `new-host-key` for the host, commit, and install the host again. The installer ISO holds no key, and needs no change.

### Add sops

Ansible decrypts the fleet's secrets with `sops`, which neither image has. Add it to nix's default profile one time, after the first deploy:

```bash
docker exec semaphore-semaphore /nix/var/nix/profiles/default/bin/nix \
  --extra-experimental-features 'nix-command flakes' \
  profile add --profile /nix/var/nix/profiles/default nixpkgs#sops
```

The profile is in `nix-data`, so `sops` is still there after a redeploy, and it is on the `PATH` set above. Run the command again after `nix-data` has been emptied and filled again.

## Wiring it to the ansible repo after deploy

Full walkthrough in [The Semaphore project](https://myah-mitchell.github.io/docs/fleet-bootstrap/foundation/semaphore-project/): the Project, the SSH credential, the repos, the inventory, the run's secrets, and a Template that runs against the fleet.

Two points worth knowing before you start.

The ansible repo is public, so its Repository entry needs no credential. Set *Access Key* to **None** rather than creating a deploy key. The dotfiles repo needs no Repository entry at all, because its own Ansible role clones it directly over plain HTTPS.

Semaphore reaches every host with a static SSH key trusted by the `ansible` service account. That is the same kind of bootstrap exception as Komodo's own manual first start. Once step-ca's SSH CA is live on pk01, replace it with a dedicated service principal on a short-lived, auto-renewed certificate.

The nixos-fleet commands a run starts (`host-state`, `install-host`, `deploy-host`) open their own SSH connections and name no key file, so they reach the key only through the SSH agent Semaphore starts for the run, by the `SSH_AUTH_SOCK` they inherit from `ansible-playbook`. That has not been tried. If the first run fails at the `nixos` stage with a publickey error, this is the place to look.
