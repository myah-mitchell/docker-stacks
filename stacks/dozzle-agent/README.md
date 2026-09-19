# Dozzle Stack (Agent) Overview

This will start up a Dozzle stack with Dozzle running in agent mode collecting logs. This server will only need port 7007 inbound open for the Dozzle server to connect to this agent on. This compose file should only be ran once per server but can ran on as many servers as you would like.

# Create and Setup Required Folders
## Create Stack Folders

```bash
projectName="dozzle"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

## Open the firewall for dozzle

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
sudo ufw allow from <internal-subnet> to any port 7007 proto tcp comment 'Dozzle agent'
```
