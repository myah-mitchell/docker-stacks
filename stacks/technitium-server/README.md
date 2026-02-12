# Technitium Stack (Server) Overview

The `stacks\technitium-server\compose.yaml` will start up a Technitium stack with an instance of Technitium running as a server to connect to other instances of Technitium running on other servers. There is no server/agent mode here, all instances run the same config. This can only be run once per server.

# Create and Setup Requried Folders
## Create Stack Folders

```bash
projectName="projectName"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

## Create needed folders for technitium

```bash
mkdir -p /opt/docker/volumes/$projectName/technitium-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/technitium-*
```
