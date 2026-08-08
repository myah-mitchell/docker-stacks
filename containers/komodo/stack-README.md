# Initial Deployment Requirements
## Prerequisites for using komodo

# Create and Setup Required Folders
## Create needed folders for komodo

```bash
mkdir -p /opt/docker/volumes/$projectName/komodo-backups
mkdir -p /opt/docker/volumes/$projectName/komodo-sync
mkdir -p /opt/docker/volumes/$projectName/komodo-cache
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-*
```