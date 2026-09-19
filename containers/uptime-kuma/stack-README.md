# Initial Deployment Requirements
## Prerequisites for using uptime-kuma

# Create and Setup Required Folders
## Post-deploy

First visit to the web UI prompts for the admin account (no default credentials to change). Configure its own notification integration to point at `ntfy` (built-in ntfy notification type) so status-page state changes land in the same place as everything else. This is a complement to `blackbox-exporter`/`vmalert` (which do the actual metrics-driven alerting). Uptime Kuma is here purely for the simple, glanceable green/red status page.
