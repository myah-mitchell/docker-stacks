# Komodo Stack (Server) Overview

This will start up a Komodo stack with an instance of Komodo running as a server to connect to instances of Komodo running on hosts. This should only be ran once in an environment.

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

## Create needed folders for ferretdb

```bash
mkdir -p /opt/docker/volumes/$projectName/ferretdb-data
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/ferretdb-*
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*
```

## Create needed folders for komodo

```bash
mkdir -p /opt/docker/volumes/$projectName/komodo-backups
mkdir -p /opt/docker/volumes/$projectName/komodo-sync
mkdir -p /opt/docker/volumes/$projectName/komodo-cache
sudo chown 101000:101000 /opt/docker/volumes/$projectName/komodo-*
```
