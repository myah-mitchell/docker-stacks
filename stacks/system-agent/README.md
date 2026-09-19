# System Stack (Agent) Overview

The standard per-VM bundle. Every VM in the fleet runs this one stack, and it is
the only stack most VMs run besides whatever that VM exists to host.

It does four jobs.

Traefik terminates TLS for that VM's own services and puts them behind the
Authentik auth chain, without needing tf01 to be involved. traefik-kop publishes
a router into tf01's shared Redis, but only for a service that also carries a
`kop-public.traefik.*` label, so reaching the wider network is a per-service
choice rather than a per-VM one.

vmagent, vlagent, vector and cadvisor are the VM's telemetry. Between them they
cover the host's own metrics from Node Exporter, per-container metrics from
cadvisor, Traefik's metrics and access log, and the host's journald, syslog and
file logs. Everything is written to ci01's VictoriaMetrics backend.

dockns keeps the VM's DNS records in step with the containers running on it.

dozzle-agent exposes this VM's container logs to a central Dozzle on port 7007.

Deploy it only once ci01, id01 and pk01 exist: it writes metrics to ci01, uses
id01 for the auth chain, and takes its Traefik certificate from pk01. Before
those are up, traefik-bootstrap is the temporary stand-in. Do not run both on one
VM, because they bind the same ports 80, 443 and 8443.

# Initial Deployment Requirements
## Prerequisites for using vmagent

### Setting Up Node Exporter

Node Exporter reports the host's own CPU, memory, disk and network. It runs on
the host rather than in a container, and the `monitoring` role in the ansible
repo installs and configures it. Run that role against the host before deploying
this stack. Nothing here has to be done by hand.

The role leaves four files in `/etc/node-exporter/` that matter to this stack:

| File | What it is |
| --- | --- |
| `node_exporter.crt` | The self-signed certificate Node Exporter serves on port 9100. vmagent mounts it as its CA and skips verification, since it is self-signed. |
| `config.yml` | Node Exporter's own TLS and basic-auth config, holding the bcrypt hash of this host's password. |
| `password` | The plaintext, readable only by the `node_exporter` user. The role reads it back on later runs so the password stays the same. |
| `scrape-password` | A second copy of the plaintext, owned by the host-side UID that Docker's user namespace maps this stack's vmagent onto. This is the one vmagent mounts. |

Every host gets a different password, generated on that host on the role's first
run. A host's vmagent only ever scrapes that same host's Node Exporter, so the
password never has to match between hosts, and no copy of it exists outside the
host it belongs to. That is why `NODE_EXPORTER_USER` is the only Node Exporter
value in this stack's environment: there is no password for Komodo to hold.

To rotate one host's password, set `node_exporter_password` for that host and run
the role again. To rotate every host's, delete `/etc/node-exporter/password` and
`/etc/node-exporter/password.bcrypt` first.

The role also opens port 9100 in UFW as the `Node-Exporter` application, so
vmagent can reach it.

## Prerequisites for using dockns

dockns drives two DNS providers per VM:

- **UniFi** (local connector) creates the internal alias so `<service>.<site>.
  myah-mitchell.com` resolves directly to the VM hosting it, on that site's own
  UniFi console. Every VM needs this.
- **Cloudflare** creates the external record for VMs that also host a
  publicly-reachable service (via `cloudflared` + `traefik-dmz`). Most VMs don't
  need this; only ones with a `kop-public`-labeled service meant to be internet
  reachable do.

### UniFi setup (every VM)

1. In that VM's site's UniFi console, generate a local API key with permission to
   manage DNS records (Settings → System → API, or wherever your controller version
   puts it).
2. Set `DOCKNS_UNIFI_HOST` to that console's own local URL, e.g.
   `https://192.168.1.1`, not `api.ui.com`. This is deliberately the local
   connector, not the remote/cloud one: internal DNS management shouldn't depend on
   UniFi's cloud API being reachable, and it keeps the traffic on the LAN. Home-site
   and cloud-site VMs point at their own site's console, so these values differ per
   site, don't copy one site's value to the other.
3. Set `DOCKNS_UNIFI_API_KEY` to the key from step 1.
4. Leave the account/site ID unset unless the console manages more than one UniFi
   site, because dockns auto-discovers the default site.

### Cloudflare setup (only VMs hosting a public service)

Set `DOCKNS_CF_API_KEY`/`DOCKNS_CF_ACCOUNT_ID`/`DOCKNS_CF_ZONE_ID`/`DOCKNS_WAN_IP`,
see [dockns' Cloudflare provider docs](https://codeberg.org/BrenekH/DockNS/src/branch/main/docs/name-servers/cloudflare.md)
for what each value is and where to find it in the Cloudflare dashboard.

# Create and Setup Required Folders
## Create Stack Folders

```bash
projectName="system"
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

## Create needed folders for vmagent

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vmagent-data
```

## Create needed folders for vlagent

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vlagent-data
```

## Create needed folders for vector

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vector-data
```

## Open the firewall for vector

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
sudo ufw allow from <internal-subnet> to any port 5140 proto tcp comment 'Vector syslog'
sudo ufw allow from <internal-subnet> to any port 5140 proto udp comment 'Vector syslog'
```

## Open the firewall for dozzle

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
sudo ufw allow from <internal-subnet> to any port 7007 proto tcp comment 'Dozzle agent'
```

## Create needed folders for dockns

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/dockns-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/dockns-data
```
