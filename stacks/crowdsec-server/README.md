### Crowdsec Stack (Server) Overview

This will start up a Crowdsec stack with an instance of Crowdsec running as a server and also the agent. This will only need to run on one server per environment.

# Helpful Commands
## Crowdsec LAPI Server Commands

To Enroll the Server run the following:

```bash
cscli console enroll <EnrollToken>
```

To generate an API Key for a Traefik Bouncer run:

```bash
docker exec -t crowdsec cscli bouncers add traefik-bouncer-<hostname>
```

To generate a maching login for a Crowsec Satellite run:

```bash
cscli machines add <hostname> --auto -f /tmp/crowdsec.yaml
cat /tmp/crowdsec.yaml
rm /tmp/crowdsec.yaml
```

# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/crowdsec` | Logs the stack's containers write to files |
| `/opt/docker/volumes/crowdsec` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="crowdsec"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for crowdsec

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/crowdsec/crowdsec-data` | `100000:100000` | Not set |
| `/opt/docker/volumes/crowdsec/crowdsec-config` | `100000:100000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="crowdsec"
mkdir -p /opt/docker/volumes/$projectName/crowdsec-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/crowdsec-data
mkdir -p /opt/docker/volumes/$projectName/crowdsec-config
sudo chown 100000:100000 /opt/docker/volumes/$projectName/crowdsec-config
```

</details>
