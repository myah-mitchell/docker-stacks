# VictoriaMetrics Agent Stack (Agent) Overview
This will start up a Vector, VMAgent, VLAgent and some other services. This stack will collect, buffer and then forward onto the server stack. This stack should only be deployed once per server.

# Initial Deployment Requirements
## Prerequisites for using vmagent

### Setting Up Node Exporter

Node Exporter reports the host's own CPU, memory, disk and network. It runs on
the host rather than in a container, and the host's NixOS configuration installs
and configures it. Nothing here has to be done by hand.

It serves port 9100 over TLS, behind a user name and a password. vmagent mounts
two files from `/etc/node-exporter/`:

| File | What it is |
| --- | --- |
| `node_exporter.crt` | The self-signed certificate Node Exporter serves. vmagent mounts it as its CA and skips verification, since it is self-signed. |
| `scrape-password` | The password, owned by host ID `101000`. That is the ID Docker's user namespace maps this stack's vmagent onto. |

Every host has a different password, made on that host the first time it boots
and kept on its persistent disk. A host's vmagent only ever scrapes that same
host's Node Exporter, so the password never has to match between hosts, and no
copy of it exists outside the host it belongs to. That is why
`NODE_EXPORTER_USER` is the only Node Exporter value in this stack's
environment: there is no password for Komodo to hold.

The host's NixOS configuration also opens port 9100, so vmagent can reach it.

# Create and Setup Required Folders

What this stack needs from its host: folders, seed files, and open ports. It is generated from the `setup.yaml` of each container in the stack.

A host gets it from its NixOS configuration. The ansible playbook `nixos-sync.yml` writes this stack's `setup.yaml` into the host's file under `nixos/hosts/` in fleet-private, and deploying the host applies it.

Owners are host IDs. Docker runs with userns-remap, so a container's UID 1000 is host UID 101000. An internal port is open to `docker_stacks_internal_subnet` from the inventory.

The manual steps cover folders and seed files only. The firewall of a NixOS host changes only through its configuration.

## Create Stack Folders

The host's NixOS configuration creates one folder for the stack's logs and one for its volumes.

| Folder | Holds |
| --- | --- |
| `/opt/docker/logs/victoriametrics` | Logs the stack's containers write to files |
| `/opt/docker/volumes/victoriametrics` | Every other folder in this section |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

</details>

## Create needed folders for vlagent

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/victoriametrics/vlagent-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/volumes/$projectName/vlagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vlagent-data
```

</details>

## Create needed folders for vmagent

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/victoriametrics/vmagent-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vmagent-data
```

</details>

## Create needed folders for vector

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/victoriametrics/vector-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vector-data
```

</details>

## Open the firewall for vector

The host's NixOS configuration opens these when the host is deployed.

| Port | Protocol | Allowed from | Used for |
| --- | --- | --- | --- |
| `5140` | tcp | The internal subnet | Vector syslog |
| `5140` | udp | The internal subnet | Vector syslog |
