# Initial Deployment Requirements
## Prerequisites for using postfix

A relay to send through, unless this host's public address can deliver mail itself. Most mail providers junk or refuse mail sent directly from a residential address, and Postfix here does no DKIM signing, so plan on an authenticated relay such as a mail host's SMTP submission service.

# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/core` | Logs the stack's containers write to files |
| `/opt/docker/volumes/core` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="core"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for ntfy

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/core/ntfy-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="core"
mkdir -p /opt/docker/volumes/$projectName/ntfy-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ntfy-data
```

</details>

## Post-deploy: create your account and a publish-only token

`NTFY_AUTH_DEFAULT_ACCESS=deny-all` means nothing can publish or subscribe until you explicitly grant access. Run once, inside the container, after first boot:

Your own account (subscribe from phone/desktop apps, and administer topics):

```bash
docker exec -it $projectName-ntfy ntfy user add --role=admin youruser
```

A token for services that only ever publish (vmalert, mailrise, blackbox_exporter alerts, PBS/PVE via mailrise). It is narrower than handing out your admin password:

```bash
docker exec -it $projectName-ntfy ntfy user add --role=user publisher
docker exec -it $projectName-ntfy ntfy access publisher 'alerts-*' write-only
docker exec -it $projectName-ntfy ntfy token add publisher
```

Use the resulting token as the `Authorization: Bearer <token>` header (or `ntfy://token@host/topic` Apprise-style URL) in Alertmanager's webhook config and `mailrise.conf`. Subscribe to the same `alerts-*` topics from the ntfy phone/desktop app using your own account.

## Create needed folders for mailrise

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/core/mailrise-secrets` | `101000:101000` | `0700` |

| Seed file | Copied from | Owner | Mode |
| --- | --- | --- | --- |
| `/opt/docker/volumes/core/mailrise-secrets/mailrise.conf` | `containers/mailrise/config/mailrise.conf.example` | `101000:101000` | `0600` |

A seed file is copied only when the target does not exist.

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="core"
mkdir -p /opt/docker/volumes/$projectName/mailrise-secrets
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailrise-secrets
sudo chmod 700 /opt/docker/volumes/$projectName/mailrise-secrets
sudo test -e /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf \
  || sudo curl -fsSL -o /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf \
  https://raw.githubusercontent.com/myah-mitchell/fleet-stacks/main/containers/mailrise/config/mailrise.conf.example
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf
sudo chmod 600 /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf
```

</details>

The config is copied from the tracked example only when it is not already there, so a filled-in token is never overwritten.

Fill in the `token` value with the ntfy publish-only token created in ntfy's own post-deploy step.

Do all of this before the first deploy. Docker creates an empty directory in place of a missing bind-mount file, which makes mailrise fail at startup with nothing obvious to point at. The file lives here rather than in the repo checkout because Periphery re-clones over its run directory, which would take any file written inside it along with it.

## Open the firewall for mailrise

The host's NixOS configuration opens these when the host is deployed.

| Port | Protocol | Allowed from | Used for |
| --- | --- | --- | --- |
| `8025` | tcp | The internal subnet | Mailrise SMTP |

## Point PBS and PVE at it

In both PBS's and PVE's notification settings, under *Datacenter > Notifications*, change the SMTP target to this VM's LAN IP and `${MAILRISE_SMTP_PORT}` (default `8025`), no auth, no TLS. mailrise accepts anything arriving on that port and re-emits it as an ntfy push per `mailrise.conf`'s routing rules (matched by the recipient address, so mail to `backups@mailrise.xyz` becomes a push to the `alerts-backups` topic). A config key with no domain matches only `@mailrise.xyz`, so any other recipient domain is refused.

Burn in rather than cutting over instantly. Leave PBS/PVE's previous (broken, spam-filtered) SMTP config as a secondary/backup notification target for a couple of weeks after switching to mailrise, so a bug in this new path doesn't silently mean "no notifications at all" instead of "notifications in spam."

## Create needed folders for postfix

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/core/postfix-data` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="core"
mkdir -p /opt/docker/volumes/$projectName/postfix-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postfix-data
```

</details>

Postfix runs as the image's own root, so its queue directory belongs to host UID `100000` rather than `101000`. Postfix creates the queue's subdirectories itself on first start.

## Open the firewall for postfix

The host's NixOS configuration opens these when the host is deployed.

| Port | Protocol | Allowed from | Used for |
| --- | --- | --- | --- |
| `25` | tcp | The internal subnet | Postfix SMTP |

Keep it scoped to the internal subnet. Postfix relays for any private address with no login, which is fine for a LAN-only relay and not fine for anything wider.

## Point services at it

| Setting | Value |
| --- | --- |
| Server | This VM's LAN address |
| Port | `${POSTFIX_SMTP_PORT}`, default `25` |
| Encryption | None |
| Authentication | None |
| From address | Any address in `POSTFIX_ALLOWED_SENDER_DOMAINS`, which defaults to `DOMAIN_NAME` |

The sender check is an exact match on the domain. `pve@myah-mitchell.com` is relayed, while `root@pve.home.myah-mitchell.com` is refused until that sub-domain is added to the list.

Postfix also refuses a recipient whose domain has no DNS record, so a typo in a recipient domain fails at the sending service rather than bouncing later.

## Create needed folders for mailpit

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/core/mailpit-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="core"
mkdir -p /opt/docker/volumes/$projectName/mailpit-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailpit-data
```

</details>

## Reading the copies

Browse to `https://${MAILPIT_SERVICE_NAME}.${SUB_DOMAIN_NAME}${DOMAIN_NAME}`. The UI is behind `chain-authentik@file` by default, because the copies include password reset and sign-in links.

Mailpit keeps the newest `MAILPIT_MAX_MESSAGES` copies, and nothing older than `MAILPIT_MAX_AGE`. A copy showing here proves the sending service reached Postfix. It does not prove the relay accepted the original, so check Postfix's log for that:

```bash
docker logs ${projectName}-postfix 2>&1 | grep 'status='
```

`status=sent` from the relay is delivered onward. `status=deferred` is queued for retry, and the reason follows in brackets.

## Create needed folders for blackbox-exporter

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/core/blackbox-exporter-config` | `101000:101000` | Not set |

| Seed file | Copied from | Owner | Mode |
| --- | --- | --- | --- |
| `/opt/docker/volumes/core/blackbox-exporter-config/blackbox.yml` | `containers/blackbox-exporter/config/blackbox.yml.example` | `101000:101000` | Not set |

A seed file is copied only when the target does not exist.

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="core"
mkdir -p /opt/docker/volumes/$projectName/blackbox-exporter-config
sudo chown 101000:101000 /opt/docker/volumes/$projectName/blackbox-exporter-config
sudo test -e /opt/docker/volumes/$projectName/blackbox-exporter-config/blackbox.yml \
  || sudo curl -fsSL -o /opt/docker/volumes/$projectName/blackbox-exporter-config/blackbox.yml \
  https://raw.githubusercontent.com/myah-mitchell/fleet-stacks/main/containers/blackbox-exporter/config/blackbox.yml.example
sudo chown 101000:101000 /opt/docker/volumes/$projectName/blackbox-exporter-config/blackbox.yml
```

</details>

The config is copied from the tracked example only when it is not already there, so local edits are never overwritten.

Edit that copy to add or adjust probe modules. It is usable unchanged, defining probe modules and nothing host-specific.

Do all of this before the first deploy. Docker creates an empty directory in place of a missing bind-mount file, which makes blackbox-exporter fail at startup with nothing obvious to point at. The file lives here rather than in the repo checkout because Periphery re-clones over its run directory, which would take any file written inside it along with it.

## vmagent scrape config

blackbox_exporter is a multi-target proxy, so vmagent needs a scrape job with `relabel_configs` rewriting the target into a `/probe` query param. Example addition to `vmagent`'s `prometheus.yml`:

```yaml
- job_name: 'blackbox-http'
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - https://vault.myah-mitchell.com
        - https://ntfy.home.myah-mitchell.com
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: blackbox-exporter:9115
```

Pair with a `vmalert` rule (`probe_success == 0`) notifying through `ntfy` (Phase 2). That is the "is it actually up" signal Icinga used to provide.

## Create needed folders for uptime-kuma

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/core/uptime-kuma-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="core"
mkdir -p /opt/docker/volumes/$projectName/uptime-kuma-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/uptime-kuma-data
```

</details>

## Post-deploy

First visit to the web UI prompts for the admin account (no default credentials to change). Configure its own notification integration to point at `ntfy` (built-in ntfy notification type) so status-page state changes land in the same place as everything else. This is a complement to `blackbox-exporter`/`vmalert` (which do the actual metrics-driven alerting). Uptime Kuma is here purely for the simple, glanceable green/red status page.
