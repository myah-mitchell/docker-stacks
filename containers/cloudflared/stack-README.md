# Initial Deployment Requirements
## Prerequisites for using cloudflared

# Create and Setup Required Folders
## Create needed folders for cloudflared

```bash
mkdir -p /opt/docker/stacks/$projectName/cloudflared/config
```

## One-time tunnel creation (from an admin machine, not this container)

1. Install the `cloudflared` CLI locally and run `cloudflared tunnel login` — opens a browser, authorizes against your Cloudflare account/zone (`example.com`).
2. `cloudflared tunnel create h1-edge` (colo's edge, if it's ever added, would be a separate `d1-edge` tunnel) — writes a credentials JSON to `~/.cloudflared/<tunnel-id>.json` and prints the tunnel ID.
3. Copy that JSON file onto `vm-edge` as `config/<tunnel-id>.json` (same folder as `config.yml`, git-ignored — see root `.gitignore`).
4. Copy `config/config.yml.example` to `config/config.yml`, fill in the real `<tunnel-id>` in both the `tunnel:` and `credentials-file:` lines, and add an `ingress` entry per public hostname.
5. `cloudflared tunnel route dns h1-edge vault.example.com` (repeat per hostname) — creates the public CNAME in Cloudflare DNS automatically, no manual DNS-record step needed.

No Komodo secret needed for this container specifically — the credentials file is host-resident (git-ignored, never leaves `vm-edge`), the same "sensitive file lives on disk, not in an env var" pattern as step-ca's root key. Rotate by repeating steps 2–5 with a new tunnel name and deleting the old one (`cloudflared tunnel delete h1-edge`) once cutover is confirmed.
