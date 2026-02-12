# Initial Deployment Requirements
## Prerequisites for using authentik

# Create and Setup Requried Folders
## Create needed folders for authentik

```bash
mkdir -p /opt/docker/volumes/$projectName/authentik-media
mkdir -p /opt/docker/volumes/$projectName/authentik-template
mkdir -p /opt/docker/volumes/$projectName/authentik-certs
sudo chown 101000:101000 /opt/docker/volumes/$projectName/authentik-*
```