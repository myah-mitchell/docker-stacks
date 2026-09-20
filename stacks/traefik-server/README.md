# Traefik-kop Central Stack (Server) Overview

This will start up a Traefik stack with Traefik-kop and a password-protected Redis server that all Traefik-kop services can write to. This server will need to allow inbound 6379 (Redis) and then port 80/443 (HTTP/HTTPS). This compose file should only be deployed to one server.

# Create and Setup Required Folders
## Create Stack Folders

```bash
projectName="traefik"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

## Create needed folders for traefik

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/logs/$projectName/traefik
sudo chown 101000:101000 /opt/docker/logs/$projectName/traefik
sudo chmod 755 /opt/docker/logs/$projectName/traefik
mkdir -p /opt/docker/volumes/$projectName/traefik-certs
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-plugins
```

The log folder is mode 755 rather than group-writable. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so it would exit 1 every five minutes and access.log would grow forever.

## Open the firewall for traefik

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
sudo ufw allow 80/tcp comment 'Traefik HTTP'
sudo ufw allow 443/tcp comment 'Traefik HTTPS'
sudo ufw allow 8443/tcp comment 'Traefik HTTPS (alt)'
```

## Open the firewall for redis

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
sudo ufw allow from <internal-subnet> to any port 6379 proto tcp comment 'traefik-kop Redis'
```
