# Initial Deployment Requirements
## Prerequisites for using stalwart

A Stalwart Enterprise license for the domain, stored in a Komodo Secret named `STALWART_LICENSE_KEY`.

# Create and Setup Required Folders
## Create needed folders for stalwart

Stalwart runs as the image's own UID 2000, so its directories belong to host UID `102000` rather than `101000`.

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
