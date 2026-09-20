# traefik-agent

traefik-agent is the Traefik half of a VM. It runs on the VMs that publish something of their own, next to [system-agent](system-agent-setup.md), and it is what [traefik-bootstrap](traefik-bootstrap.md) stands in for until the fleet can support the real thing.

Deploying it on a VM is how that VM stops being in bootstrap mode.

tf01 and bh01 do not follow this page. Their own stacks, traefik-server and traefik-dmz, include this one and bring the same services with them.

Read [Conventions](conventions.md) first. This page assumes its naming and secrets rules.

## Contents

- [What it runs](#what-it-runs)
- [When to deploy it](#when-to-deploy-it)
- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Create the runtime folders](#1-create-the-runtime-folders)
- [2. Open the firewall](#2-open-the-firewall)
- [3. Create the Stack resource](#3-create-the-stack-resource)
- [4. Paste the environment](#4-paste-the-environment)
- [5. Deploy and verify](#5-deploy-and-verify)
- [6. Tear down traefik-bootstrap](#6-tear-down-traefik-bootstrap)
- [What's next](#whats-next)

## What it runs

Six services.

Traefik terminates TLS for that VM's own services and puts them behind the Authentik auth chain, without tf01 being in the request path. error-pages, logrotate, socket-proxy, and socket-proxy-rw support it.

traefik-kop publishes a router into tf01's shared Redis, but only for a service that also carries a `kop-public.traefik.*` label, so reaching the wider network stays a per-service choice.

Its metrics and access log are collected by the system-agent stack on the same VM. Nothing in this stack ships telemetry itself.

## When to deploy it

Once id01, pk01, and tf01 are live. Traefik takes its certificate from pk01, its auth chain from id01, and traefik-kop writes to tf01's Redis, so deploying it earlier gets a Traefik that cannot issue a certificate and an auth chain that forwards to nothing.

Deploy [traefik-bootstrap](traefik-bootstrap.md) in the meantime, and come back here per VM once those three are up.

The ansible `stacks` role leaves this stack out of any run answered *Bootstrap* `true`, because `stacks/traefik-agent/setup.yaml` marks it as needing the rest of the fleet. That is also what makes the role prepare traefik-bootstrap on that host instead.

> [!WARNING]
> Do not run traefik-bootstrap and traefik-agent on the same VM at once. Both publish `:80`, `:443`, and `:8443` on the host and will fight over them. Step 6 is the handover.

## Prerequisites

- The target VM is a connected, healthy Komodo Server resource, from [Provisioning a VM](provision-a-vm.md), and already has the `proxy` Docker network.
- [system-agent](system-agent-setup.md) is deployed on the VM. Its dockns publishes the DNS records these routers are reached by, and its vector and vmagent are what collect this stack's access log and metrics.
- id01 is live, through [id01 bootstrap](id01-bootstrap.md), so `chain-authentik@file` resolves.
- pk01 is live, through [pk01 bootstrap](pk01-bootstrap.md), so Traefik can get a real internal certificate.
- tf01 is live, through [tf01 bootstrap](tf01-bootstrap.md), if you want traefik-kop to publish anything. The stack deploys without it; only `kop-public` routers stop working.
- km01's `[[GLOBAL_...]]` Variables exist, from step 14 of [km01 bootstrap](komodo-bootstrap.md).

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<host>` | The VM's hostname, for example `id01` |
| `<host-ip>` | That VM's address |

## 1. Create the runtime folders

Neither Periphery nor Compose creates host bind-mount directories, so these have to exist with the right ownership before the first deploy.

The ansible `stacks` role creates them from `stacks/traefik-agent/setup.yaml`, and opens step 2's ports in the same run.

Add `traefik-agent` to `<host>`'s `docker_stacks` list in ansible-private's `hosts.yml`, as in [step 10 of Semaphore setup](semaphore-setup.md#add-a-real-host-group-to-ansible-private), if it is not there already. The list is what the host runs once the site is finished, so it can carry this stack from the day the host is created.

Run **provision-stacks** with *Target* answered `<host>` and *Bootstrap* blank, then check the result on the VM:

```bash
sudo ls -ln /opt/docker/logs/traefik /opt/docker/volumes/traefik
```

The `traefik` log folder and both `traefik-` volume folders are owned by `101000`, and the log folder is mode `755`.

<details>
<summary>Manual steps, instead of ansible</summary>

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
```

</details>

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

The `755` mode on the Traefik log directory matters. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so a directory left group-writable by the default umask makes the logrotate container exit 1 every five minutes and access.log grows forever.

That directory is also where the system-agent stack's vector reads the access log from, which is why it lives under the `traefik` project rather than this stack's own name.

## 2. Open the firewall

Base provisioning enables UFW with a default-deny inbound policy and opens only what each host's own roles need. Traefik's three ports are not part of that, which is why the `stacks` role opens them.

Step 1's run opened all three rules. Confirm them on the VM:

```bash
sudo ufw status
```

`80/tcp`, `443/tcp`, and `8443/tcp` show `ALLOW` from `Anywhere`.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
sudo ufw allow 80/tcp comment 'Traefik HTTP'
sudo ufw allow 443/tcp comment 'Traefik HTTPS'
sudo ufw allow 8443/tcp comment 'Traefik HTTPS (alt)'
sudo ufw status
```

</details>

## 3. Create the Stack resource

In Komodo's UI, go to *Resources > Stacks*, create a Stack named `traefik-agent-<host>`, for example `traefik-agent-id01`, and set its target *Server* to that same VM.

Komodo requires every Stack name to be unique, and several VMs run this stack, so the host name goes on the end.

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/traefik-agent` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

## 4. Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/traefik-agent/komodo.env` in this repo, copy its full contents, and paste them into that field.

Three keys need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | The VM's hostname, `<host>` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |

Leave `TRAEFIK_AUTH_CHAIN` blank. Blank is what gets you the real `chain-authentik@file`, and this stack is the point at which that becomes correct.

Leave `TRAEFIK_TLS_OPTIONS` and `TRAEFIK_CERT_RESOLVER` as pasted, at `tls-opts@file` and `letsencrypt`. Those two are what separate this stack from [traefik-bootstrap](traefik-bootstrap.md), which runs the same service with a self-signed certificate and no resolver.

### Clear the two CrowdSec keys

Clear `CROWDSEC_LAPI_KEY` and `CROWDSEC_LAPI_HOST` to blank. The base Traefik service keeps its CrowdSec plugin lines commented out, so nothing reads either one, and no `GLOBAL_CROWDSEC_LAPI_HOST` Variable exists to resolve the second.

That is the same reason every runbook before this one clears them.

### Check that every reference resolves

A reference with no Variable or Secret behind it reaches Compose as the literal string, which usually surfaces as a type error rather than as a missing credential.

Nineteen `[[GLOBAL_...]]` references come from [step 14](komodo-bootstrap.md#14-create-komodos-global-variables) of the km01 runbook, and need no action. The rest come from later runbooks:

| Reference | Created in |
| --- | --- |
| `TRAEFIK_KOP_REDIS_PASSWORD`, `TRAEFIK_KOP_REDIS_SERVER` | [step 4 of tf01 bootstrap](tf01-bootstrap.md#4-create-the-five-komodo-secrets) |
| `CF_API_EMAIL`, `CF_DNS_API_TOKEN`, `LE_EMAIL` | The same step on tf01 |
| `GLOBAL_AUTHENTIK_HOST` | [step 8 of id01 bootstrap](id01-bootstrap.md#8-turn-on-chain-authentik-fleet-wide) |

That list is why this page sits after the host runbooks rather than after ci01. Two of them each contribute something it needs.

## 5. Deploy and verify

Save the Stack resource, then click **Deploy**. Watch the deploy log.

Confirm all six services show running and healthy:

```text
traefik
error-pages
logrotate
traefik-kop
socket-proxy
socket-proxy-rw
```

Then browse to `https://traefik.<host>.home.myah-mitchell.com`, substituting whatever sub-domain and domain you actually set. This is the first stack on the VM whose dashboard sits behind the real auth chain, so expect Authentik to ask you to sign in, and expect the certificate to be trusted rather than warned about. If the certificate is still self-signed, Traefik did not reach step-ca on pk01.

## 6. Tear down traefik-bootstrap

Only if this VM was running it. tf01 and bh01 never did, because their own stacks are a Traefik already.

Delete this VM's `traefik-bootstrap-<host>` Stack resource in Komodo. It cannot run alongside this one.

Then clear the `TRAEFIK_AUTH_CHAIN` override on every other stack on this VM that was set to `chain-no-auth@file`, and redeploy each. They fall back to `chain-authentik@file` and pick up the real auth chain.

Hostnames do not change in the handover. Only the certificate and the auth chain do.

## What's next

Repeat this page on every VM that publishes something of its own, and only `SERVER_NAME` differs between them.

Once this VM's Traefik has routed something, its access log shows up in VictoriaLogs under the `traefik-access` index, and its metrics under the `traefik` job. [system-agent](system-agent-setup.md#7-confirm-the-telemetry-is-arriving) is where both are checked.

On ci01, go back to [subscribe your phone](core-infra-setup.md#after-the-traefik-handover-subscribe-your-phone) once this page is done. ntfy is reachable from a phone only from this point on.

See [Running order](README.md#running-order) for which VMs are still waiting, and [Stacks](stacks.md) for what else lands on each one.
