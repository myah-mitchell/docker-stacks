# bh01 bootstrap runbook

bh01 is the DMZ edge, and the only host in the fleet reachable from the internet. It reaches the internet outbound-only, through a Cloudflare Tunnel, so no port is ever forwarded to it and no WAN address points at it.

The optional mx01 is the one exception. Mail cannot travel through a Cloudflare Tunnel, so mx01 takes its mail ports by port forward, and publishes its web side through this tunnel like everything else. See [mx01 bootstrap](mx01-bootstrap.md).

Its stack is traefik-dmz: the same traefik-agent bundle tf01 runs, plus a Redis replica of tf01's master and the cloudflared connector. Eleven services.

bh01 does not get traefik-bootstrap. Like tf01, it is a real Traefik.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules, and it assumes you have worked through [ci01 bootstrap](ci01-bootstrap.md) and [tf01 bootstrap](tf01-bootstrap.md).

> [!WARNING]
> bh01 runs the same base Traefik service as tf01, with the same Let's Encrypt resolver and the same Redis provider, pointed at its own local replica. See [What tf01 turns on in the base Traefik service](tf01-bootstrap.md#what-tf01-turns-on-in-the-base-traefik-service), and bring tf01 up first.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Create the tunnel from an admin machine](#1-create-the-tunnel-from-an-admin-machine)
- [2. Provision the VM](#2-provision-the-vm)
- [3. Create the runtime folders and install the tunnel config](#3-create-the-runtime-folders-and-install-the-tunnel-config)
- [4. Open the firewall](#4-open-the-firewall)
- [5. Create the Stack resource for traefik-dmz](#5-create-the-stack-resource-for-traefik-dmz)
- [6. Verify](#6-verify)
- [7. Publish the first hostname](#7-publish-the-first-hostname)
- [What's next](#whats-next)

## Prerequisites

- tf01 is finished, through [tf01 bootstrap](tf01-bootstrap.md). bh01's Redis is a replica of tf01's, and `TRAEFIK_KOP_REDIS_PASSWORD` and `TRAEFIK_KOP_REDIS_SERVER` were created there.
- km01 is finished through step 14 of [km01 bootstrap](komodo-bootstrap.md).
- ci01 is finished, through [Semaphore setup](semaphore-setup.md).
- A Cloudflare account holding the zone, and the `cloudflared` CLI installed on an admin machine that is not bh01.
- A DMZ VLAN that can reach the internal VLAN where tf01 lives, and a decision about what that firewall allows. Everything published through this tunnel crosses that boundary.

## Placeholders

The first six are the ones [Provisioning a VM](provision-a-vm.md) takes from this page. It lists four more that are the same for every host.

| Placeholder | Value |
| --- | --- |
| `<host>` | `bh01` |
| `<cores>` | `4` |
| `<memory>` | `8192` |
| `<vmid>` | VMID to give the new VM, yours to pick |
| `<ip>` | Static address for bh01, on the DMZ VLAN |
| `<gateway-ip>` | The DMZ VLAN's gateway, not the internal one every host before this used |
| `<tunnel-id>` | The tunnel's UUID, printed when you create it in step 1 |

## 1. Create the tunnel from an admin machine

Do this first. The tunnel has to exist before the stack can connect to it, and creating it produces the credentials file step 3 installs.

Run these on an admin machine with the `cloudflared` CLI, not on bh01:

```bash
cloudflared tunnel login
cloudflared tunnel create home-edge
```

The first opens a browser and authorises against the Cloudflare account holding `myah-mitchell.com`. The second writes a credentials file to `~/.cloudflared/<tunnel-id>.json` and prints the tunnel ID. Keep both.

`home-edge` names this site's edge. A cloud site, if one is ever added, gets its own `cloud-edge` tunnel rather than sharing this one.

That credentials file is a real credential: anything holding it can serve traffic for your hostnames. Treat it the way this repo treats every other one, which means it lives on the host under `/opt/docker/volumes`, outside any repo checkout, and is never committed. See [config/ and secrets/](conventions.md#config-and-secrets).

## 2. Provision the VM

Follow [Provisioning a VM](provision-a-vm.md), six steps ending with bh01 connected and healthy under *Resources > Servers*.

> [!IMPORTANT]
> At step 2 there, set the VLAN tag to the DMZ one, and take both `<ip>` and `<gateway-ip>` from the DMZ network. This is the only host in the running order where any of that differs, and it is the whole point of bh01.

The VM still provisions the same way, still runs Periphery, and still dials out to Core on km01. Periphery's connection is outbound, so a DMZ host that cannot be reached from the internal network still joins Komodo normally.

## 3. Create the runtime folders and install the tunnel config

The ansible `stacks` role creates these from `stacks/traefik-dmz/setup.yaml`, seeds cloudflared's ingress config, and opens step 4's ports in the same run. The tunnel credentials stay a manual step, because they come from your admin machine rather than from this repo.

In ansible-private's `hosts.yml`, add bh01 to the `docker_host` group if it is not there yet, and add the `traefik-dmz` stack to its `docker_stacks` list, as in [step 10 of Semaphore setup](semaphore-setup.md#add-a-real-host-group-to-ansible-private). Commit and push it, and paste the new contents into Semaphore's **ansible-fleet** Inventory, as in [Load it into Semaphore](semaphore-setup.md#load-it-into-semaphore).

Run **provision-stacks** with *Target* answered `bh01`, then check the result on bh01:

```bash
sudo ls -ln /opt/docker/logs/traefik /opt/docker/volumes/traefik
```

Every folder is owned by `101000`. The `traefik` log folder is mode `755`, and `cloudflared-secrets` is mode `700`.

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

mkdir -p /opt/docker/volumes/$projectName/vmagent-data
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vmagent-*
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vlagent-*
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vector-*

mkdir -p /opt/docker/volumes/$projectName/cloudflared-config
mkdir -p /opt/docker/volumes/$projectName/cloudflared-secrets
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cloudflared-*
sudo chmod 700 /opt/docker/volumes/$projectName/cloudflared-secrets
```

</details>

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

The `755` mode on the Traefik log directory matters. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so a directory left group-writable by the default umask makes the logrotate container exit 1 every five minutes and access.log grows forever.

cloudflared's two directories are host volumes for the same reason every other one is. Periphery re-clones over its run directory, so a credential written inside the checkout does not survive.

### Install the tunnel credentials

Copy the credentials file from step 1 onto bh01, then put it in place as `<tunnel-id>.json`:

```bash
sudo install -m 600 <tunnel-id>.json \
  /opt/docker/volumes/traefik/cloudflared-secrets/<tunnel-id>.json
sudo chown 101000:101000 \
  /opt/docker/volumes/traefik/cloudflared-secrets/<tunnel-id>.json
```

### Write the ingress config

The `stacks` run above seeded it from the example this repo serves publicly. A copy already on the host is never replaced, so your edits survive later runs.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
sudo curl -fsSL -o /opt/docker/volumes/traefik/cloudflared-config/config.yml \
  https://raw.githubusercontent.com/myah-mitchell/docker-stacks/main/containers/cloudflared/config/config.yml.example
sudo chown 101000:101000 /opt/docker/volumes/traefik/cloudflared-config/config.yml
```

</details>

Edit that copy and fill in the real tunnel ID in both the `tunnel:` and `credentials-file:` lines. The example ships one ingress rule and a catch-all:

```yaml
ingress:
  - hostname: vault.myah-mitchell.com
    service: http://traefik-traefik:80

  - service: http_status:404
```

Every rule points at `http://traefik-traefik:80`, which is this stack's own Traefik on the `proxy` network. cloudflared never routes to a backend directly, and never to a WAN port. Traefik on bh01 is what decides where the request actually goes.

The catch-all matters. Without it, an unmatched hostname is proxied somewhere unintended rather than refused. Keep it last, because cloudflared matches rules in order.

This list mirrors the [generated README for traefik-dmz](../stacks/traefik-dmz/README.md), which `scripts/build.py` rebuilds. That file wins if the two disagree.

## 4. Open the firewall

Step 3's run opened these. Confirm them on bh01:

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

Those three are the ports the Traefik container publishes, and they are reachable only from inside the DMZ. Nothing on the internet reaches them, because nothing forwards to bh01.

The role does not open `6379` here, and neither should you. bh01's Redis is a replica and publishes no port, unlike tf01's master. It connects outbound to tf01 instead.

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

`CF_API_EMAIL`, `CF_DNS_API_TOKEN`, and `LE_EMAIL` are the exception: keep those, because this Traefik wants a real certificate too. They resolve from the Secrets created in [tf01's step 4](tf01-bootstrap.md#4-create-the-five-komodo-secrets), as do `TRAEFIK_KOP_REDIS_PASSWORD` and `TRAEFIK_KOP_REDIS_SERVER`.

### Deploy

Save the Stack resource, then click **Deploy**. All eleven services should come up, cloudflared included, because its config and credentials went in during step 3.

## 6. Verify

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

## 7. Publish the first hostname

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

The work that unblocks next is not another VM. It is system-agent, which replaces traefik-bootstrap on every VM still running it and puts each host into tf01's routing table. That needs ci01, id01, and pk01 all live, which they now are.

Run [system-agent](system-agent-setup.md) once per VM, ci01 included. Its step 7 is where each VM's traefik-bootstrap comes down.
