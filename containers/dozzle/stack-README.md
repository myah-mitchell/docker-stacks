# Initial Deployment Requirements
## Prerequisites for using dozzle

# Create and Setup Requried Folders
## Create needed folders for dozzle

```bash
mkdir -p /opt/docker/logs/$projectName/dozzle
sudo chown 101000:101000 /opt/docker/logs/$projectName/dozzle

mkdir -p /opt/docker/volumes/$projectName/dozzle-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/dozzle-*
```