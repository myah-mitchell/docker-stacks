# Initial Deployment Requirements
## Prerequisites for using mailrise

# Create and Setup Required Folders
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
