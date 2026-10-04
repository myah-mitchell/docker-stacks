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

## Create needed folders for cloudflared

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/traefik/cloudflared-config` | `101000:101000` | Not set |
| `/opt/docker/volumes/traefik/cloudflared-secrets` | `101000:101000` | `0700` |

| Seed file | Copied from | Owner | Mode |
| --- | --- | --- | --- |
| `/opt/docker/volumes/traefik/cloudflared-config/config.yml` | `containers/cloudflared/config/config.yml.example` | `101000:101000` | Not set |

A seed file is copied only when the target does not exist.

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="traefik"
mkdir -p /opt/docker/volumes/$projectName/cloudflared-config
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cloudflared-config
mkdir -p /opt/docker/volumes/$projectName/cloudflared-secrets
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cloudflared-secrets
sudo chmod 700 /opt/docker/volumes/$projectName/cloudflared-secrets
sudo test -e /opt/docker/volumes/$projectName/cloudflared-config/config.yml \
  || sudo curl -fsSL -o /opt/docker/volumes/$projectName/cloudflared-config/config.yml \
  https://raw.githubusercontent.com/myah-mitchell/fleet-stacks/main/containers/cloudflared/config/config.yml.example
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cloudflared-config/config.yml
```

</details>

The ingress config is copied from the tracked example only when it is not already there, so a filled-in `config.yml` is never overwritten.

The tunnel credentials file goes in `cloudflared-secrets/`, covered below, so the config directory never needs to hold anything sensitive. Both live on the host rather than in the repo checkout because Periphery re-clones over its run directory, which would take any file written inside it along with it.

## One-time tunnel creation (from an admin machine, not this container)

1. Install the `cloudflared` CLI locally and run `cloudflared tunnel login`. It opens a browser and authorizes against your Cloudflare account/zone (`myah-mitchell.com`).
2. `cloudflared tunnel create home-edge` (the cloud site's edge, if it's ever added, would be a separate `cloud-edge` tunnel). It writes a credentials JSON to `~/.cloudflared/<tunnel-id>.json` and prints the tunnel ID.
3. Copy that JSON file onto `bh01` as `/opt/docker/volumes/$projectName/cloudflared-secrets/<tunnel-id>.json`, then `sudo chmod 600` it and `sudo chown 101000:101000` it. It never goes in the config directory, which only ever holds non-secret files.
4. In `/opt/docker/volumes/$projectName/cloudflared-config/config.yml`, seeded above, fill in the real `<tunnel-id>` in both the `tunnel:` and `credentials-file:` lines (the latter points at `/etc/cloudflared/secrets/`, where the credentials directory is mounted), and add an `ingress` entry per public hostname.
5. `cloudflared tunnel route dns home-edge vault.myah-mitchell.com` (repeat per hostname). That creates the public CNAME in Cloudflare DNS automatically, no manual DNS-record step needed.

No Komodo secret is needed for this container specifically. The credentials file is host-resident (under `/opt/docker/volumes/`, never leaves `bh01`), the same "sensitive file lives on disk, not in an env var" pattern as step-ca's root key. Rotate by repeating steps 2 to 5 with a new tunnel name and deleting the old one (`cloudflared tunnel delete home-edge`) once cutover is confirmed.
