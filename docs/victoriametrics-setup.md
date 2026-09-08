# Deploying the VictoriaMetrics backend

`stacks/victoriametrics-server` is the fleet's metrics, logs, and traces backend. It lands on ci01, after Semaphore, and it is the last piece of core-infra that has a stack ready to deploy.

Every other VM is already trying to write to it. vmagent, vlagent, and vector run as sidecars in each traefik stack, and until this exists they buffer to their own data folders and retry.

This stack also pulls in `stacks/victoriametrics-agent` through an `include:` in its compose file, so ci01 gets the agent sidecars as part of the same deploy rather than as a second Stack resource.

Read [Conventions](conventions.md) first. This doc assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Confirm node_exporter is real on ci01](#1-confirm-node_exporter-is-real-on-ci01)
- [2. Open the syslog port](#2-open-the-syslog-port)
- [3. Create the runtime folders](#3-create-the-runtime-folders)
- [4. Create the three VMAuth keys](#4-create-the-three-vmauth-keys)
- [5. Create the Stack resource](#5-create-the-stack-resource)
- [6. Verify](#6-verify)
- [7. First access](#7-first-access)
- [8. Let the rest of the fleet ship to it](#8-let-the-rest-of-the-fleet-ship-to-it)
- [What has no stack yet](#what-has-no-stack-yet)
- [What's next](#whats-next)

## Prerequisites

- ci01 is provisioned and shows connected and healthy in Komodo, through step 9 of [ci01 bootstrap](ci01-bootstrap.md). Step 9 in particular: this stack's routers need traefik-bootstrap on ci01 to be reachable at all.
- Semaphore is deployed and wired to the ansible repo, through [Semaphore setup](semaphore-setup.md). Its step 12 is what replaces the committed `CHANGEME` node_exporter password with a real one, and step 1 below depends on that having run.
- km01's `[[GLOBAL_...]]` Variables exist, from step 14 of [km01 bootstrap](komodo-bootstrap.md).

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<ci-ip>` | ci01's address, the one set in its own runbook |
| `<internal-subnet>` | The internal VLAN's CIDR, the one every fleet VM sits on |

## 1. Confirm node_exporter is real on ci01

vmagent scrapes `<ci-ip>` on port 9100, over HTTPS, with a self-signed certificate and basic auth. Nothing in this stack installs node_exporter, but nothing here needs to: the ansible monitoring role already does it on every provisioned host.

`roles/monitoring/tasks/node-exporter.yml` installs the binary, generates the self-signed certificate, writes `/etc/node-exporter/config.yml` with a bcrypt hash of `node_exporter_password`, and runs it under a systemd unit. The basic-auth user it configures is `node-exporter-user`, which is the value already committed as the `NODE_EXPORTER_USER` default.

So the only thing to check is that the password is no longer the placeholder:

```bash
ssh <ci-ip> "sudo grep -c node-exporter-user /etc/node-exporter/config.yml"
```

If that file does not exist, or `node_exporter_password` is still `CHANGEME` in ansible, go back to [step 12 of Semaphore setup](semaphore-setup.md#12-fix-existing-hosts-before-running). Deploying now still works, but the `node` scrape target fails on every host until it is fixed.

Have the real `node_exporter_password` from ansible-private's `group_vars/all/private.yml` to hand. Step 5 pastes it into `NODE_EXPORTER_PASS`, unhashed, because that is what vmagent sends on every scrape.

> [!NOTE]
> The [generated README for victoriametrics-server](../stacks/victoriametrics-server/README.md) walks through installing node_exporter by hand, from the download to the systemd unit. That predates the ansible role and is superseded by it for any host these runbooks provisioned. Follow it only for a host ansible does not manage.

## 2. Open the syslog port

vector's host variant publishes 5140 on TCP and UDP so it can take syslog from the network:

```bash
sudo ufw allow from <internal-subnet> to any port 5140 proto tcp comment 'Vector syslog'
sudo ufw allow from <internal-subnet> to any port 5140 proto udp comment 'Vector syslog'
sudo ufw status
```

The generated README opens this with a named UFW application and no source restriction. Scope it to the internal subnet instead. Only fleet hosts ship syslog here, and an open syslog port is an easy way to fill a disk from off the network.

## 3. Create the runtime folders

Same rule as everywhere else. Neither Periphery nor Compose creates host bind-mount directories, so these have to exist with the right ownership before the first deploy.

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

Every service here runs as `PUID`, so all seven data folders take 101000. There is no Postgres in this stack and nothing owned by 100000. See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

The [generated README for victoriametrics-server](../stacks/victoriametrics-server/README.md) lists an eighth folder, `cadvisor-data`. Creating it is harmless, but no service mounts it, so the list above leaves it out.

## 4. Create the three VMAuth keys

The tf01 and bh01 runbooks both tell you to clear `VMAUTH_USER`, `VMAUTH_PASS`, and `VMAUTH_HOST`, because the Variables behind them do not exist yet. This step is what makes them real.

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

Five keys in the pasted text need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |
| `NODE_EXPORTER_PASS` | The real `node_exporter_password` from step 1 |
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

The last five come from `stacks/victoriametrics-agent` through the `include:`. They are part of this deploy, which is why ci01 never gets an agent stack of its own.

If vmagent is healthy but its `node` scrape target is failing, the cause is step 1 rather than anything in this stack.

## 7. First access

Browse to `https://grafana.ci01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you actually set. Your browser will warn about the certificate, because traefik-bootstrap signs its own. Accept it and continue.

Grafana sets no admin credentials in its environment, so the first login is the stock `admin` and `admin`, and it forces a change. The VictoriaMetrics and VictoriaLogs datasources are provisioned from the repo and should already be present.

## 8. Let the rest of the fleet ship to it

Nothing on ci01 needs changing here. The stacks that need it are the ones deployed before this existed, where `VMAUTH_USER`, `VMAUTH_PASS`, and `VMAUTH_HOST` were cleared to blank because the Variables behind them did not resolve.

Go back to each of those Stack resources in Komodo, restore the three keys to the `[[GLOBAL_VMAUTH_...]]` references their `komodo.env` ships with, and redeploy. So far that means tf01 and bh01. See [Keys to clear](tf01-bootstrap.md#keys-to-clear).

Nothing is lost in the meantime. Each agent buffers to its own data folder and retries, capped at 100 MB per remote-write URL, so a host that has been waiting a while backfills rather than starting clean.

## What has no stack yet

ntfy, mailrise, blackbox-exporter, and uptime-kuma each have a container directory in this repo and no stack. Assembling them is a repo change rather than a runbook step, and there is nothing to deploy until someone does it.

Two of them are referenced elsewhere. mailrise is the plausible SMTP relay behind Authentik's email settings, and ntfy is where vmalert's alerts are meant to land instead of the blackhole receiver alertmanager ships with. See [step 4 of id01 bootstrap](id01-bootstrap.md#4-create-the-komodo-secrets-and-variables).

## What's next

ci01 is finished. tf01 is the next VM, in [tf01 bootstrap](tf01-bootstrap.md). See [Running order](README.md#running-order) for the rest.
