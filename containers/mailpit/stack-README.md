# Initial Deployment Requirements
## Prerequisites for using mailpit

# Create and Setup Required Folders
## Create needed folders for mailpit

```bash
mkdir -p /opt/docker/volumes/$projectName/mailpit-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/mailpit-data
```

## Reading the copies

Browse to `https://${MAILPIT_SERVICE_NAME}.${SUB_DOMAIN_NAME}${DOMAIN_NAME}`. The UI is behind `chain-authentik@file` by default, because the copies include password reset and sign-in links.

Mailpit keeps the newest `MAILPIT_MAX_MESSAGES` copies, and nothing older than `MAILPIT_MAX_AGE`. A copy showing here proves the sending service reached Postfix. It does not prove the relay accepted the original, so check Postfix's log for that:

```bash
docker logs ${projectName}-postfix 2>&1 | grep 'status='
```

`status=sent` from the relay is delivered onward. `status=deferred` is queued for retry, and the reason follows in brackets.
