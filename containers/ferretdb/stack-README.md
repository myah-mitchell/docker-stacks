# Initial Deployment Requirements
## Prerequisites for using ferretdb

# Create and Setup Requried Folders
## Create needed folders for ferretdb

```bash
mkdir -p /opt/docker/volumes/$projectName/ferretdb-data
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/ferretdb-*
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*
```