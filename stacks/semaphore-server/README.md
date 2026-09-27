# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/semaphore` | Logs the stack's containers write to files |
| `/opt/docker/volumes/semaphore` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="semaphore"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for semaphore

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/semaphore/semaphore-data` | `101001:101001` | Not set |
| `/opt/docker/volumes/semaphore/semaphore-config` | `101001:101001` | Not set |
| `/opt/docker/volumes/semaphore/semaphore-tmp` | `101001:101001` | Not set |
| `/opt/docker/volumes/semaphore/postgres-initdb` | `100000:100000` | `0755` |

| Seed file | Copied from | Owner | Mode |
| --- | --- | --- | --- |
| `/opt/docker/volumes/semaphore/postgres-initdb/10-tofu-state.sh` | `containers/semaphore/config/postgres-initdb/10-tofu-state.sh` | `100000:100000` | `0755` |

A seed file is copied only when the target does not exist.

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="semaphore"
mkdir -p /opt/docker/volumes/$projectName/semaphore-data
sudo chown 101001:101001 /opt/docker/volumes/$projectName/semaphore-data
mkdir -p /opt/docker/volumes/$projectName/semaphore-config
sudo chown 101001:101001 /opt/docker/volumes/$projectName/semaphore-config
mkdir -p /opt/docker/volumes/$projectName/semaphore-tmp
sudo chown 101001:101001 /opt/docker/volumes/$projectName/semaphore-tmp
mkdir -p /opt/docker/volumes/$projectName/postgres-initdb
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-initdb
sudo chmod 755 /opt/docker/volumes/$projectName/postgres-initdb
sudo test -e /opt/docker/volumes/$projectName/postgres-initdb/10-tofu-state.sh \
  || sudo curl -fsSL -o /opt/docker/volumes/$projectName/postgres-initdb/10-tofu-state.sh \
  https://raw.githubusercontent.com/myah-mitchell/docker-stacks/main/containers/semaphore/config/postgres-initdb/10-tofu-state.sh
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-initdb/10-tofu-state.sh
sudo chmod 755 /opt/docker/volumes/$projectName/postgres-initdb/10-tofu-state.sh
```

</details>

Semaphore runs as the image's own UID 1001, so its directories belong to host UID `101001` rather than `101000`.

## Generate the cookie/encryption secrets once

```bash
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_HASH
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_ENCRYPTION
head -c32 /dev/urandom | base64  # SEMAPHORE_ACCESS_KEY_ENCRYPTION
```

Set these as Komodo Secrets, and keep them stable across restarts. Rotating any of them invalidates every stored SSH key, every stored vault secret, and every active session.

## Wiring it to the ansible repo after deploy

Full walkthrough in [The Semaphore project](https://myah-mitchell.github.io/docs/fleet-bootstrap/foundation/semaphore-project/): the Project, the SSH credential, the repos, the inventory, the run's secrets, and a Template that runs against the fleet.

Two points worth knowing before you start.

The ansible repo is public, so its Repository entry needs no credential. Set *Access Key* to **None** rather than creating a deploy key. The dotfiles repo needs no Repository entry at all, because its own Ansible role clones it directly over plain HTTPS.

Semaphore reaches every host with a static SSH key trusted by the `ansible` service account. That is the same kind of bootstrap exception as Komodo's own manual first start. Once step-ca's SSH CA is live on pk01, replace it with a dedicated service principal on a short-lived, auto-renewed certificate.

## Create needed folders for postgres

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/semaphore/postgres-data` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="semaphore"
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-data
```

</details>

## Create needed folders for postgres-backup

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/semaphore/postgres-backup-data` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="semaphore"
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
