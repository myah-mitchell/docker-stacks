# Initial Deployment Requirements
## Prerequisites for using stalwart

A Stalwart Enterprise license for the domain, stored in a Komodo Secret named `STALWART_LICENSE_KEY`.

## Prerequisites for using bulwark

An Authentik OAuth2 application for Bulwark to sign in through. Its client ID and secret go in the Komodo Secrets `MAIL_OIDC_CLIENT_ID` and `MAIL_OIDC_CLIENT_SECRET`, and a 96-character random `BULWARK_SESSION_SECRET_KEY` goes beside them.

# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/mail` | Logs the stack's containers write to files |
| `/opt/docker/volumes/mail` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="mail"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for stalwart

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/mail/stalwart-config` | `102000:102000` | Not set |
| `/opt/docker/volumes/mail/stalwart-data` | `102000:102000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="mail"
mkdir -p /opt/docker/volumes/$projectName/stalwart-config
sudo chown 102000:102000 /opt/docker/volumes/$projectName/stalwart-config
mkdir -p /opt/docker/volumes/$projectName/stalwart-data
sudo chown 102000:102000 /opt/docker/volumes/$projectName/stalwart-data
```

</details>

Stalwart runs as the image's own UID 2000, so its directories belong to host UID `102000` rather than `101000`.

## Open the firewall for stalwart

The host's NixOS configuration opens these when the host is deployed.

| Port | Protocol | Allowed from | Used for |
| --- | --- | --- | --- |
| `25` | tcp | Any address | Stalwart SMTP |
| `465` | tcp | Any address | Stalwart submissions |
| `587` | tcp | Any address | Stalwart submission |
| `993` | tcp | Any address | Stalwart IMAPS |

## First start

With no `config.json`, Stalwart starts in bootstrap mode and prints a one-time admin password:

```bash
docker logs ${projectName}-stalwart 2>&1 | grep -A8 'bootstrap mode'
```

Sign in at `https://${STALWART_SERVICE_NAME}.${SERVER_NAME}.${SUB_DOMAIN_NAME}${DOMAIN_NAME}/admin` and run the setup wizard. The password changes on every bootstrap start.

## Recovery

Stop the container, then start a one-off copy in recovery mode against the same volumes. It serves only the admin UI, on `127.0.0.1:8080`:

```bash
docker run --rm -it --name ${projectName}-stalwart-recovery \
  --volumes-from ${projectName}-stalwart \
  -e STALWART_RECOVERY_MODE=1 \
  -e STALWART_RECOVERY_ADMIN=recovery:<recovery-password> \
  -p 127.0.0.1:8080:8080 \
  stalwartlabs/stalwart:v0.16.22
```

Never add either variable to the stack itself.

## Create needed folders for bulwark

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/mail/bulwark-data` | `101001:101001` | Not set |
| `/opt/docker/volumes/mail/bulwark-data/settings` | `101001:101001` | Not set |
| `/opt/docker/volumes/mail/bulwark-data/admin` | `101001:101001` | Not set |
| `/opt/docker/volumes/mail/bulwark-data/admin-state` | `101001:101001` | Not set |
| `/opt/docker/volumes/mail/bulwark-data/telemetry` | `101001:101001` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="mail"
mkdir -p /opt/docker/volumes/$projectName/bulwark-data
sudo chown 101001:101001 /opt/docker/volumes/$projectName/bulwark-data
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/settings
sudo chown 101001:101001 /opt/docker/volumes/$projectName/bulwark-data/settings
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/admin
sudo chown 101001:101001 /opt/docker/volumes/$projectName/bulwark-data/admin
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/admin-state
sudo chown 101001:101001 /opt/docker/volumes/$projectName/bulwark-data/admin-state
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/telemetry
sudo chown 101001:101001 /opt/docker/volumes/$projectName/bulwark-data/telemetry
```

</details>

Bulwark runs as the image's own UID 1001, so its directories belong to host UID `101001` rather than `101000`.
