# tf01 bootstrap runbook

tf01 is the fleet's Traefik hub. It runs the first real Traefik in the plan, with a Let's Encrypt cert resolver instead of self-signed TLS, and it holds the shared Redis that every other VM's traefik-kop publishes into.

Its stack is `stacks/traefik-server`. That is `stacks/traefik-agent` plus a Redis master, and traefik-agent is in turn traefik-basic plus the monitoring sidecars plus traefik-kop, so ten services come up on one VM.

tf01 does not get `stacks/traefik-bootstrap`. It is the real Traefik, so there is nothing to stand in for.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules, and it assumes you have already worked through [ci01 bootstrap](ci01-bootstrap.md), which spells out the shared provisioning steps this page compresses into one.

> [!WARNING]
> Two directives tf01 depends on are commented out in `containers/traefik/compose.yaml` today. Read [What has to change in the repo first](#what-has-to-change-in-the-repo-first) before provisioning anything. Neither is fixable from Komodo's UI.

## Contents

- [What has to change in the repo first](#what-has-to-change-in-the-repo-first)
- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Provision the VM](#1-provision-the-vm)
- [2. Create the runtime folders](#2-create-the-runtime-folders)
- [3. Open the firewall](#3-open-the-firewall)
- [4. Create the four Komodo Secrets](#4-create-the-four-komodo-secrets)
- [5. Create the Stack resource for traefik-server](#5-create-the-stack-resource-for-traefik-server)
- [6. Verify](#6-verify)
- [7. First access](#7-first-access)
- [8. Point the other VMs at this Redis](#8-point-the-other-vms-at-this-redis)
- [What's next](#whats-next)

## What has to change in the repo first

Both of these are edits to `containers/traefik/compose.yaml`, committed and pushed before Komodo clones the repo onto tf01. Neither can be worked around from the *Environment* text, and `TRAEFIK_EXTRA_COMMAND` cannot cover them because it expands as a single argument and each fix needs more than one flag.

### The Redis provider is commented out

```yaml
# Docker Redis provider for storing proxy labels from traefik-kop hosts
#- --providers.redis.endpoints=redis:6379
```

Aggregating routers published by every other VM's traefik-kop is tf01's entire reason to exist. Until that line is live, tf01 serves only the containers running on tf01 itself, and traefik-kop elsewhere writes into a Redis nobody reads.

Enabling it needs the password too, so it is two flags rather than one:

```yaml
- --providers.redis.endpoints=redis:6379
- --providers.redis.password=${REDIS_PASSWORD}
```

Guard both behind something that keeps them off every other Traefik in the fleet. Only tf01 has a Redis to point at, and a Traefik that cannot reach its configured Redis provider does not start cleanly.

### The ACME resolver has no email

The `letsencrypt` resolver defines its storage, its Cloudflare DNS-01 challenge, and its resolvers, but no account email:

```yaml
- --certificatesresolvers.letsencrypt.acme.storage=/etc/traefik/certs/acme.json
- --certificatesresolvers.letsencrypt.acme.dnschallenge.provider=cloudflare
- --certificatesresolvers.letsencrypt.acme.dnschallenge.delaybeforecheck=10
- --certificatesresolvers.letsencrypt.acme.dnschallenge.resolvers=1.1.1.1:53,8.8.8.8:53
```

The service does set `LE_EMAIL` in its environment, but that is not a name Traefik reads. Traefik takes an ACME email from `--certificatesresolvers.<name>.acme.email` or from `TRAEFIK_CERTIFICATESRESOLVERS_LETSENCRYPT_ACME_EMAIL`, and registers no account without one.

This has never been exercised, because traefik-bootstrap strips the resolver entirely and no other stack has run with it. tf01 is the first stack that asks Let's Encrypt for a certificate, so it is the first that finds out.

### What is already correct

The HTTPS entrypoint's own `certresolver` line is commented out on purpose, and does not need enabling. Certificates reach it through the default TLS store instead:

```yaml
- "traefik.tls.stores.default.defaultGeneratedCert.resolver=letsencrypt"
```

That label is live, and it covers the domain and its wildcards. Leave the entrypoint line alone.

## Prerequisites

- ci01 is finished, through [Semaphore setup](semaphore-setup.md) and [VictoriaMetrics setup](victoriametrics-setup.md). Semaphore's step 13 is what pushes the real `node_exporter_password` to every host, and tf01's vmagent scrapes node_exporter with it.
- The three `GLOBAL_VMAUTH_` values exist, from [step 4 of VictoriaMetrics setup](victoriametrics-setup.md#4-create-the-three-vmauth-keys). Without them this host's monitoring sidecars deploy with nowhere to write.
- km01 is finished through step 14 of [km01 bootstrap](komodo-bootstrap.md), so the nineteen `[[GLOBAL_...]]` Variables exist.
- The two repo changes above are committed and pushed to `main`.
- A Cloudflare API token scoped to edit DNS for the zone, and the account email that owns it. The resolver uses a DNS-01 challenge, so Let's Encrypt never needs to reach tf01 from the internet.

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<template-vmid>` | VMID of the `ubuntu-server-2604` cloud-init template |
| `<tf-vmid>` | VMID to give the new VM |
| `<tf-ip>` | Static address for tf01 |
| `<gateway-ip>` | Gateway for that subnet |
| `<km-ip>` | km01's address, from its own runbook |
| `<same>` | The value cloud-init already used, recovered rather than guessed |
| `<internal-subnet>` | The internal VLAN's CIDR, the one every fleet VM sits on |

## 1. Provision the VM

Follow steps 1 to 7 of [ci01 bootstrap](ci01-bootstrap.md), substituting tf01 throughout. Those steps are identical for every VM in the fleet, and there is no tf01-specific variation in any of them.

Size it larger than ci01. Ten services run here, and Traefik is the path every other host's traffic takes:

```bash
qm clone <template-vmid> <tf-vmid> --name tf01 --full
qm set <tf-vmid> --cores 4 --memory 8192
qm set <tf-vmid> --ipconfig0 ip=<tf-ip>/24,gw=<gateway-ip>
qm start <tf-vmid>
```

tf01 is on the internal VLAN, not the DMZ. bh01 is the host that faces the internet, and it reaches tf01 over the internal network.

Stop when tf01 shows connected and healthy under *Resources > Servers*, which is ci01's step 7. Skip its step 8 entirely.

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

## 4. Create the four Komodo Secrets

`stacks/traefik-server/komodo.env` carries four references that no earlier runbook creates. Deploying before they exist passes the literal string `[[CF_DNS_API_TOKEN]]` into the container.

In Komodo's UI on km01, go to *Settings > Secrets* and create all four by name, with no `[[` or `]]`.

| Secret | Value |
| --- | --- |
| `CF_API_EMAIL` | The Cloudflare account email that owns the DNS token |
| `CF_DNS_API_TOKEN` | The Cloudflare API token, scoped to edit DNS for the zone |
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

Leave `PROJECT_NAME` as the committed `traefik`, and leave the hostname keys alone.

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

An `acme.json` of a few hundred bytes holds a registration and no certificate. A missing account email shows up here first, as a registration error in the log.

## 7. First access

Browse to `https://traefik.tf01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you set.

Unlike every stack reached through traefik-bootstrap, this one should present a certificate your browser already trusts. A warning here means the resolver did not issue, and step 6's log check says why.

The dashboard is on its own `dashboard` entrypoint, on `:8443`, and it is not gated behind anything yet. Gating it belongs with the rest of the Authentik work, after id01. See [id01 bootstrap](id01-bootstrap.md).

## 8. Point the other VMs at this Redis

Every VM that runs traefik-kop needs `TRAEFIK_KOP_REDIS_SERVER` and `TRAEFIK_KOP_REDIS_PASSWORD` resolved, and both are now instance-wide Secrets, so nothing per host has to change.

What does have to happen per host is the stack that carries traefik-kop. Only `stacks/traefik-agent` and the two stacks built on it include it, and `stacks/traefik-bootstrap` deliberately does not. A VM still on traefik-bootstrap publishes nothing into this Redis and routes only locally.

That is the ordering to keep in mind for the rest of the fleet: a VM starts on traefik-bootstrap to be reachable at all, and joins tf01's routing table when its real stack replaces it.

## What's next

id01 is the next VM. Authentik is what turns `chain-authentik@file` from a middleware that nothing can satisfy into the fleet's real auth gate, and it is what unblocks tearing down traefik-bootstrap everywhere.

See [id01 bootstrap](id01-bootstrap.md), and [Running order](README.md#running-order) for where tf01 sits.
