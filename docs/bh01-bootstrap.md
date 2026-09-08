# bh01 bootstrap runbook

bh01 is the DMZ edge, and the only host in the fleet reachable from the internet. It reaches the internet outbound-only, through a Cloudflare Tunnel, so no port is ever forwarded to it and no WAN address points at it.

Its stack is `stacks/traefik-dmz`: the same traefik-agent bundle tf01 runs, plus a Redis replica of tf01's master and the cloudflared connector. Eleven services.

bh01 does not get `stacks/traefik-bootstrap`. Like tf01, it is a real Traefik.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules, and it assumes you have worked through [ci01 bootstrap](ci01-bootstrap.md) and [tf01 bootstrap](tf01-bootstrap.md).

> [!WARNING]
> The two repo changes described in [What has to change in the repo first](tf01-bootstrap.md#what-has-to-change-in-the-repo-first) apply here too. bh01 runs the same base Traefik service, wants the same Let's Encrypt resolver, and reads the same Redis provider. Settle both on tf01 before starting here.

## Contents

- [Prerequisites](#prerequisites)
- [1. Create the tunnel from an admin machine](#1-create-the-tunnel-from-an-admin-machine)
- [2. Provision the VM](#2-provision-the-vm)
- [3. Create the runtime folders](#3-create-the-runtime-folders)
- [4. Open the firewall](#4-open-the-firewall)
- [5. Create the Stack resource for traefik-dmz](#5-create-the-stack-resource-for-traefik-dmz)
- [6. Install the tunnel credentials and config](#6-install-the-tunnel-credentials-and-config)
- [7. Verify](#7-verify)
- [8. Publish the first hostname](#8-publish-the-first-hostname)
- [What's next](#whats-next)

## Prerequisites

- tf01 is finished, through [tf01 bootstrap](tf01-bootstrap.md). bh01's Redis is a replica of tf01's, and `TRAEFIK_KOP_REDIS_PASSWORD` and `TRAEFIK_KOP_REDIS_SERVER` were created there.
- km01 is finished through step 14 of [km01 bootstrap](komodo-bootstrap.md).
- ci01 is finished, through [Semaphore setup](semaphore-setup.md).
- A Cloudflare account holding the zone, and the `cloudflared` CLI installed on an admin machine that is not bh01.
- A DMZ VLAN that can reach the internal VLAN where tf01 lives, and a decision about what that firewall allows. Everything published through this tunnel crosses that boundary.

## 1. Create the tunnel from an admin machine

Do this first. The tunnel has to exist before the stack can connect to it, and creating it produces the credentials file step 6 installs.

Run these on an admin machine with the `cloudflared` CLI, not on bh01:

```bash
cloudflared tunnel login
cloudflared tunnel create home-edge
```

The first opens a browser and authorises against the Cloudflare account holding `myah-mitchell.com`. The second writes a credentials file to `~/.cloudflared/<tunnel-id>.json` and prints the tunnel ID. Keep both.

`home-edge` names this site's edge. A cloud site, if one is ever added, gets its own `cloud-edge` tunnel rather than sharing this one.

That credentials file is a real credential: anything holding it can serve traffic for your hostnames. Treat it the way this repo treats every other one, which means it lives in a `secrets/` folder and is never committed. See [config/ and secrets/](conventions.md#config-and-secrets).

## 2. Provision the VM

Follow [Provisioning a VM](provision-a-vm.md), seven steps ending with bh01 connected and healthy under *Resources > Servers*.

Give it four cores and 8 GB.

> [!IMPORTANT]
> At step 2 there, set the VLAN tag to the DMZ one, not the internal one every previous VM used. This is the only host in the running order where that differs, and it is the whole point of bh01.

The VM still provisions the same way, still runs Periphery, and still dials out to Core on km01. Periphery's connection is outbound, so a DMZ host that cannot be reached from the internal network still joins Komodo normally.

## 3. Create the runtime folders

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

cloudflared needs no volume here. Its two directories live inside the clone, and step 6 covers them.

This list mirrors the [generated README for traefik-dmz](../stacks/traefik-dmz/README.md), which `scripts/build.py` rebuilds. That file wins if the two disagree.

## 4. Open the firewall

```bash
sudo ufw allow 80/tcp comment 'Traefik HTTP'
sudo ufw allow 443/tcp comment 'Traefik HTTPS'
sudo ufw allow 8443/tcp comment 'Traefik HTTPS (alt)'
sudo ufw status
```

Those three are the ports the Traefik container publishes, and they are reachable only from inside the DMZ. Nothing on the internet reaches them, because nothing forwards to bh01.

Do not open `6379` here. bh01's Redis is a replica and publishes no port, unlike tf01's master. It connects outbound to tf01 instead.

## 5. Create the Stack resource for traefik-dmz

In Komodo's UI, go to *Resources > Stacks* and create a Stack named `traefik-dmz`. Set its target *Server* to **bh01**.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/traefik-dmz` |
| *File Path* | `compose.yaml`, relative to the run directory |

### Paste the environment

Open `stacks/traefik-dmz/komodo.env`, copy its full contents, and paste them into *Environment*.

Three keys need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `bh01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |

`PROJECT_NAME` stays the committed `traefik`, not `traefik-dmz`. Every traefik stack in the repo uses the same project name, which is why cloudflared's ingress rules point at the container `traefik-traefik`. It is safe because no host ever runs two of them.

Clear the same three keys tf01 clears, for the same reasons. See [Keys to clear](tf01-bootstrap.md#keys-to-clear).

`CF_API_EMAIL` and `CF_DNS_API_TOKEN` are the exception: keep those, because this Traefik wants a real certificate too. They resolve from the Secrets created in [tf01's step 4](tf01-bootstrap.md#4-create-the-four-komodo-secrets), as do `TRAEFIK_KOP_REDIS_PASSWORD` and `TRAEFIK_KOP_REDIS_SERVER`.

### Deploy

Save the Stack resource, then click **Deploy**. Ten of the eleven services should come up. cloudflared will not, because its config and credentials do not exist yet, and step 6 is what fixes that.

## 6. Install the tunnel credentials and config

cloudflared mounts two directories from inside the clone:

```yaml
- ./config:/etc/cloudflared:ro
- ./secrets:/etc/cloudflared/secrets:ro
```

Those paths are relative to `containers/cloudflared/`, not to the stack directory, because Compose resolves a relative bind mount against the file that declares it and this service is reached through `extends`.

Find the clone on bh01:

```bash
ls /opt/docker/repos/
```

`<clone-dir>` below is whichever path that prints, and `<tunnel-id>` is the UUID step 1 printed.

Copy the credentials file from step 1 into place, as `<tunnel-id>.json`:

```bash
sudo install -m 600 <tunnel-id>.json <clone-dir>/containers/cloudflared/secrets/<tunnel-id>.json
sudo chown 101000:101000 <clone-dir>/containers/cloudflared/secrets/<tunnel-id>.json
```

Then create the config from the example already in the clone:

```bash
sudo cp <clone-dir>/containers/cloudflared/config/config.yml.example \
        <clone-dir>/containers/cloudflared/config/config.yml
```

Edit that copy and fill in the real tunnel ID in both the `tunnel:` and `credentials-file:` lines. The example ships one ingress rule and a catch-all:

```yaml
ingress:
  - hostname: vault.myah-mitchell.com
    service: http://traefik-traefik:80

  - service: http_status:404
```

Every rule points at `http://traefik-traefik:80`, which is this stack's own Traefik on the `proxy` network. cloudflared never routes to a backend directly, and never to a WAN port. Traefik on bh01 is what decides where the request actually goes.

The catch-all matters. Without it, an unmatched hostname is proxied somewhere unintended rather than refused. Keep it last, because cloudflared matches rules in order.

Redeploy the stack. cloudflared should now connect and report healthy.

> [!NOTE]
> `config.yml` sits in `config/`, which this repo never gitignores, so a copy made inside the clone is visible to git even though only `secrets/` is ignored. That is intentional, since ingress hostnames are not secret, but check `git status` in the clone before committing anything from bh01.

## 7. Verify

Confirm all eleven services show running and healthy, in Komodo's container view:

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
cloudflared
```

Then confirm the Redis replica actually caught up with tf01:

```bash
docker exec traefik-redis redis-cli info replication
```

Look for `role:slave` and `master_link_status:up`. A replica that cannot reach its master reports `down` here and keeps serving stale data silently, which is the failure worth catching now rather than during an outage.

## 8. Publish the first hostname

Publishing is two steps: a DNS record, and an ingress rule.

Create the record from the admin machine, not the Cloudflare dashboard:

```bash
cloudflared tunnel route dns home-edge vault.myah-mitchell.com
```

That creates the public CNAME pointing at the tunnel. Repeat it per hostname.

Then add the matching ingress rule in `config.yml`, above the catch-all, and redeploy.

A published hostname has no sub-domain in it. `vault.myah-mitchell.com` is public, while `vault.home.myah-mitchell.com` is the internal name for the same service. That is why Authentik's own router answers on `auth.myah-mitchell.com` as well as its internal names. See [id01 bootstrap](id01-bootstrap.md#7-first-access).

Nothing should be published before it is behind `chain-authentik@file`, unless it does its own authentication. A hostname on this tunnel is on the internet the moment its DNS record exists.

## What's next

ap01 is the last VM in the running order. Its runbook is not written yet, and it cannot be: Vaultwarden has no container directory in this repo, so there is no stack to deploy. See [Running order](README.md#running-order).

The work that unblocks next is not another VM. It is `stacks/system-agent`, which replaces traefik-bootstrap on every VM still running it and puts each host into tf01's routing table. That needs ci01, id01, and pk01 all live, which they now are. See [Tearing it down](traefik-bootstrap.md#tearing-it-down).
