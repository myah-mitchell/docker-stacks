# Initial Deployment Requirements
## Prerequisites for using crowdsec

# Helpful Commands
## Crowdsec LAPI Server Commands [crowdsec-server]

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

# Create and Setup Required Folders
## Create needed folders for crowdsec

```bash
mkdir -p /opt/docker/volumes/$projectName/crowdsec-data
mkdir -p /opt/docker/volumes/$projectName/crowdsec-config
sudo chown 100000:100000 /opt/docker/volumes/$projectName/crowdsec-*
```