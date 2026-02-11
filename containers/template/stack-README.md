# Initial Deployment Requirements
### Create needed folders for imageName

```bash
projectName="<projectName>"
mkdir -p /opt/docker/logs/$projectName/imageName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName
sudo chown 101000:101000 /opt/docker/logs/$projectName/*

mkdir -p /opt/docker/volumes/$projectName/imageName/certs
mkdir -p /opt/docker/volumes/$projectName/imageName/plugins
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
sudo chown 101000:101000 /opt/docker/volumes/$projectName/*
```