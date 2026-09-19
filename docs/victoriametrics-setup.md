# Deploying the VictoriaMetrics backend

victoriametrics-server is the fleet's metrics, logs, and traces backend. It lands on ci01, after Semaphore, and it is the third of ci01's four stacks.

Build it before the VMs that feed it. vmagent, vlagent, and vector run as sidecars in each traefik stack, and every host after ci01 in the running order deploys with those sidecars already pointed here.

This stack also pulls in victoriametrics-agent through an `include:` in its compose file, so ci01 gets the agent sidecars as part of the same deploy rather than as a second Stack resource.

Read [Conventions](conventions.md) first. This doc assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Set up Node Exporter on ci01](#1-set-up-node-exporter-on-ci01)
- [2. Open the syslog port](#2-open-the-syslog-port)
- [3. Create the runtime folders](#3-create-the-runtime-folders)
- [4. Create the three VMAuth keys](#4-create-the-three-vmauth-keys)
- [5. Create the Stack resource](#5-create-the-stack-resource)
- [6. Verify](#6-verify)
- [7. First access](#7-first-access)
- [What's next](#whats-next)

## Prerequisites

- ci01 is provisioned and shows connected and healthy in Komodo, through step 2 of [ci01 bootstrap](ci01-bootstrap.md). Step 2 in particular: this stack's routers need traefik-bootstrap on ci01 to be reachable at all.
- Semaphore is deployed and wired to the ansible repo, through [Semaphore setup](semaphore-setup.md). Steps 1 and 2 below run two of its Templates.
- km01's `[[GLOBAL_...]]` Variables exist, from step 14 of [km01 bootstrap](komodo-bootstrap.md).

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<ci-ip>` | ci01's address, the one set in its own runbook |
| `<internal-subnet>` | The internal VLAN's CIDR, the one every fleet VM sits on |

## 1. Set up Node Exporter on ci01

vmagent scrapes `<ci-ip>` on port 9100, over HTTPS, with a self-signed certificate and basic auth. Nothing in this stack installs Node Exporter. The ansible monitoring role does, and cloud-init already ran it once when ci01 first booted.

Run it again anyway, from Semaphore's `provision-monitoring` Template with `target` answered `ci01`. ci01 was provisioned before Semaphore existed, so its Node Exporter predates the per-host password the role now generates.

Then confirm the three files this stack mounts or depends on are there:

```bash
ssh <ci-ip> "sudo ls -l /etc/node-exporter/"
```

Expect `node_exporter.crt`, `config.yml`, and `scrape-password`. The last one is the copy of this host's password that vmagent reads, and it must be owned by `101000`.

If `scrape-password` is missing, the deploy still starts, but Docker creates the path as a directory and vmagent cannot read a password at all. Fix it before step 5 rather than after.

There is no password to collect. Each host's is generated on that host and never leaves it, which is why `NODE_EXPORTER_USER` is the only Node Exporter value in this stack's environment.

## 2. Open the syslog port

vector's host variant publishes 5140 on TCP and UDP so it can take syslog from the network. The ansible `stacks` role opens both, scoped to the internal subnet, in the same run that creates step 3's folders.

In ansible-private's `hosts.yml`, add the `victoriametrics-server` stack to ci01's `docker_stacks` list, as in [step 10 of Semaphore setup](semaphore-setup.md#add-a-real-host-group-to-ansible-private). Commit and push it, and paste the new contents into Semaphore's **ansible-fleet** Inventory, as in [Load it into Semaphore](semaphore-setup.md#load-it-into-semaphore).

Run **provision-stacks** with *Target* answered `ci01`, then confirm the rules on ci01:

```bash
sudo ufw status
```

`5140/tcp` and `5140/udp` show `ALLOW` from `<internal-subnet>`, with the comment `Vector syslog`.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
sudo ufw allow from <internal-subnet> to any port 5140 proto tcp comment 'Vector syslog'
sudo ufw allow from <internal-subnet> to any port 5140 proto udp comment 'Vector syslog'
sudo ufw status
```

</details>

Only fleet hosts ship syslog here, and an open syslog port is an easy way to fill a disk from off the network.

## 3. Create the runtime folders

Same rule as everywhere else. Neither Periphery nor Compose creates host bind-mount directories, so these have to exist with the right ownership before the first deploy.

Step 2's run created them. Check the result on ci01:

```bash
sudo ls -ln /opt/docker/volumes/victoriametrics
```

All seven data folders are owned by `101000`.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
projectName="victoriametrics"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/victoriametrics-data
mkdir -p /opt/docker/volumes/$projectName/victorialogs-data
mkdir -p /opt/docker/volumes/$projectName/victoriatraces-data
mkdir -p /opt/docker/volumes/$projectName/grafana-data
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown -R 101000:101000 /opt/docker/volumes/$projectName/
```

</details>

Every service here runs as `PUID`, so all seven data folders take 101000. There is no Postgres in this stack and nothing owned by 100000. See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

## 4. Create the three VMAuth keys

Every traefik stack's `komodo.env` carries three VMAuth keys that reference Variables nothing has created yet. Create the Variables here and every later host resolves them on its first deploy.

Create them on km01, `GLOBAL_VMAUTH_PASS` under *Settings > Secrets* and the other two under *Settings > Variables*:

| Name | Value |
| --- | --- |
| `GLOBAL_VMAUTH_USER` | Your choice |
| `GLOBAL_VMAUTH_PASS` | Your choice, alphanumeric only |
| `GLOBAL_VMAUTH_HOST` | `vmauth.ci01.home.myah-mitchell.com` |

`GLOBAL_VMAUTH_HOST` is a hostname with no scheme. Each agent builds its own URL around it, so vmagent posts to `/api/v1/write` and vlagent to `/insert/native`, both over HTTPS.

The alphanumeric-only rule matters here for the same reason it does everywhere else. See [Conventions](conventions.md#alphanumeric-only).

> [!WARNING]
> These two credentials do not protect the data. vmauth's router is hardcoded to `chain-no-auth@file`, and its `config/auth-vl-single.yml` defines only an `unauthorized_user` route, so vmauth proxies whatever reaches it. The username and password guard vmauth's own endpoints, not the traffic it forwards. Anything that can resolve that hostname can read and write all three databases, so keep it off public DNS until that config grows a real user block.

## 5. Create the Stack resource

In Komodo's UI, go to *Resources > Stacks*, create a Stack named `victoriametrics-server`, and set its target *Server* to **ci01**.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/victoriametrics-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/victoriametrics-server/komodo.env` in this repo, copy its full contents, and paste them into that field.

Four keys in the pasted text need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |
| `TRAEFIK_AUTH_CHAIN` | `chain-no-auth@file`, so it routes through traefik-bootstrap |

Leave `NODE_EXPORTER_USER` as the committed `node-exporter-user`. That is the user the ansible role configures, and changing it here without changing it there breaks the scrape.

Five of this stack's routers fall back to `chain-authentik@file`, which still has nothing behind it, hence the override. Grafana and vmauth are hardcoded to `chain-no-auth@file` and ignore it, because both do their own authentication. Clear the override once id01 is live.

The three `[[GLOBAL_VMAUTH_...]]` references resolve from step 4. Leave every other `[[...]]` reference exactly as it is.

### Deploy

Save the Stack resource, then click **Deploy**. This one pulls a dozen images on a cold host, so give it longer than Semaphore took.

## 6. Verify

Confirm all twelve services show running and healthy, in Komodo's container view for the resource:

```text
victoriametrics
victorialogs
victoriatraces
vmauth
vmalert
grafana
alertmanager
vmagent
vlagent
vector
cadvisor
socket-proxy
```

The last five come from victoriametrics-agent through the `include:`. They are part of this deploy, which is why ci01 never gets an agent stack of its own.

If vmagent is healthy but its `node` scrape target is failing, the cause is step 1 rather than anything in this stack.

## 7. First access

Browse to `https://grafana.ci01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you actually set. Your browser will warn about the certificate, because traefik-bootstrap signs its own. Accept it and continue.

Grafana sets no admin credentials in its environment, so the first login is the stock `admin` and `admin`, and it forces a change. The VictoriaMetrics and VictoriaLogs datasources are provisioned from the repo and should already be present.

## What's next

The fleet now has somewhere to send metrics, logs, and traces. Every host built after this one ships from its first deploy, with no keys to come back and fill in.

ci01 has one stack left. [Core infrastructure setup](core-infra-setup.md) deploys ntfy, mailrise, Postfix, Mailpit, blackbox-exporter, and uptime-kuma, which turn those metrics into notifications and give the fleet a mail relay.
