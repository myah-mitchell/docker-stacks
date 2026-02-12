# <stackName> Overview
<information about the stack>

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

## Create needed folders for crowdsec

```bash
mkdir -p /opt/docker/volumes/$projectName/crowdsec-data
mkdir -p /opt/docker/volumes/$projectName/crowdsec-config
sudo chown 100000:100000 /opt/docker/volumes/$projectName/crowdsec-*
```
