# Create and Setup Required Folders
## Create Stack Folders

```bash
projectName="projectName"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

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

Set as Komodo variables; keep stable across restarts — rotating any of these invalidates every stored SSH key/vault secret and active session.

## Post-deploy: register the `ansible` repo

1. Bootstrap-phase SSH key: Semaphore is provisioned in Phase 2 (docker-stacks Phase 2 / "Home core platform bootstrap") with a static SSH key trusted by the `ansible` service user every host's `users` Ansible role creates — this is the same necessary-bootstrap-exception category as Komodo's manual `docker compose up -d` start (nothing better exists yet at this point in the sequence).
2. **Superseded in Phase 7**: once step-ca's SSH CA is live, switch Semaphore to a dedicated `semaphore` service principal using a short-lived, auto-renewed step-ca cert instead of the static key — closes the "if that one key ever leaks, it's valid forever" exposure down to hours. Don't skip this step once Phase 7 lands.
3. In the Semaphore UI: add a **Key Store** entry for that SSH identity, then one **Repository** (`ansible`) using a read-only GitHub **deploy key** (not a personal access token — see plan Risk #1, a deploy key's blast radius is scoped to that one repo). `dotfiles` doesn't need a Repository entry of its own — the `dotfiles` Ansible role clones it directly (plain HTTPS, no credential; `myah-mitchell/dotfiles` is public) as part of its own tasks, not through Semaphore's checkout.
4. Create a **Project** wrapping the `ansible` repo + its `hosts.yml` inventory, and **Templates** for the common playbook runs (full `provision.yml` re-run, and later the Phase 8 dotfiles-sync task).

## Create needed folders for postgres

```bash
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*
```

## Create needed folders for postgres-backup

```bash
mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-backup-*
```

## Restore from a dump (verify this actually works — an untested backup isn't a backup)

List available dumps (daily/weekly/monthly subfolders, gzip-compressed SQL):

```bash
docker exec -it ${projectName}-postgres-backup ls -la /backups
```

Restore into a *scratch* postgres instance first, never directly into the live one, to confirm the dump is actually valid before trusting it:

```bash
gunzip -c /opt/docker/volumes/$projectName/postgres-backup-data/daily/<dump-file>.sql.gz \
  | docker exec -i <scratch-postgres-container> psql -U <user> -d <db>
```
