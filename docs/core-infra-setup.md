# Deploying the core infrastructure stack

core-infra is what turns the metrics ci01 already collects into something that reaches you. It is the fourth and last of ci01's stacks.

ntfy is the destination. It takes a push over HTTP and delivers it to a phone or desktop app, and everything else here ends up talking to it.

mailrise is an SMTP server that only speaks ntfy. Proxmox Backup Server and Proxmox VE can send mail and cannot send push notifications, so mailrise takes their mail on the LAN and re-emits it as an ntfy push.

blackbox-exporter probes URLs from outside the service being probed, which is the one thing a metrics agent running next to a service cannot do. uptime-kuma is the glanceable red and green version of the same question.

Read [Conventions](conventions.md) first. This doc assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Create the runtime folders](#1-create-the-runtime-folders)
- [2. Open the SMTP port](#2-open-the-smtp-port)
- [3. Create the Stack resource](#3-create-the-stack-resource)
- [4. Verify](#4-verify)
- [5. Create the ntfy accounts](#5-create-the-ntfy-accounts)
- [6. Finish mailrise and point Proxmox at it](#6-finish-mailrise-and-point-proxmox-at-it)
- [7. First access to Uptime Kuma](#7-first-access-to-uptime-kuma)
- [What's next](#whats-next)

## Prerequisites

- ci01 is provisioned and shows connected and healthy in Komodo, through step 2 of [ci01 bootstrap](ci01-bootstrap.md). traefik-bootstrap on ci01 is what makes any of these reachable.
- The VictoriaMetrics backend is deployed, through [VictoriaMetrics setup](victoriametrics-setup.md). blackbox-exporter has nothing scraping it until vmagent is there.
- km01's `[[GLOBAL_...]]` Variables exist, from step 14 of [km01 bootstrap](komodo-bootstrap.md).

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<ci-ip>` | ci01's address, the one set in its own runbook |
| `<internal-subnet>` | The internal VLAN in CIDR form, from the same place `<ci-ip>` came from |
| `<ntfy-user>` | The account name you sign in to the ntfy apps with, your choice, created in step 5 |
| `<ntfy-token>` | The publish token printed by step 5 |

## 1. Create the runtime folders

Neither Periphery nor Compose creates host bind-mount directories, so these have to exist with the right ownership before the first deploy.

```bash
projectName="core"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/ntfy-data
mkdir -p /opt/docker/volumes/$projectName/uptime-kuma-data
mkdir -p /opt/docker/volumes/$projectName/blackbox-exporter-config
mkdir -p /opt/docker/volumes/$projectName/mailrise-secrets
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ntfy-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/uptime-kuma-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/blackbox-exporter-config
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailrise-secrets
sudo chmod 700 /opt/docker/volumes/$projectName/mailrise-secrets
```

ntfy and uptime-kuma keep state. mailrise and blackbox-exporter each read one config file that is not in git, so those two directories hold the files rather than the repo checkout does. Periphery re-clones over its run directory, and anything written inside that directory goes with it.

Seed both files now, from the examples this repo serves publicly, so nothing has to be cloned first:

```bash
sudo curl -fsSL -o /opt/docker/volumes/$projectName/blackbox-exporter-config/blackbox.yml \
  https://raw.githubusercontent.com/myah-mitchell/docker-stacks/main/containers/blackbox-exporter/config/blackbox.yml.example
sudo curl -fsSL -o /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf \
  https://raw.githubusercontent.com/myah-mitchell/docker-stacks/main/containers/mailrise/config/mailrise.conf.example
sudo chmod 600 /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf
sudo chown 101000:101000 /opt/docker/volumes/$projectName/blackbox-exporter-config/blackbox.yml
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf
```

The blackbox copy is usable as it stands. It defines probe modules and nothing host-specific.

The mailrise copy is not, because it carries two `REPLACE_WITH_NTFY_TOKEN` placeholders and the token does not exist until step 5. Leave them for now. mailrise starts and accepts mail with a placeholder token, it just cannot deliver. It gets mode `600` because that is the file the real token ends up in.

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

## 2. Open the SMTP port

mailrise publishes port 8025 on the host, because Proxmox has to reach it directly rather than through Traefik. Base provisioning enables UFW with a default-deny inbound policy, so nothing opens it for you:

```bash
sudo ufw allow from <internal-subnet> to any port 8025 proto tcp comment 'Mailrise SMTP'
sudo ufw status
```

Scope it to the internal subnet. mailrise accepts anything that arrives on that port with no authentication, which is fine for a LAN-only relay and not fine for anything wider.

The other three services are reached through Traefik on 443, already open from traefik-bootstrap.

## 3. Create the Stack resource

In Komodo's UI, go to *Resources > Stacks*, create a Stack named `core-infra`, and set its target *Server* to **ci01**.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/core-infra` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/core-infra/komodo.env` in this repo, copy its full contents, and paste them into that field.

Four keys in the pasted text need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |
| `TRAEFIK_AUTH_CHAIN` | `chain-no-auth@file`, so it routes through traefik-bootstrap |

blackbox-exporter and uptime-kuma both fall back to `chain-authentik@file`, which still has nothing behind it, hence the override. Clear it once id01 is live. ntfy is hardcoded to `chain-no-auth@file` and ignores the setting, because publishers authenticate to ntfy itself rather than through a browser sign-in.

Leave every `[[GLOBAL_...]]` reference exactly as it is.

### Deploy

Save the Stack resource, then click **Deploy**.

All four services should come up. Both config files were put in place in step 1, so there is nothing to fix up afterwards and nothing to redeploy for.

## 4. Verify

Confirm all four services show running and healthy, in Komodo's container view for the resource:

```text
ntfy
mailrise
blackbox-exporter
uptime-kuma
```

mailrise starts after ntfy is healthy, so a stuck mailrise usually means ntfy is the real problem.

## 5. Create the ntfy accounts

ntfy deploys with `NTFY_AUTH_DEFAULT_ACCESS` set to `deny-all`, so nothing can publish or subscribe until you say so. Nothing is broken; it is waiting.

Make your own account first, which is the one you sign in to from the phone and desktop apps:

```bash
docker exec -it core-ntfy ntfy user add --role=admin <ntfy-user>
```

Then make a second account that can only publish, and only to the alert topics:

```bash
docker exec -it core-ntfy ntfy user add --role=user publisher
docker exec -it core-ntfy ntfy access publisher 'alerts-*' write-only
docker exec -it core-ntfy ntfy token add publisher
```

Keep the token that last command prints. Everything that sends alerts uses it, and handing out a write-only token is a good deal narrower than handing out your admin password.

Store it in Vaultwarden. It is the same token step 6 needs and the same one Alertmanager will need later.

## 6. Finish mailrise and point Proxmox at it

Replace both `REPLACE_WITH_NTFY_TOKEN` placeholders in the config seeded in step 1 with the token from step 5:

```bash
sudo sed -i 's/REPLACE_WITH_NTFY_TOKEN/<ntfy-token>/g' \
        /opt/docker/volumes/core/mailrise-secrets/mailrise.conf
```

Restart mailrise from Komodo so it reads the file again.

The example config routes on the recipient's local part, so the address a sender uses picks the topic the push lands on.

| Mail addressed to | Pushed to topic |
| --- | --- |
| `backups@mailrise.local` | `alerts-backups` |
| `infra@mailrise.local` | `alerts-infra` |

In both Proxmox Backup Server and Proxmox VE, under *Datacenter > Notifications*, add an SMTP target pointed at `<ci-ip>` on port `8025`, with no authentication and no TLS. Address it to `backups@mailrise.local`.

> [!WARNING]
> Keep the previous mail target as a second notification target for a couple of weeks rather than cutting straight over. A mistake in this path means no notifications at all, which is worse than the notifications-in-spam problem it replaces.

Subscribe to `alerts-backups` and `alerts-infra` from the ntfy app, signed in as the account from step 5, and send a test notification from Proxmox to confirm the whole path works.

## 7. First access to Uptime Kuma

Browse to `https://uptime-kuma.ci01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you actually set. Your browser will warn about the certificate, because traefik-bootstrap signs its own. Accept it and continue.

There are no default credentials. The first visit prompts you to create the admin account.

In its notification settings, add an ntfy notification pointed at `http://ntfy` with the publisher token. Uptime Kuma is the status page, not the alerting engine, but it should still land in the same place as everything else.

## What's next

ci01 is finished. It runs Semaphore, the VictoriaMetrics backend, and the notification and uptime services, and every VM built after this one reports to it from its first deploy.

blackbox-exporter is deployed but nothing probes anything yet. It is a multi-target proxy, so it needs a vmagent scrape job that rewrites each target into a `/probe` query parameter, and a vmalert rule on `probe_success` to notify through ntfy. The [generated README for core-infra](../stacks/core-infra/README.md) has the scrape job to copy. Both belong with the rest of the alerting work rather than here.

tf01 is the next VM, in [tf01 bootstrap](tf01-bootstrap.md). See [Running order](README.md#running-order) for the rest.
