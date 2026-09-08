# pk01 bootstrap runbook

pk01 runs step-ca, the internal certificate authority. It is what replaces the self-signed certificates traefik-bootstrap has been serving on every internal hostname, and it is the eventual home of the SSH CA that retires Semaphore's static key.

Its stack is `stacks/step-ca-server`, and it is the smallest in the repo: one service, one volume, no database.

It is also the only stack whose first boot is a ceremony rather than a deploy. step-ca generates a root key on that first start, and the root key has to be taken offline before this CA issues anything real. Read [the root key custody section](#5-the-root-key-ceremony) before you start, not when you reach it.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules, and it assumes you have worked through [ci01 bootstrap](ci01-bootstrap.md), which spells out the shared provisioning steps this page compresses into one.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Provision the VM](#1-provision-the-vm)
- [2. Create the runtime folders](#2-create-the-runtime-folders)
- [3. Deploy traefik-bootstrap onto pk01](#3-deploy-traefik-bootstrap-onto-pk01)
- [4. Create the Stack resource and the CA password](#4-create-the-stack-resource-and-the-ca-password)
- [5. The root key ceremony](#5-the-root-key-ceremony)
- [6. Verify](#6-verify)
- [What's next](#whats-next)

## Prerequisites

- km01 is finished through step 14 of [km01 bootstrap](komodo-bootstrap.md), so the nineteen `[[GLOBAL_...]]` Variables exist. This stack needs no other Variable or Secret.
- ci01 is finished, through [Semaphore setup](semaphore-setup.md).
- Two physically separate durable locations ready for the root key backup, and a way to reach Vaultwarden for the CA password. Step 5 needs both, and it is not a step to start and then pause.

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<template-vmid>` | VMID of the `ubuntu-server-2604` cloud-init template |
| `<pk-vmid>` | VMID to give the new VM |
| `<pk-ip>` | Static address for pk01 |
| `<gateway-ip>` | Gateway for that subnet |
| `<same>` | The value cloud-init already used, recovered rather than guessed |
| `<clone-dir>` | Where Periphery cloned this repo on pk01, found in step 4 rather than assumed |

## 1. Provision the VM

Follow steps 1 to 7 of [ci01 bootstrap](ci01-bootstrap.md), substituting pk01 throughout.

One service and no database, so this is the smallest VM in the fleet:

```bash
qm clone <template-vmid> <pk-vmid> --name pk01 --full
qm set <pk-vmid> --cores 2 --memory 2048
qm set <pk-vmid> --ipconfig0 ip=<pk-ip>/24,gw=<gateway-ip>
qm start <pk-vmid>
```

pk01 is internal-only and mesh-only. It is never published through bh01's tunnel. A CA that issues for the internal zone has no reason to answer from the internet.

Stop when pk01 shows connected and healthy under *Resources > Servers*, which is ci01's step 7.

## 2. Create the runtime folders

```bash
projectName="step-ca"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/step-ca-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/step-ca-data
```

`101000` here is the same rule every other stack follows, and it is worth checking rather than assuming: the service runs as its own `PUID`, so the container's UID 1000 is host UID 101000. See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000).

`step-ca-data` is the CA's entire state: its configuration, its database of issued certificates, and the encrypted intermediate key. Back it up.

## 3. Deploy traefik-bootstrap onto pk01

step-ca publishes no port. Traefik routes to it on `9000` over HTTPS, and without a Traefik on pk01 nothing can reach the CA.

Follow [How to deploy it](traefik-bootstrap.md#how-to-deploy-it), five steps ending with all five services healthy. Set its target *Server* to **pk01** and its `SERVER_NAME` to `pk01`, with the same sub-domain and domain you use in step 4.

step-ca's own router is hardcoded to `chain-no-auth@file` rather than reading `TRAEFIK_AUTH_CHAIN`, so there is no override to set here. That is deliberate, and it stays true after id01 exists: step-ca does its own authentication per provisioner, and a forward-auth hop in front of the ACME endpoint would break the unattended clients that need to reach it.

## 4. Create the Stack resource and the CA password

This stack is unusual in that a file has to exist on disk before the first successful start. `containers/step-ca/compose.yaml` mounts it:

```yaml
- ./secrets/password:/home/step/secrets/password:ro
```

That path is relative to `containers/step-ca/`, not to the stack directory, because Compose resolves a relative bind mount against the file that declares it and this service is reached through `extends`. So on pk01 the file lands under the repo Periphery clones, at `containers/step-ca/secrets/password`.

### Create the Stack resource

In Komodo's UI, go to *Resources > Stacks* and create a Stack named `step-ca-server`. Set its target *Server* to **pk01**.

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/step-ca-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

Open `stacks/step-ca-server/komodo.env`, copy its full contents, and paste them into *Environment*. Three keys need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `pk01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |

`STEPCA_CA_NAME` is committed as `h1 Internal CA` and is what the CA calls itself in every certificate it issues. Change it now if you want something else, because changing it later means reissuing.

Leave every `[[GLOBAL_...]]` reference as pasted. This stack needs nothing beyond km01's step 14.

### Write the password, then deploy

Save the Stack resource and click **Deploy** once. It will not come up, and that is expected: the password file does not exist yet, so Docker creates an empty directory where the file should be.

Find the clone and clean up that stray directory:

```bash
ls /opt/docker/repos/
sudo rm -rf <clone-dir>/containers/step-ca/secrets/password
```

Then generate the password:

```bash
head -c32 /dev/urandom | base64 | sudo tee <clone-dir>/containers/step-ca/secrets/password > /dev/null
sudo chmod 600 <clone-dir>/containers/step-ca/secrets/password
sudo chown 101000:101000 <clone-dir>/containers/step-ca/secrets/password
```

Store a copy in Vaultwarden, and a second copy in the same offline location as the root key backups from step 5. This password encrypts both the root and intermediate private keys at rest. Losing it after the root key is offline means the backup can never be unlocked again, which defeats the point of keeping one.

Click **Deploy** again. This time step-ca initialises: it generates the root and intermediate keys, writes its configuration, and starts answering.

> [!NOTE]
> Redeploying a Git Repo stack can re-clone over the run directory. Confirm the password file survived a redeploy before relying on it, and if it does not, keep a copy outside the clone and restore it as part of the deploy routine. This is worth settling on pk01 rather than discovering later.

## 5. The root key ceremony

Do this now, in one sitting, before this CA issues anything real.

At this point `/home/step/secrets/` inside the container holds both `root_ca_key` and `intermediate_ca_key`. Every certificate the fleet ever trusts chains back to the first one, and it should not stay on a running host.

The full procedure is in the [generated README for step-ca-server](../stacks/step-ca-server/README.md): extracting the root key, adding a second independent encryption layer with a passphrase that is not the CA password, copying it to two physically separate durable locations, removing it from the running container, and re-signing a throwaway intermediate to prove the backup actually works.

It is not repeated here because there is exactly one authoritative copy of it and this is not it.

Two things worth knowing before you open that page. The second passphrase must be different from the CA password and must be written down somewhere that is not solely Vaultwarden, because Vaultwarden itself may one day be gated behind a certificate this CA issued. And the verification step at the end is the whole point: an untested root key backup is not a backup.

## 6. Verify

Confirm the one service shows running and healthy in Komodo's container view:

```text
step-ca
```

Then check the CA answers, from pk01:

```bash
docker exec -it step-ca-step-ca step ca health --ca-url https://127.0.0.1:9000
```

That is the same command the container's own healthcheck runs, so a healthy container and a failing command here means the exec name is wrong rather than the CA.

Through Traefik, from anywhere on the internal network:

```bash
curl -k https://step-ca.pk01.home.myah-mitchell.com/health
```

The `-k` is expected while pk01 is still behind traefik-bootstrap. That certificate is self-signed, and replacing it is what the next phase of work is for.

## What's next

bh01 is the next VM, and it is the first one that faces the internet. See [bh01 bootstrap](bh01-bootstrap.md).

pk01 existing also unblocks two things that are not VM provisioning:

Traefik can start asking this CA for internal certificates instead of serving self-signed ones. `containers/traefik/compose.yaml` has a commented-out `internalca` resolver block for it, and the [step-ca stack README](../stacks/step-ca-server/README.md) is explicit that the DNS-01 specifics there are unverified and need real testing before being uncommented.

Semaphore's static SSH key can be replaced with a dedicated service principal on a short-lived, auto-renewed step-ca certificate. See [step 9 of Semaphore setup](semaphore-setup.md#14-replace-this-key-once-step-ca-is-live).

See [Running order](README.md#running-order) for where pk01 sits.
