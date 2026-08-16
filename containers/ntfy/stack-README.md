# Initial Deployment Requirements
## Prerequisites for using ntfy

# Create and Setup Required Folders
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

A token for services that only ever publish (vmalert, mailrise, blackbox_exporter alerts, PBS/PVE via mailrise) — narrower than handing out your admin password:

```bash
docker exec -it $projectName-ntfy ntfy user add --role=user publisher
docker exec -it $projectName-ntfy ntfy access publisher 'alerts-*' write-only
docker exec -it $projectName-ntfy ntfy token add publisher
```

Use the resulting token as the `Authorization: Bearer <token>` header (or `ntfy://token@host/topic` Apprise-style URL) in Alertmanager's webhook config and `mailrise.conf`. Subscribe to the same `alerts-*` topics from the ntfy phone/desktop app using your own account.
