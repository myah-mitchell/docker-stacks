# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/authentik` | Logs the stack's containers write to files |
| `/opt/docker/volumes/authentik` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="authentik"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for authentik

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/authentik/authentik-media` | `101000:101000` | Not set |
| `/opt/docker/volumes/authentik/authentik-templates` | `101000:101000` | Not set |
| `/opt/docker/volumes/authentik/authentik-certs` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="authentik"
mkdir -p /opt/docker/volumes/$projectName/authentik-media
sudo chown 101000:101000 /opt/docker/volumes/$projectName/authentik-media
mkdir -p /opt/docker/volumes/$projectName/authentik-templates
sudo chown 101000:101000 /opt/docker/volumes/$projectName/authentik-templates
mkdir -p /opt/docker/volumes/$projectName/authentik-certs
sudo chown 101000:101000 /opt/docker/volumes/$projectName/authentik-certs
```

</details>

## Create needed folders for postgres

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/authentik/postgres-data` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="authentik"
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-data
```

</details>

## Create needed folders for postgres-backup

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/authentik/postgres-backup-data` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="authentik"
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

## Create needed folders for geoipupdate

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/authentik/geoip-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="authentik"
mkdir -p /opt/docker/volumes/$projectName/geoip-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/geoip-data
```

</details>
