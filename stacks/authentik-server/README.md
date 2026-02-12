# Authentik Stack (Server) Overview

The `stacks\authentic-server\compose.yaml` will start up an Authentik stack with a server and workinger. This stack should only be ran once per environment.

# Create and Setup Requried Folders
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

## Create needed folders for geoipupdate

```bash
mkdir -p /opt/docker/volumes/$projectName/geoip-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/geoip-*
```
