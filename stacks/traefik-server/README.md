# Traefik-kop Central Stack (Server) Overview

This will start up a Traefik stack with Traefik-kop and a password-protected Redis server that all Traefik-kop services can write to. This server will need to allow inbound 6379 (Redis) and then port 80/443 (HTTP/HTTPS). This compose file should only be deployed to one server.

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

## Create needed folders for traefik

```bash
mkdir -p /opt/docker/logs/$projectName/traefik
sudo chown 101000:101000 /opt/docker/logs/$projectName/traefik

mkdir -p /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-*
```

## Create needed folders for vmagent

```bash
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vmagent-*
```

## Create needed folders for vlagent

```bash
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vlagent-*
```

## Create needed folders for vector

```bash
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vector-*
```
