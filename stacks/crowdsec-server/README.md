### Crowdsec Stack (Server) Overview

This will start up a Crowdsec stack with an instance of Crowdsec running as a server and also the agent. This will only need to run on one server per environment.

# Helpful Commands
## Crowdsec LAPI Server Commands

To Enroll the Server run the following:

```
cscli console enroll <EnrollToken>
```

To generate an API Key for a Traefik Bouncer run:

```
docker exec -t crowdsec cscli bouncers add traefik-bouncer-<hostname>
```

To generate a maching login for a Crowsec Satellite run:

```
cscli machines add <hostname> --auto -f /tmp/crowdsec.yaml
cat /tmp/crowdsec.yaml
rm /tmp/crowdsec.yaml
```

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

## Create needed folders for postgres

```bash
mkdir -p /opt/docker/volumes/$projectName/postgres-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*
```
