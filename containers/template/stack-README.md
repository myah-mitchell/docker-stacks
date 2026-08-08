# Initial Deployment Requirements
## Prerequisites for using imageName

# Create and Setup Required Folders
## Create needed folders for imageName

```bash
mkdir -p /opt/docker/logs/$projectName/imageName
sudo chown 101000:101000 /opt/docker/logs/$projectName/imageName

mkdir -p /opt/docker/volumes/$projectName/imageName-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/imageName-*
```