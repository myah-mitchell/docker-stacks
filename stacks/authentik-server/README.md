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

## Create needed folders for authentik

```bash
mkdir -p /opt/docker/volumes/$projectName/authentik-media
mkdir -p /opt/docker/volumes/$projectName/authentik-templates
mkdir -p /opt/docker/volumes/$projectName/authentik-certs
sudo chown 101000:101000 /opt/docker/volumes/$projectName/authentik-*
```

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

## Create needed folders for geoipupdate

```bash
mkdir -p /opt/docker/volumes/$projectName/geoip-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/geoip-*
```
