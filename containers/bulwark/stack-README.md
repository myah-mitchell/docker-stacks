# Initial Deployment Requirements
## Prerequisites for using bulwark

An Authentik OAuth2 application for Bulwark to sign in through. Its client ID and secret go in the Komodo Secrets `MAIL_OIDC_CLIENT_ID` and `MAIL_OIDC_CLIENT_SECRET`, and a 96-character random `BULWARK_SESSION_SECRET_KEY` goes beside them.

# Create and Setup Required Folders
## Create needed folders for bulwark

```bash
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/settings
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/admin
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/admin-state
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/telemetry
sudo chown -R 101001:101001 /opt/docker/volumes/$projectName/bulwark-data
```

Bulwark runs as the image's own UID 1001, so its directories belong to host UID `101001` rather than `101000`.
