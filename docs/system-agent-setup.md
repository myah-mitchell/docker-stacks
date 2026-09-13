# system-agent

system-agent is the standard per-VM bundle. Every VM in the fleet runs this one stack, and for most VMs it is the only stack besides whatever that VM exists to host.

It is also what [traefik-bootstrap](traefik-bootstrap.md) is a stand-in for. Deploying it on a VM is how that VM stops being in bootstrap mode.

Because every VM runs it, this page is written once and each host runbook points here rather than repeating it.

Read [Conventions](conventions.md) first. This page assumes its naming and secrets rules.

## Contents

- [What it runs](#what-it-runs)
- [When to deploy it](#when-to-deploy-it)
- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Run the monitoring role against the VM](#1-run-the-monitoring-role-against-the-vm)
- [2. Create the runtime folders](#2-create-the-runtime-folders)
- [3. Open the firewall](#3-open-the-firewall)
- [4. Collect the VM's dockns values](#4-collect-the-vms-dockns-values)
- [5. Create the Stack resource](#5-create-the-stack-resource)
- [6. Deploy and verify](#6-deploy-and-verify)
- [7. Tear down traefik-bootstrap](#7-tear-down-traefik-bootstrap)
- [8. Confirm the telemetry is arriving](#8-confirm-the-telemetry-is-arriving)
- [What's next](#whats-next)

## What it runs

Twelve services doing four jobs.

Traefik terminates TLS for that VM's own services and puts them behind the Authentik auth chain, without tf01 being in the request path. error-pages, logrotate, socket-proxy, and socket-proxy-rw support it. traefik-kop publishes a router into tf01's shared Redis, but only for a service that also carries a `kop-public.traefik.*` label, so reaching the wider network stays a per-service choice.

vmagent, vlagent, vector, and cadvisor are the VM's telemetry. Between them they cover the host's own metrics from Node Exporter, per-container metrics from cadvisor, Traefik's metrics and access log, and the host's journald, syslog, and file logs. All of it goes to ci01.

dockns keeps the VM's DNS records in step with the containers running on it.

dozzle-agent exposes this VM's container logs on port 7007, for a central Dozzle to read.

## When to deploy it

Once ci01, id01, and pk01 are all live. system-agent writes metrics to ci01, uses id01 for its auth chain, and takes its Traefik certificate from pk01, so deploying it before those exist gets you a Traefik that cannot issue a certificate and an auth chain that forwards to nothing.

Deploy [traefik-bootstrap](traefik-bootstrap.md) in the meantime, and come back here per VM once the three backends are up.

> [!WARNING]
> Do not run traefik-bootstrap and system-agent on the same VM at once. Both publish `:80`, `:443`, and `:8443` on the host and will fight over them. Step 7 is the handover.

## Prerequisites

- The target VM is a connected, healthy Komodo Server resource, from [Provisioning a VM](provision-a-vm.md).
- ci01 is finished, through [ci01 bootstrap](ci01-bootstrap.md). vmagent, vlagent, and vector have nothing to write to otherwise.
- id01 is live, through [id01 bootstrap](id01-bootstrap.md), so `chain-authentik@file` resolves.
- pk01 is live, through [pk01 bootstrap](pk01-bootstrap.md), so Traefik can get a real internal certificate.
- tf01 is live, through [tf01 bootstrap](tf01-bootstrap.md), if you want traefik-kop to publish anything. The stack deploys without it; only `kop-public` routers stop working.
- km01's `[[GLOBAL_...]]` Variables exist, from step 14 of [km01 bootstrap](komodo-bootstrap.md).

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<host>` | The VM's hostname, for example `tf01` |
| `<host-ip>` | That VM's address |
| `<internal-subnet>` | The internal VLAN in CIDR form, from the same place `<host-ip>` came from |
| `<unifi-url>` | That site's UniFi console over HTTPS at its LAN address, not `api.ui.com` |

## 1. Run the monitoring role against the VM

vmagent scrapes this host's own Node Exporter on port 9100, over HTTPS with a self-signed certificate and basic auth. Nothing in this stack installs Node Exporter. The ansible `monitoring` role does, and cloud-init already ran it once when the VM first booted.

Run it again from Semaphore's `provision-monitoring` Template, with `target` answered `<host>`. Any VM provisioned before Semaphore existed has a Node Exporter that predates the per-host password the role now generates.

Then confirm the files this stack mounts are there:

```bash
ssh <host-ip> "sudo ls -l /etc/node-exporter/"
```

Expect `node_exporter.crt`, `config.yml`, and `scrape-password`. That last one is this host's password in plaintext, and it must be owned by `101000`, the host-side UID that Docker's user namespace maps vmagent onto.

If `scrape-password` is missing, the deploy still starts, but Docker creates the path as a directory and vmagent gets no password at all. Fix it before step 5 rather than after.

There is no password to collect and nothing to paste into Komodo. Each host's password is generated on that host, is different from every other host's, and never leaves it. A host's vmagent only ever scrapes its own Node Exporter, so nothing needs them to match. That is why `NODE_EXPORTER_USER` is the only Node Exporter value in this stack's environment.

## 2. Create the runtime folders

Neither Periphery nor Compose creates host bind-mount directories, so these have to exist with the right ownership before the first deploy.

```bash
projectName="system"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/logs/$projectName/traefik
mkdir -p /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
mkdir -p /opt/docker/volumes/$projectName/vector-data
mkdir -p /opt/docker/volumes/$projectName/cadvisor-data
sudo chown -R 101000:101000 /opt/docker/logs/$projectName/traefik
sudo chmod 755 /opt/docker/logs/$projectName/traefik
sudo chown 101000:101000 /opt/docker/volumes/$projectName/*-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-*
```

dockns is the one exception. It is the only service here that does not pick up the shared `user:` override, so it runs as the image's own root and its directory belongs to `100000` rather than `101000`:

```bash
mkdir -p /opt/docker/volumes/$projectName/dockns-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/dockns-data
```

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

The explicit `chmod 755` on the Traefik log directory matters. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so a directory left group-writable by the default umask makes the logrotate container exit 1 every five minutes and access.log grows forever.

## 3. Open the firewall

Base provisioning enables UFW with a default-deny inbound policy and opens only what each host's own roles need. None of these ports are part of that, so nothing opens them for you.

Traefik's three, open to anything that can reach the VM:

```bash
sudo ufw allow 80/tcp comment 'Traefik HTTP'
sudo ufw allow 443/tcp comment 'Traefik HTTPS'
sudo ufw allow 8443/tcp comment 'Traefik HTTPS (alt)'
```

Dozzle's agent port and vector's syslog port, scoped to the internal subnet:

```bash
sudo ufw allow from <internal-subnet> to any port 7007 proto tcp comment 'Dozzle agent'
sudo ufw allow from <internal-subnet> to any port 5140 proto tcp comment 'Vector syslog'
sudo ufw allow from <internal-subnet> to any port 5140 proto udp comment 'Vector syslog'
sudo ufw status
```

Scope those two rather than opening them outright. Only the central Dozzle reads 7007, and an unrestricted syslog port is an easy way for anything on the network to fill a disk.

The monitoring role already opened 9100 for Node Exporter as the `Node-Exporter` UFW application, so it is not repeated here.

## 4. Collect the VM's dockns values

dockns writes this VM's DNS records, and it needs credentials for the DNS provider before it can. Every VM needs the UniFi half. Only a VM hosting an internet-reachable service needs the Cloudflare half.

For UniFi, generate a local API key on that VM's own site's UniFi console, with permission to manage DNS records. In current firmware that is under *Settings > System > API*.

`DOCKNS_UNIFI_HOST` is that console's own local URL, `<unifi-url>`, not `api.ui.com`. The local connector is deliberate: internal DNS should not depend on UniFi's cloud API being reachable, and the traffic stays on the LAN. The home site and the cloud site have separate consoles, so a VM on one site cannot use the other's values.

Both values are per site rather than fleet-wide, so they are not `[[GLOBAL_...]]` Variables. `komodo.env` ships them as ordinary `[[...]]` references, and a two-site fleet needs a separate pair per site. Name each pair after its site, or paste the literal values into the stack's *Environment* on each VM.

For Cloudflare, four more keys have to be filled in. Leave all four blank on a VM with nothing public on it.

| Key | Where to find it |
| --- | --- |
| `DOCKNS_CF_API_KEY` | A Cloudflare API token with DNS edit rights on the zone |
| `DOCKNS_CF_ACCOUNT_ID` | The account overview page in the Cloudflare dashboard |
| `DOCKNS_CF_ZONE_ID` | The zone overview page for the domain |
| `DOCKNS_WAN_IP` | The site's public address, the one records should point at |

[dockns' Cloudflare provider docs](https://codeberg.org/BrenekH/DockNS/src/branch/main/docs/name-servers/cloudflare.md) cover each of them in more detail.

## 5. Create the Stack resource

In Komodo's UI, go to *Resources > Stacks*, create a Stack named `system-agent`, and set its target *Server* to the VM you are deploying onto.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/system-agent` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/system-agent/komodo.env` in this repo, copy its full contents, and paste them into that field.

Three keys need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | The VM's hostname, `<host>` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |

Leave `TRAEFIK_AUTH_CHAIN` blank. Blank is what gets you the real `chain-authentik@file`, and this stack is the point at which that becomes correct.

### Clear the two CrowdSec keys

Clear `CROWDSEC_LAPI_KEY` and `CROWDSEC_LAPI_HOST` to blank. The base Traefik service keeps its CrowdSec plugin lines commented out, so nothing reads either one, and no `GLOBAL_CROWDSEC_LAPI_HOST` Variable exists to resolve the second.

That is the same reason every runbook before this one clears them.

### Check that every reference resolves

This is the stack with the most `[[...]]` references in the repo, and it is the first one that needs all of them at once. A reference with no Variable or Secret behind it reaches Compose as the literal string, which usually surfaces as a type error rather than as a missing credential.

Nineteen `[[GLOBAL_...]]` references come from [step 14](komodo-bootstrap.md#14-create-komodos-global-variables) of the km01 runbook, and need no action. The other ten come from later runbooks:

| Reference | Created in |
| --- | --- |
| `GLOBAL_VMAUTH_USER`, `GLOBAL_VMAUTH_PASS`, `GLOBAL_VMAUTH_HOST` | [step 4 of VictoriaMetrics setup](victoriametrics-setup.md#4-create-the-three-vmauth-keys) |
| `TRAEFIK_KOP_REDIS_PASSWORD`, `TRAEFIK_KOP_REDIS_SERVER` | [step 4 of tf01 bootstrap](tf01-bootstrap.md#4-create-the-four-komodo-secrets) |
| `CF_API_EMAIL`, `CF_DNS_API_TOKEN` | The same step on tf01 |
| `GLOBAL_AUTHENTIK_HOST` | [step 8 of id01 bootstrap](id01-bootstrap.md#8-turn-on-chain-authentik-fleet-wide) |
| `DOCKNS_UNIFI_HOST`, `DOCKNS_UNIFI_API_KEY` | Step 4 above, per site |

The four `DOCKNS_CF_` and `DOCKNS_WAN_IP` references are the exception. Clear them to blank on a VM with nothing public on it, rather than creating empty Variables.

That list is also why this page sits after every host runbook rather than after ci01. Four of the five hosts each contribute something it needs.

## 6. Deploy and verify

Save the Stack resource, then click **Deploy**. Watch the deploy log.

Confirm all twelve services show running and healthy:

```text
traefik
error-pages
logrotate
traefik-kop
vmagent
vlagent
vector
cadvisor
dozzle-agent
dockns
socket-proxy
socket-proxy-rw
```

Then browse to `https://traefik.<host>.home.myah-mitchell.com`, substituting whatever sub-domain and domain you actually set. This is the first stack whose dashboard sits behind the real auth chain, so expect Authentik to ask you to sign in, and expect the certificate to be trusted rather than warned about. If the certificate is still self-signed, Traefik did not reach step-ca on pk01.

## 7. Tear down traefik-bootstrap

Only if this VM was running it. tf01 and bh01 never did, because their own stacks are a Traefik already.

Delete the traefik-bootstrap Stack resource in Komodo. It cannot run alongside this one.

Then clear the `TRAEFIK_AUTH_CHAIN` override on every other stack on this VM that was set to `chain-no-auth@file`, and redeploy each. They fall back to `chain-authentik@file` and pick up the real auth chain.

Hostnames do not change in the handover. Only the certificate and the auth chain do.

## 8. Confirm the telemetry is arriving

The four telemetry services report healthy whether or not anything is reaching ci01, so check the far end rather than the container.

In Grafana on ci01, query for this host:

```text
up{instance=~".*<host>.*"}
```

Expect a series for the node, cadvisor, vmagent, vlagent, and Traefik jobs, all at `1`. A missing `node` series with everything else present means the Node Exporter password from step 1 is not being read, which usually means `scrape-password` is a directory rather than a file.

For logs, open VictoriaLogs and filter on `stream_name`, which is the one stream field this pipeline sets. Expect streams named after this host's systemd units from journald, and `host-syslog` and similar from the files under `/var/log`.

Traefik's access log is separate. It goes to its own `traefik-access` index with its own stream fields, and appears only once something has actually been routed through this VM.

## What's next

Repeat this page per VM. It is the same twelve services and the same eight steps every time, and only `SERVER_NAME` and the dockns values differ.

On ci01, go back to [subscribe your phone](core-infra-setup.md#after-system-agent-subscribe-your-phone) once this page is done. ntfy is reachable from a phone only from this point on.

See [Running order](README.md#running-order) for which VMs are still waiting on it, and [Stacks](stacks.md) for what else lands on each one.
