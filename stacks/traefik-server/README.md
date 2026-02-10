# Traefik Server Overview
<information about the stack>

# Initial Deployment Requirements
### Create needed folders for Traefik

```bash
mkdir -p /opt/docker/logs/$projectName/traefik
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$$$$$$$$$$projectName
sudo chown 101000:101000 /opt/docker/logs/$projectName/*

mkdir -p /opt/docker/volumes/$projectName/traefik/certs
mkdir -p /opt/docker/volumes/$projectName/traefik/plugins
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
sudo chown 101000:101000 /opt/docker/volumes/$projectName/*
```
