# VictoriaMetrics Agent Stack (Agent) Overview
This will start up a Vector, VMAgent, VLAgent and some other services. This stack will collect, buffer and then forward onto the server stack. This stack should only be deployed once per server.

# Initial Deployment Requirements
## Prerequisites for using vmagent

### Setting Up Node Exporter

Node Exporter reports the host's own CPU, memory, disk and network. It runs on
the host rather than in a container, and the `monitoring` role in the ansible
repo installs and configures it. Run that role against the host before deploying
this stack. Nothing here has to be done by hand.

The role leaves four files in `/etc/node-exporter/` that matter to this stack:

| File | What it is |
| --- | --- |
| `node_exporter.crt` | The self-signed certificate Node Exporter serves on port 9100. vmagent mounts it as its CA and skips verification, since it is self-signed. |
| `config.yml` | Node Exporter's own TLS and basic-auth config, holding the bcrypt hash of this host's password. |
| `password` | The plaintext, readable only by the `node_exporter` user. The role reads it back on later runs so the password stays the same. |
| `scrape-password` | A second copy of the plaintext, owned by the host-side UID that Docker's user namespace maps this stack's vmagent onto. This is the one vmagent mounts. |

Every host gets a different password, generated on that host on the role's first
run. A host's vmagent only ever scrapes that same host's Node Exporter, so the
password never has to match between hosts, and no copy of it exists outside the
host it belongs to. That is why `NODE_EXPORTER_USER` is the only Node Exporter
value in this stack's environment: there is no password for Komodo to hold.

To rotate one host's password, set `node_exporter_password` for that host and run
the role again. To rotate every host's, delete `/etc/node-exporter/password` and
`/etc/node-exporter/password.bcrypt` first.

The role also opens port 9100 in UFW as the `Node-Exporter` application, so
vmagent can reach it.

## Prerequisites for using vector

### Setting Up Syslog Collection

#### Open Port in UFW for Syslog

We need to create a UFW application so that we can let vector collect syslog

```bash
sudo vi /etc/ufw/applications.d/vector-syslog
```

```bash
[Vector-Syslog]
title=Vector Syslog
description=Allows incoming traffic for vector syslog on port 5140
ports=5140/udp|5140/tcp
```

We then can enable this new application

```bash
sudo ufw app update Vector-Syslog
sudo ufw app list
sudo ufw allow Vector-Syslog
```

# Create and Setup Required Folders
## Create Stack Folders

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

## Create needed folders for vlagent

```bash
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vlagent-*
```

## Create needed folders for vmagent

```bash
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vmagent-*
```

## Create needed folders for vector

```bash
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vector-*
```

## Create needed folders for cadvisor

```bash
mkdir -p /opt/docker/volumes/$projectName/cadvisor-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/cadvisor-*
```
