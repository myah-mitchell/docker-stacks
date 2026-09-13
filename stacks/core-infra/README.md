# Create and Setup Required Folders
## Create Stack Folders

```bash
projectName="core"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

## Create needed folders for ntfy

```bash
mkdir -p /opt/docker/volumes/$projectName/ntfy-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ntfy-*
```

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

The compose file mounts this config as `./secrets/mailrise.conf`, and that path is relative to `containers/mailrise/` rather than to the stack directory, because Compose resolves a relative bind mount against the file that declares it. So it belongs in this container's own `secrets/` folder, inside whichever checkout of this repo the stack runs from:

```bash
cp containers/mailrise/config/mailrise.conf.example \
   containers/mailrise/secrets/mailrise.conf
```

Fill in the `token` value with the ntfy publish-only token created in ntfy's own post-deploy step. It goes in `secrets/` rather than `config/`, which only ever holds the non-secret example and is always tracked in git.

Create it before the first start. Docker creates an empty directory in place of a missing bind-mount file, which makes mailrise fail at startup with nothing obvious to point at.

## Point PBS and PVE at it

In both PBS's and PVE's notification settings, under *Datacenter > Notifications*, change the SMTP target to this VM's LAN IP and `${MAILRISE_SMTP_PORT}` (default `8025`), no auth, no TLS. mailrise accepts anything arriving on that port and re-emits it as an ntfy push per `mailrise.conf`'s routing rules (matched by the recipient address, so mail to `backups@mailrise.local` becomes a push to the `alerts-backups` topic).

Burn in rather than cutting over instantly. Leave PBS/PVE's previous (broken, spam-filtered) SMTP config as a secondary/backup notification target for a couple of weeks after switching to mailrise, so a bug in this new path doesn't silently mean "no notifications at all" instead of "notifications in spam."

## Create needed folders for blackbox-exporter

The compose file mounts this config as `./config/blackbox.yml`, and that path is relative to `containers/blackbox-exporter/` rather than to the stack directory, because Compose resolves a relative bind mount against the file that declares it. So it belongs in this container's own `config/` folder, inside whichever checkout of this repo the stack runs from:

```bash
cp containers/blackbox-exporter/config/blackbox.yml.example \
   containers/blackbox-exporter/config/blackbox.yml
```

Edit that copy to add or adjust probe modules. Create it before the first start. Docker creates an empty directory in place of a missing bind-mount file, which makes blackbox-exporter fail at startup with nothing obvious to point at.

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

```bash
mkdir -p /opt/docker/volumes/$projectName/uptime-kuma-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/uptime-kuma-*
```

## Post-deploy

First visit to the web UI prompts for the admin account (no default credentials to change). Configure its own notification integration to point at `ntfy` (built-in ntfy notification type) so status-page state changes land in the same place as everything else. This is a complement to `blackbox-exporter`/`vmalert` (which do the actual metrics-driven alerting). Uptime Kuma is here purely for the simple, glanceable green/red status page.
