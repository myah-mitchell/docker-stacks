# Initial Deployment Requirements
## Prerequisites for using cloudflared

# Create and Setup Required Folders
## Create needed folders for cloudflared

```bash
mkdir -p /opt/docker/volumes/$projectName/cloudflared-config
mkdir -p /opt/docker/volumes/$projectName/cloudflared-secrets
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cloudflared-config
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cloudflared-secrets
sudo chmod 700 /opt/docker/volumes/$projectName/cloudflared-secrets
```

Seed the ingress config from the tracked example, which this repo serves publicly, so no checkout has to exist yet:

```bash
sudo curl -fsSL -o /opt/docker/volumes/$projectName/cloudflared-config/config.yml \
  https://raw.githubusercontent.com/myah-mitchell/docker-stacks/main/containers/cloudflared/config/config.yml.example
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cloudflared-config/config.yml
```

The tunnel credentials file goes in `cloudflared-secrets/`, covered below, so the config directory never needs to hold anything sensitive. Both live on the host rather than in the repo checkout because Periphery re-clones over its run directory, which would take any file written inside it along with it.

## One-time tunnel creation (from an admin machine, not this container)

1. Install the `cloudflared` CLI locally and run `cloudflared tunnel login`. It opens a browser and authorizes against your Cloudflare account/zone (`myah-mitchell.com`).
2. `cloudflared tunnel create home-edge` (the cloud site's edge, if it's ever added, would be a separate `cloud-edge` tunnel). It writes a credentials JSON to `~/.cloudflared/<tunnel-id>.json` and prints the tunnel ID.
3. Copy that JSON file onto `bh01` as `/opt/docker/volumes/$projectName/cloudflared-secrets/<tunnel-id>.json`, then `sudo chmod 600` it and `sudo chown 101000:101000` it. It never goes in the config directory, which only ever holds non-secret files.
4. In `/opt/docker/volumes/$projectName/cloudflared-config/config.yml`, seeded above, fill in the real `<tunnel-id>` in both the `tunnel:` and `credentials-file:` lines (the latter points at `/etc/cloudflared/secrets/`, where the credentials directory is mounted), and add an `ingress` entry per public hostname.
5. `cloudflared tunnel route dns home-edge vault.myah-mitchell.com` (repeat per hostname). That creates the public CNAME in Cloudflare DNS automatically, no manual DNS-record step needed.

No Komodo secret is needed for this container specifically. The credentials file is host-resident (under `/opt/docker/volumes/`, never leaves `bh01`), the same "sensitive file lives on disk, not in an env var" pattern as step-ca's root key. Rotate by repeating steps 2 to 5 with a new tunnel name and deleting the old one (`cloudflared tunnel delete home-edge`) once cutover is confirmed.
