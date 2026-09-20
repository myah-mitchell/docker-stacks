# system-agent

system-agent is the standard per-VM bundle. Every VM in the fleet runs this one stack, and for most VMs it is the only stack besides whatever that VM exists to host.

It carries no Traefik. The VMs that publish something run [traefik-agent](traefik-agent-setup.md) beside it, and [traefik-bootstrap](traefik-bootstrap.md) is the stand-in for that stack, not for this one.

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
- [7. Confirm the telemetry is arriving](#7-confirm-the-telemetry-is-arriving)
- [What's next](#whats-next)

## What it runs

Seven services doing three jobs.

vmagent, vlagent, vector, and cadvisor are the VM's telemetry. Between them they cover the host's own metrics from Node Exporter, per-container metrics from cadvisor, and the host's journald, syslog, and file logs. On a VM that also runs [traefik-agent](traefik-agent-setup.md) they pick up that Traefik's metrics and access log as well, without either stack knowing about the other. All of it goes to ci01.

dockns keeps the VM's DNS records in step with the containers running on it.

dozzle-agent exposes this VM's container logs on port 7007, for a central Dozzle to read.

socket-proxy is how vector, dozzle-agent, and dockns read the Docker API without the socket being mounted into any of them.

## When to deploy it

Once ci01 is live. This stack writes metrics and logs to ci01 and needs nothing else from the fleet: no auth chain, no certificate, no Traefik. A VM still in bootstrap mode can run it as soon as the monitoring backends exist.

Nothing here publishes `:80`, `:443`, or `:8443`, so this stack and traefik-bootstrap can sit on the same VM. The handover that has to be sequenced is traefik-bootstrap to traefik-agent, and it lives on [that page](traefik-agent-setup.md#6-tear-down-traefik-bootstrap).

The ansible `stacks` role leaves this stack out of any run answered *Bootstrap* `true`, because `stacks/system-agent/setup.yaml` marks it as needing the rest of the fleet.

## Prerequisites

- The target VM is a connected, healthy Komodo Server resource, from [Provisioning a VM](provision-a-vm.md).
- ci01 is finished, through [ci01 bootstrap](ci01-bootstrap.md). vmagent, vlagent, and vector have nothing to write to otherwise.
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

The ansible `stacks` role creates them from `stacks/system-agent/setup.yaml`, and opens step 3's ports in the same run.

`<host>`'s `docker_stacks` already lists `system-agent`, from [step 10 of Semaphore setup](semaphore-setup.md#add-a-real-host-group-to-ansible-private), and nothing in the inventory has to change here. What changes is the *Bootstrap* answer that has been keeping this stack out of the run: leave it blank from now on.

Run **provision-stacks** with *Target* answered `<host>` and *Bootstrap* blank, then check the result on the VM:

```bash
sudo ls -ln /opt/docker/volumes/system
```

Every folder but one is owned by `101000`.

dockns is the exception. It is the only service here that does not pick up the shared `user:` override, so it runs as the image's own root and its directory belongs to `100000` rather than `101000`.

`/opt/docker/logs/system` is created as well and stays empty. Nothing in this stack writes a log file of its own; container output goes to Docker's log driver, which is where vector reads it from.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
projectName="system"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/vmagent-data
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/*-data
```

```bash
mkdir -p /opt/docker/volumes/$projectName/dockns-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/dockns-data
```

</details>

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

## 3. Open the firewall

Base provisioning enables UFW with a default-deny inbound policy and opens only what each host's own roles need. None of these ports are part of that, which is why the `stacks` role opens them.

Step 2's run opened all three rules. Confirm them on the VM:

```bash
sudo ufw status
```

`7007/tcp`, `5140/tcp`, and `5140/udp` show `ALLOW` from `<internal-subnet>`.

<details>
<summary>Manual steps, instead of ansible</summary>

Dozzle's agent port and vector's syslog port, scoped to the internal subnet:

```bash
sudo ufw allow from <internal-subnet> to any port 7007 proto tcp comment 'Dozzle agent'
sudo ufw allow from <internal-subnet> to any port 5140 proto tcp comment 'Vector syslog'
sudo ufw allow from <internal-subnet> to any port 5140 proto udp comment 'Vector syslog'
sudo ufw status
```

</details>

Scope those rather than opening them outright. Only the central Dozzle reads 7007, and an unrestricted syslog port is an easy way for anything on the network to fill a disk.

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

In Komodo's UI, go to *Resources > Stacks*, create a Stack named `system-agent-<host>`, for example `system-agent-ci01`, and set its target *Server* to that same VM.

Komodo requires every Stack name to be unique, and every VM runs this stack, so the host name goes on the end.

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

### Check that every reference resolves

A reference with no Variable or Secret behind it reaches Compose as the literal string, which usually surfaces as a type error rather than as a missing credential.

Nineteen `[[GLOBAL_...]]` references come from [step 14](komodo-bootstrap.md#14-create-komodos-global-variables) of the km01 runbook, and need no action. The rest come from later runbooks:

| Reference | Created in |
| --- | --- |
| `GLOBAL_VMAUTH_USER`, `GLOBAL_VMAUTH_PASS`, `GLOBAL_VMAUTH_HOST` | [step 4 of VictoriaMetrics setup](victoriametrics-setup.md#4-create-the-three-vmauth-keys) |
| `DOCKNS_UNIFI_HOST`, `DOCKNS_UNIFI_API_KEY` | Step 4 above, per site |

The four `DOCKNS_CF_` and `DOCKNS_WAN_IP` references are the exception. Clear them to blank on a VM with nothing public on it, rather than creating empty Variables.

## 6. Deploy and verify

Save the Stack resource, then click **Deploy**. Watch the deploy log.

Confirm all seven services show running and healthy:

```text
vmagent
vlagent
vector
cadvisor
dozzle-agent
dockns
socket-proxy
```

None of them publishes a web UI of its own, so the real check is the next step.

## 7. Confirm the telemetry is arriving

The telemetry services report healthy whether or not anything is reaching ci01, so check the far end rather than the container.

In Grafana on ci01, query for this host:

```text
up{instance=~".*<host>.*"}
```

Expect a series for the node, cadvisor, vmagent, and vlagent jobs, all at `1`, plus a Traefik series on a VM that also runs traefik-agent. A missing `node` series with everything else present means the Node Exporter password from step 1 is not being read, which usually means `scrape-password` is a directory rather than a file.

vmagent looks the Traefik target up by name rather than assuming it is there, so on a VM without traefik-agent that job finds nothing and reports no failure.

For logs, open VictoriaLogs and filter on `stream_name`, which is the one stream field this pipeline sets. Expect streams named after this host's systemd units from journald, and `host-syslog` and similar from the files under `/var/log`.

Traefik's access log is separate. It goes to its own `traefik-access` index with its own stream fields, and appears only on a VM running traefik-agent, once something has actually been routed through it.

## What's next

Repeat this page per VM. It is the same seven services and the same seven steps every time, and only `SERVER_NAME` and the dockns values differ.

On a VM that publishes anything, go on to [traefik-agent](traefik-agent-setup.md). That is the stack that replaces traefik-bootstrap and ends the bootstrap phase for that VM.

See [Running order](README.md#running-order) for which VMs are still waiting on it, and [Stacks](stacks.md) for what else lands on each one.
