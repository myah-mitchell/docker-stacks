# Initial Deployment Requirements
## Prerequisites for using mailrise

# Create and Setup Required Folders
## Create needed folders for mailrise

```bash
mkdir -p /opt/docker/volumes/$projectName/mailrise-secrets
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailrise-secrets
```

Seed the config from the tracked example, which this repo serves publicly, so no checkout has to exist yet:

```bash
sudo curl -fsSL -o /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf \
  https://raw.githubusercontent.com/myah-mitchell/docker-stacks/main/containers/mailrise/config/mailrise.conf.example
sudo chmod 600 /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailrise-secrets/mailrise.conf
```

Fill in the `token` value with the ntfy publish-only token created in ntfy's own post-deploy step.

Do all of this before the first deploy. Docker creates an empty directory in place of a missing bind-mount file, which makes mailrise fail at startup with nothing obvious to point at. The file lives here rather than in the repo checkout because Periphery re-clones over its run directory, which would take any file written inside it along with it.

## Point PBS and PVE at it

In both PBS's and PVE's notification settings, under *Datacenter > Notifications*, change the SMTP target to this VM's LAN IP and `${MAILRISE_SMTP_PORT}` (default `8025`), no auth, no TLS. mailrise accepts anything arriving on that port and re-emits it as an ntfy push per `mailrise.conf`'s routing rules (matched by the recipient address, so mail to `backups@mailrise.xyz` becomes a push to the `alerts-backups` topic). A config key with no domain matches only `@mailrise.xyz`, so any other recipient domain is refused.

Burn in rather than cutting over instantly. Leave PBS/PVE's previous (broken, spam-filtered) SMTP config as a secondary/backup notification target for a couple of weeks after switching to mailrise, so a bug in this new path doesn't silently mean "no notifications at all" instead of "notifications in spam."
