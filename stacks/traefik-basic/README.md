# Traefik Stack (Basic) Overview

This will start up a basic Traefik stack without Traefik-kop support or any monitoring/log collection. This is a working Traefik stack with a socket-proxy, custom error pages, and access log rotation.

# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/traefik` | Logs the stack's containers write to files |
| `/opt/docker/volumes/traefik` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="traefik"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for traefik

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/logs/traefik/traefik` | `101000:101000` | `0755` |
| `/opt/docker/volumes/traefik/traefik-certs` | `101000:101000` | Not set |
| `/opt/docker/volumes/traefik/traefik-plugins` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="traefik"
mkdir -p /opt/docker/logs/$projectName/traefik
sudo chown 101000:101000 /opt/docker/logs/$projectName/traefik
sudo chmod 755 /opt/docker/logs/$projectName/traefik
mkdir -p /opt/docker/volumes/$projectName/traefik-certs
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-plugins
```

</details>

The log folder is mode 755 rather than group-writable. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so it would exit 1 every five minutes and access.log would grow forever.

## Open the firewall for traefik

The host's NixOS configuration opens these when the host is deployed.

| Port | Protocol | Allowed from | Used for |
| --- | --- | --- | --- |
| `80` | tcp | Any address | Traefik HTTP |
| `443` | tcp | Any address | Traefik HTTPS |
| `8443` | tcp | Any address | Traefik HTTPS (alt) |
