# Initial Deployment Requirements
## Prerequisites for using dockns

dockns drives two DNS providers per VM:

- **UniFi** (local connector) — creates the internal alias so `<service>.<site>.
  myah-mitchell.com` resolves directly to the VM hosting it, on that site's own
  UniFi console. Every VM needs this.
- **Cloudflare** — creates the external record for VMs that also host a
  publicly-reachable service (via `cloudflared` + `traefik-dmz`). Most VMs don't
  need this; only ones with a `kop-public`-labeled service meant to be internet
  reachable do.

### UniFi setup (every VM)

1. In that VM's site's UniFi console, generate a local API key with permission to
   manage DNS records (Settings → System → API, or wherever your controller version
   puts it).
2. Set `DOCKNS_UNIFI_HOST` to that console's own local URL, e.g.
   `https://192.168.1.1` — **not** `api.ui.com`. This is deliberately the local
   connector, not the remote/cloud one: internal DNS management shouldn't depend on
   UniFi's cloud API being reachable, and it keeps the traffic on the LAN. Home-site
   and cloud-site VMs point at their own site's console — these values differ per
   site, don't copy one site's value to the other.
3. Set `DOCKNS_UNIFI_API_KEY` to the key from step 1.
4. Leave the account/site ID unset unless the console manages more than one UniFi
   site — dockns auto-discovers the default site.

### Cloudflare setup (only VMs hosting a public service)

Set `DOCKNS_CF_API_KEY`/`DOCKNS_CF_ACCOUNT_ID`/`DOCKNS_CF_ZONE_ID`/`DOCKNS_WAN_IP` —
see [dockns' Cloudflare provider docs](https://codeberg.org/BrenekH/DockNS/src/branch/main/docs/name-servers/cloudflare.md)
for what each value is and where to find it in the Cloudflare dashboard.

# Create and Setup Required Folders
## Create needed folders for dockns

```bash
mkdir -p /opt/docker/volumes/$projectName/dockns-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/dockns-*
```