# Initial Deployment Requirements
## Prerequisites for using mailrise

# Create and Setup Required Folders
## Create needed folders for mailrise

```bash
mkdir -p /opt/docker/stacks/$projectName/mailrise/config
mkdir -p /opt/docker/stacks/$projectName/mailrise/secrets
```

Copy `config/mailrise.conf.example` to **`secrets/mailrise.conf`** (not `config/`) and fill in the `token` value with the ntfy publish-only token created in ntfy's own post-deploy step (see ntfy's stack-README). `config/` only ever holds the non-secret `.example` template — the real file with a real token belongs in `secrets/`, matching every other container's convention.

## Point PBS and PVE at it

In both PBS's and PVE's notification settings (Datacenter → Notifications in the PVE/PBS web UI), change the SMTP target to this VM's LAN IP and `${MAILRISE_SMTP_PORT}` (default `8025`), no auth, no TLS — mailrise accepts anything arriving on that port and re-emits it as an ntfy push per `mailrise.conf`'s routing rules (matched by the recipient address, e.g. `pbs-backups@mailrise.local` → the `backups` ntfy topic).

**Burn-in, don't cut over instantly**: leave PBS/PVE's previous (broken, spam-filtered) SMTP config as a secondary/backup notification target for a couple of weeks after switching to mailrise, so a bug in this new path doesn't silently mean "no notifications at all" instead of "notifications in spam."
