# Initial Deployment Requirements
## Prerequisites for using crowdsec

# Create and Setup Requried Folders
## Create needed folders for crowdsec

```bash
mkdir -p /opt/docker/volumes/$projectName/crowdsec-data
mkdir -p /opt/docker/volumes/$projectName/crowdsec-config
sudo chown 100000:100000 /opt/docker/volumes/$projectName/crowdsec-*
```