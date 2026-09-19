# Dozzle Stack (Server) Overview

This will start up a Dozzle stack with an instance of Dozzle running as a server to connect to instances of Dozzle running in agent mode. This will also start up a local Dozzle agent instance so you do not need to also start the Dozzle Agent stack on the same server as this. This server will need access to all other servers running Dozzle on port 7007. This compose file should only be ran once per server but can ran on as many servers as you would like as there is no interferance with multiple servers running.

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
