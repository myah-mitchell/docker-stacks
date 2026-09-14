# tf01 bootstrap runbook

tf01 is the fleet's Traefik hub. It runs the first real Traefik in the plan, with a Let's Encrypt cert resolver instead of self-signed TLS, and it holds the shared Redis that every other VM's traefik-kop publishes into.

Its stack is traefik-server. That is traefik-agent plus a Redis master, and traefik-agent is in turn traefik-basic plus the monitoring sidecars plus traefik-kop, so ten services come up on one VM.

tf01 does not get traefik-bootstrap. It is the real Traefik, so there is nothing to stand in for.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules, and it assumes you have already worked through [ci01 bootstrap](ci01-bootstrap.md).

## Contents

- [What tf01 turns on in the base Traefik service](#what-tf01-turns-on-in-the-base-traefik-service)
- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Provision the VM](#1-provision-the-vm)
- [2. Create the runtime folders](#2-create-the-runtime-folders)
- [3. Open the firewall](#3-open-the-firewall)
- [4. Create the five Komodo Secrets](#4-create-the-five-komodo-secrets)
- [5. Create the Stack resource for traefik-server](#5-create-the-stack-resource-for-traefik-server)
- [6. Verify](#6-verify)
- [7. First access](#7-first-access)
- [8. Point the other VMs at this Redis](#8-point-the-other-vms-at-this-redis)
- [What's next](#whats-next)

## What tf01 turns on in the base Traefik service

Every Traefik stack in the fleet extends the one `.traefik` service in `containers/traefik/compose.yaml`. Two parts of it matter here first, and both are driven by values in this stack's `komodo.env` rather than by anything tf01-specific in the compose file.

### The Redis provider

Aggregating the routers every other VM's traefik-kop publishes is tf01's entire reason to exist. Its Traefik reads them from Redis:

```yaml
- ${TRAEFIK_REDIS_ENDPOINTS:+--providers.redis.endpoints=${TRAEFIK_REDIS_ENDPOINTS}}
- ${TRAEFIK_REDIS_ENDPOINTS:+--providers.redis.password=${REDIS_PASSWORD}}
```

Both lines are gated on `TRAEFIK_REDIS_ENDPOINTS`. When it is blank or absent, each expands to an empty argument and the provider stays off, which is what every Traefik without a local Redis needs.

`scripts/build.py` adds `TRAEFIK_REDIS_ENDPOINTS: redis:6379` only to stacks that run the Redis master or a replica, so traefik-server and traefik-dmz get it and nothing else does. Leave it as pasted.

Compose replaces `command:` as a whole list rather than merging it, so a stack cannot append these two flags to the base service on its own. Traefik's `TRAEFIK_PROVIDERS_REDIS_*` environment variables are no way around that either: Traefik reads its install configuration from only one source, and once any flag is on the command line it ignores those variables.

### The ACME account email

```yaml
- --certificatesresolvers.letsencrypt.acme.email=${LE_EMAIL}
```

`LE_EMAIL` resolves from a Komodo Secret created in [step 4](#4-create-the-five-komodo-secrets), and Let's Encrypt registers the resolver's account under it.

tf01 is the first stack that exercises this. traefik-bootstrap strips the resolver entirely, so no earlier host has asked Let's Encrypt for anything.

### What is already correct

The HTTPS entrypoint's own `certresolver` line is commented out on purpose, and does not need enabling. Certificates reach it through the default TLS store instead:

```yaml
- "traefik.tls.stores.default.defaultGeneratedCert.resolver=letsencrypt"
```

That label is live, and it covers the domain and its wildcards. Leave the entrypoint line alone.

## Prerequisites

- ci01 is finished, through [Semaphore setup](semaphore-setup.md) and [VictoriaMetrics setup](victoriametrics-setup.md). Semaphore's `provision-monitoring` Template is what generates this host's own Node Exporter password, and tf01's vmagent scrapes node_exporter with it.
- The three `GLOBAL_VMAUTH_` values exist, from [step 4 of VictoriaMetrics setup](victoriametrics-setup.md#4-create-the-three-vmauth-keys). Without them this host's monitoring sidecars deploy with nowhere to write.
- km01 is finished through step 14 of [km01 bootstrap](komodo-bootstrap.md), so the nineteen `[[GLOBAL_...]]` Variables exist.
- A Cloudflare API token scoped to edit DNS for the zone, and the account email that owns it. The resolver uses a DNS-01 challenge, so Let's Encrypt never needs to reach tf01 from the internet.

## Placeholders

The first six are the ones [Provisioning a VM](provision-a-vm.md) takes from this page. It lists four more that are the same for every host.

| Placeholder | Value |
| --- | --- |
| `<host>` | `tf01` |
| `<cores>` | `4` |
| `<memory>` | `8192` |
| `<vmid>` | VMID to give the new VM, yours to pick |
| `<ip>` | Static address for tf01, on the internal VLAN |
| `<gateway-ip>` | The internal VLAN's gateway |
| `<internal-subnet>` | The internal VLAN's CIDR, the one every fleet VM but bh01 sits on |

## 1. Provision the VM

Follow [Provisioning a VM](provision-a-vm.md), seven steps ending with tf01 connected and healthy under *Resources > Servers*. There is no tf01-specific variation in any of them.

Four cores and 8 GB because ten services run here, and Traefik is the path every other host's traffic takes.

tf01 is on the internal VLAN, not the DMZ, so it takes the same gateway ci01 did. bh01 is the host that faces the internet, and it reaches tf01 over the internal network.

## 2. Create the runtime folders

```bash
projectName="traefik"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/logs/$projectName/traefik
sudo chown 101000:101000 /opt/docker/logs/$projectName/traefik
sudo chmod 755 /opt/docker/logs/$projectName/traefik

mkdir -p /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-*

mkdir -p /opt/docker/volumes/$projectName/vmagent-data
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vmagent-*
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vlagent-*
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vector-*
```

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

The explicit `chmod 755` on the Traefik log directory matters. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so a directory left group-writable by the default umask makes the logrotate container exit 1 every five minutes and access.log grows forever.

`traefik-certs` is the one to back up. It holds `acme.json`, the Let's Encrypt account key and every issued certificate. Losing it means re-registering and re-issuing, and Let's Encrypt rate-limits both.

This list mirrors the [generated README for traefik-server](../stacks/traefik-server/README.md), which `scripts/build.py` rebuilds. That file wins if the two disagree.

## 3. Open the firewall

```bash
sudo ufw allow 80/tcp comment 'Traefik HTTP'
sudo ufw allow 443/tcp comment 'Traefik HTTPS'
sudo ufw allow 8443/tcp comment 'Traefik HTTPS (alt)'
sudo ufw allow from <internal-subnet> to any port 6379 proto tcp comment 'traefik-kop Redis'
sudo ufw status
```

The first three are the ports the Traefik container publishes, the same three every VM's Traefik needs.

The fourth is specific to tf01. `.redis-public` publishes `6379` on the host, because traefik-kop on every other VM connects to it across the network. Scope it to the internal subnet rather than opening it outright: Redis here holds routing configuration for the whole fleet, and it is reachable with nothing but the password.

## 4. Create the five Komodo Secrets

`stacks/traefik-server/komodo.env` carries five references that no earlier runbook creates. Deploying before they exist passes the literal string `[[CF_DNS_API_TOKEN]]` into the container.

In Komodo's UI on km01, go to *Settings > Secrets* and create all five by name, with no `[[` or `]]`.

| Secret | Value |
| --- | --- |
| `CF_API_EMAIL` | The Cloudflare account email that owns the DNS token |
| `CF_DNS_API_TOKEN` | The Cloudflare API token, scoped to edit DNS for the zone |
| `LE_EMAIL` | The address to register the Let's Encrypt account under |
| `TRAEFIK_KOP_REDIS_PASSWORD` | Your choice, alphanumeric only |
| `TRAEFIK_KOP_REDIS_SERVER` | `tf01.home.myah-mitchell.com` |

`TRAEFIK_KOP_REDIS_PASSWORD` is the fleet-wide Redis password. tf01's Redis sets it with `--requirepass`, and every other VM's traefik-kop authenticates with it. Pick it once here and never per host.

`TRAEFIK_KOP_REDIS_SERVER` is what tf01's own traefik-kop dials, and it is also what bh01's Redis replica replicates from. Use the hostname rather than the address, so a re-addressed tf01 does not need every stack redeployed.

The alphanumeric-only rule applies for the same reason it does everywhere else. See [Conventions](conventions.md#alphanumeric-only).

## 5. Create the Stack resource for traefik-server

In Komodo's UI, go to *Resources > Stacks* and create a Stack named `traefik-server`. Set its target *Server* to **tf01**, the resource from step 1.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/traefik-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### Paste the environment

Open `stacks/traefik-server/komodo.env` in this repo, copy its full contents, and paste them into *Environment*.

Three keys need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `tf01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |

Leave `PROJECT_NAME` as the committed `traefik`, `TRAEFIK_REDIS_ENDPOINTS` as the committed `redis:6379`, and the hostname keys alone.

Leave the `[[GLOBAL_...]]` references as pasted, with the exceptions in the next section. Komodo resolves them from the Variables created in [step 14](komodo-bootstrap.md#14-create-komodos-global-variables) of the km01 runbook.

### Keys to clear

Three keys arrive as references to Variables that do not exist yet, or as values nothing here can use. Clear each one to blank.

| Keys | Why they do nothing yet |
| --- | --- |
| `CROWDSEC_LAPI_KEY`, `CROWDSEC_LAPI_HOST` | The base Traefik service keeps its CrowdSec environment lines and its bouncer middleware commented out |
| `AUTHENTIK_HOST` | id01 does not exist yet, so nothing forwards auth anywhere |

`AUTHENTIK_HOST` is the one to come back to. See [step 8 of id01 bootstrap](id01-bootstrap.md#8-turn-on-chain-authentik-fleet-wide).

Leave the three `VMAUTH_` keys alone. ci01 comes before tf01 in the running order, so the Variables behind them already exist and this host's monitoring sidecars ship from their first deploy.

### Deploy

Save the Stack resource, then click **Deploy**. Watch the deploy log.

## 6. Verify

Confirm all ten services show running and healthy, in Komodo's container view for the resource:

```text
traefik
error-pages
socket-proxy
socket-proxy-rw
logrotate
vmagent
vlagent
vector
traefik-kop
redis
```

Then confirm Traefik actually got a certificate, rather than falling back to its self-signed default:

```bash
sudo ls -l /opt/docker/volumes/traefik/traefik-certs/acme.json
docker logs traefik-traefik 2>&1 | grep -i acme
```

An `acme.json` of a few hundred bytes holds a registration and no certificate. A bad account email shows up here first, as a registration error in the log. An `LE_EMAIL` Secret that was never created reaches Traefik as the literal `[[LE_EMAIL]]`, and fails the same way.

## 7. First access

Browse to `https://traefik.tf01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you set.

Unlike every stack reached through traefik-bootstrap, this one should present a certificate your browser already trusts. A warning here means the resolver did not issue, and step 6's log check says why.

The dashboard is on its own `dashboard` entrypoint, on `:8443`, and it is not gated behind anything yet. Gating it belongs with the rest of the Authentik work, after id01. See [id01 bootstrap](id01-bootstrap.md).

## 8. Point the other VMs at this Redis

Every VM that runs traefik-kop needs `TRAEFIK_KOP_REDIS_SERVER` and `TRAEFIK_KOP_REDIS_PASSWORD` resolved, and both are now instance-wide Secrets, so nothing per host has to change.

What does have to happen per host is the stack that carries traefik-kop. Only traefik-agent and the two stacks built on it include it, and traefik-bootstrap deliberately does not. A VM still on traefik-bootstrap publishes nothing into this Redis and routes only locally.

That is the ordering to keep in mind for the rest of the fleet: a VM starts on traefik-bootstrap to be reachable at all, and joins tf01's routing table when its real stack replaces it.

## What's next

id01 is the next VM. Authentik is what turns `chain-authentik@file` from a middleware that nothing can satisfy into the fleet's real auth gate, and it is what unblocks tearing down traefik-bootstrap everywhere.

See [id01 bootstrap](id01-bootstrap.md), and [Running order](README.md#running-order) for where tf01 sits.
