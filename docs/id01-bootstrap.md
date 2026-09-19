# id01 bootstrap runbook

id01 runs Authentik, the fleet's identity provider. Nearly every stack in this repo defaults its Traefik router to `chain-authentik@file`, and until id01 exists that middleware points at nothing, which is why every VM so far has needed `TRAEFIK_AUTH_CHAIN` overridden to `chain-no-auth@file`.

Its stack is authentik-server: the Authentik server and worker, their Postgres and its backup sidecar, a Redis, geoipupdate, and a socket-proxy. Seven services.

Authentik cannot sit behind Authentik, so its own router is hardcoded to `chain-no-auth@file` rather than reading `TRAEFIK_AUTH_CHAIN`. It still needs a Traefik on id01 to be reachable at all, and that is traefik-bootstrap until system-agent is ready.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules, and it assumes you have worked through [ci01 bootstrap](ci01-bootstrap.md).

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Provision the VM](#1-provision-the-vm)
- [2. Create the runtime folders](#2-create-the-runtime-folders)
- [3. Deploy traefik-bootstrap onto id01](#3-deploy-traefik-bootstrap-onto-id01)
- [4. Create the Komodo Secrets and Variables](#4-create-the-komodo-secrets-and-variables)
- [5. Create the Stack resource for authentik-server](#5-create-the-stack-resource-for-authentik-server)
- [6. Verify](#6-verify)
- [7. First access](#7-first-access)
- [8. Turn on chain-authentik fleet-wide](#8-turn-on-chain-authentik-fleet-wide)
- [What's next](#whats-next)

## Prerequisites

- km01 is finished through step 14 of [km01 bootstrap](komodo-bootstrap.md), so the nineteen `[[GLOBAL_...]]` Variables exist.
- ci01 is finished, through [ci01 bootstrap](ci01-bootstrap.md), so this host's metrics and logs have a backend once system-agent replaces traefik-bootstrap here. The Node Exporter password needs nothing from ci01: cloud-init's first run of the monitoring role generates it, and [step 4 of Provisioning a VM](provision-a-vm.md#4-verify-base-provisioning) checks it is there.
- A MaxMind account, for the free GeoLite2 databases. Signing up is free and takes a few minutes. Step 4 explains what happens if you skip it.

## Placeholders

The first six are the ones [Provisioning a VM](provision-a-vm.md) takes from this page. It lists four more that are the same for every host.

| Placeholder | Value |
| --- | --- |
| `<host>` | `id01` |
| `<cores>` | `4` |
| `<memory>` | `8192` |
| `<vmid>` | VMID to give the new VM, yours to pick |
| `<ip>` | Static address for id01, on the internal VLAN |
| `<gateway-ip>` | The internal VLAN's gateway |
| `<ci-ip>` | ci01's LAN address, where Postfix listens |

## 1. Provision the VM

Follow [Provisioning a VM](provision-a-vm.md), six steps ending with id01 connected and healthy under *Resources > Servers*.

Four cores and 8 GB because Authentik's worker is the memory-hungry part, and Postgres sits alongside it.

id01 is on the internal VLAN. Authentik is reached from the internet through bh01's tunnel later, never by exposing id01 directly.

## 2. Create the runtime folders

The ansible `stacks` role creates these from `stacks/authentik-server/setup.yaml`.

In ansible-private's `hosts.yml`, add id01 to the `docker_host` group if it is not there yet, and add the `traefik-bootstrap` and `authentik-server` stacks to its `docker_stacks` list, as in [step 10 of Semaphore setup](semaphore-setup.md#add-a-real-host-group-to-ansible-private). Commit and push it, and paste the new contents into Semaphore's **ansible-fleet** Inventory, as in [Load it into Semaphore](semaphore-setup.md#load-it-into-semaphore).

Run **provision-stacks** with *Target* answered `id01`. Listing both stacks means this one run also covers the folders and ports for step 3's traefik-bootstrap.

Check the result on id01:

```bash
sudo ls -ln /opt/docker/volumes/authentik
```

`postgres-data` and `postgres-backup-data` are owned by `100000`, and the other four folders by `101000`.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
projectName="authentik"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/authentik-media
mkdir -p /opt/docker/volumes/$projectName/authentik-templates
mkdir -p /opt/docker/volumes/$projectName/authentik-certs
sudo chown 101000:101000 /opt/docker/volumes/$projectName/authentik-*

mkdir -p /opt/docker/volumes/$projectName/geoip-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/geoip-*

mkdir -p /opt/docker/volumes/$projectName/postgres-data
mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*
```

</details>

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

`postgres-data` is the one that matters. It holds every user, group, application, and flow you configure from here on. `postgres-backup-data` gets daily, weekly, and monthly dumps of it, and the [generated README for authentik-server](../stacks/authentik-server/README.md) has the restore procedure. Test a restore before you trust it.

That generated README is also the authority for this folder list, and `scripts/build.py` rebuilds it.

## 3. Deploy traefik-bootstrap onto id01

Authentik publishes no port directly. Without a Traefik on id01 there is no way to reach its setup flow, and the setup flow is the only way to create the first admin account.

Follow [How to deploy it](traefik-bootstrap.md#how-to-deploy-it), five steps ending with all five services healthy. Name the Stack `traefik-bootstrap-id01`, set its target *Server* to **id01**, and set its `SERVER_NAME` to `id01`, with the same sub-domain and domain you use in step 5.

There is a real ordering trap here. traefik-bootstrap is what makes Authentik reachable, and Authentik is what eventually makes traefik-bootstrap unnecessary. Deploy the bootstrap Traefik first, then Authentik, and tear the bootstrap down per VM only once each VM's real stack is ready.

## 4. Create the Komodo Secrets and Variables

`stacks/authentik-server/komodo.env` carries twelve references that no earlier runbook creates. This step creates ten of them, and step 5 clears the other two.

In Komodo's UI on km01, go to *Settings > Secrets* and create these three. They are real credentials.

| Secret | Value |
| --- | --- |
| `AUTHENTIK_SECRET_KEY` | 96 alphanumeric characters of your choice |
| `AUTHENTIK_POSTGRES_USER` | Your choice |
| `AUTHENTIK_POSTGRES_PASSWORD` | Your choice, alphanumeric only |

`AUTHENTIK_SECRET_KEY` signs sessions and encrypts stored credentials. Rotating it invalidates every active session and every secret Authentik holds, so treat it the way [Semaphore's three encryption keys](semaphore-setup.md#2-generate-semaphores-three-encryption-keys) are treated: set once, back it up, leave it alone.

The alphanumeric-only rule applies here for the usual reason. See [Conventions](conventions.md#alphanumeric-only).

### The MaxMind credentials

Still on *Settings > Secrets*, create these two:

| Secret | Value |
| --- | --- |
| `GLOBAL_GEOIPUPDATE_ACCOUNT_ID` | Your MaxMind account ID |
| `GLOBAL_GEOIPUPDATE_LICENSE_KEY` | A MaxMind licence key |

These are `GLOBAL_` because geoipupdate appears in more than one stack, not because km01's step 14 created them. It did not.

`scripts/build.py` deliberately never generates these. A licence key is issued by MaxMind, so a random value would look filled in and fail at the first download. See [Conventions](conventions.md#secrets).

Without them, geoipupdate starts, fails to authenticate, and reports unhealthy, which shows the whole stack as degraded in Komodo. Nothing else breaks, because the CrowdSec bouncer that would read the databases is commented out anyway. It is still worth having the stack come up clean.

### The email settings

Authentik sends its mail through Postfix on ci01, which you tested in [step 8 of Core infrastructure setup](core-infra-setup.md#8-send-a-test-message-through-postfix). Go to *Settings > Variables* and create these five. They are configuration rather than credentials.

| Variable | Value |
| --- | --- |
| `GLOBAL_EMAIL_HOST` | `<ci-ip>` |
| `GLOBAL_EMAIL_PORT` | `25` |
| `GLOBAL_EMAIL_TLS` | `false` |
| `GLOBAL_EMAIL_SSL` | `false` |
| `GLOBAL_EMAIL_FROM` | The address Authentik sends as, such as `authentik@myah-mitchell.com` |

The From address has to be in a domain ci01's `POSTFIX_ALLOWED_SENDER_DOMAINS` lists, which is `DOMAIN_NAME` unless you changed it. Postfix refuses mail from any other domain.

Postfix asks nothing on the LAN for a login, so there is no `GLOBAL_EMAIL_USER` or `GLOBAL_EMAIL_PASS` to create. TLS stays off for the same reason: the connection never leaves the LAN, and Postfix applies TLS itself when it hands the mail on to your relay.

Authentik reads these at startup and does not test the connection, so a mistake surfaces only when a flow actually tries to send, such as a password recovery. Every message it sends also lands in Mailpit on ci01, which is the quickest place to look.

## 5. Create the Stack resource for authentik-server

In Komodo's UI, go to *Resources > Stacks* and create a Stack named `authentik-server`. Set its target *Server* to **id01**, the resource from step 1.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/authentik-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### Paste the environment

Open `stacks/authentik-server/komodo.env` in this repo, copy its full contents, and paste them into *Environment*.

Three keys need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `id01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |

Three more are blank and stay that way: `POSTGRES_BACKUP_DB`, `POSTGRES_BACKUP_USER`, and `POSTGRES_BACKUP_PASSWORD`. This stack's `compose.yaml` points all three at the same database, user, and password its own Postgres service already resolves.

Leave `PROJECT_NAME` as the committed `authentik`, and leave the hostname keys alone. `AUTHENTIK_SERVICE_NAME` is `auth`, which is the short public hostname Authentik answers on once bh01's tunnel exists.

Clear `AUTHENTIK_EMAIL__USERNAME` and `AUTHENTIK_EMAIL__PASSWORD` to blank, because Postfix takes no login. Leave every other `[[...]]` reference as pasted. They all resolve now, from step 4 and from km01's step 14.

### Deploy

Save the Stack resource, then click **Deploy**. Watch the deploy log.

The first deploy is slow. Authentik runs its full database migration before the server answers, and the worker will restart a few times while Postgres finishes coming up. Give it several minutes before treating a failure as real.

## 6. Verify

Confirm all seven services show running and healthy, in Komodo's container view for the resource:

```text
authentik-server
authentik-worker
postgres
postgres-backup
redis
geoipupdate
socket-proxy
```

geoipupdate is the one that can legitimately be unhealthy, if you skipped the MaxMind credentials in step 4.

## 7. First access

Browse to `https://authentik.id01.home.myah-mitchell.com/if/flow/initial-setup/`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you set.

Your browser will warn about the certificate. That is expected: traefik-bootstrap serves a self-signed one. Accept it and continue.

That path is Authentik's own one-time setup flow. It creates the `akadmin` account and then stops answering, so a second visit after setup redirects to the normal login page.

Set a real password there and store it in Vaultwarden. This account can grant itself anything in the fleet once step 8 is done.

The stack answers on several hostnames, all pointed at the same service. `authentik.id01.home.myah-mitchell.com` is the one to use while id01 is internal-only. `auth.myah-mitchell.com` has no sub-domain in it deliberately, and is the hostname meant to be published through bh01's tunnel later.

## 8. Turn on chain-authentik fleet-wide

This is what id01 was for.

`containers/traefik/rules/middlewares-authentik.yaml` builds its forwardAuth address from an environment variable read inside each Traefik container:

```yaml
address: https://{{env "AUTHENTIK_HOST"}}/outpost.goauthentik.io/auth/traefik
```

Every stack's `komodo.env` already passes `AUTHENTIK_HOST: [[GLOBAL_AUTHENTIK_HOST]]`, and every runbook so far has told you to clear it, because the Variable did not exist.

Go to *Settings > Variables* and create it now:

| Variable | Value |
| --- | --- |
| `GLOBAL_AUTHENTIK_HOST` | `authentik.id01.home.myah-mitchell.com` |

Hostname only, with no scheme and no trailing slash. The rule file supplies the `https://` itself.

Then, per stack, stop clearing `AUTHENTIK_HOST` and stop overriding `TRAEFIK_AUTH_CHAIN`. Both revert to their committed defaults, which is `chain-authentik@file`, and that stack's next deploy comes up gated.

Do this one stack at a time, starting with something you can afford to lock yourself out of. Authentik also needs a Provider and an Application configured for each hostname before forwardAuth returns anything but a redirect loop, and that configuration lives in Authentik's own UI rather than in this repo.

Tearing down each VM's traefik-bootstrap is the last part, and it belongs with system-agent rather than here. See [system-agent](system-agent-setup.md), which does the handover per VM in its step 7.

## What's next

pk01 is the next VM, and step-ca is what replaces the self-signed certificates that traefik-bootstrap has been serving on every internal hostname.

See [pk01 bootstrap](pk01-bootstrap.md), and [Running order](README.md#running-order) for where id01 sits.
