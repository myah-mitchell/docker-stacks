# VictoriaMetrics Control Stack (Server) Overview
This will start up a VictoriaMetrics server stack with VictoriaMetrics, VictoriaLogs, VictoriaTraces, Grafana, and many other services. This compose file should only be deployed to one server. It holds the backends only. The host's own metrics and logs come from system-agent, deployed beside it like on every other VM.

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

## Create needed folders for victoriametrics

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/victoriametrics/victoriametrics-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/volumes/$projectName/victoriametrics-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/victoriametrics-data
```

</details>

## Create needed folders for victorialogs

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/victoriametrics/victorialogs-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/volumes/$projectName/victorialogs-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/victorialogs-data
```

</details>

## Create needed folders for victoriatraces

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/victoriametrics/victoriatraces-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/volumes/$projectName/victoriatraces-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/victoriatraces-data
```

</details>

## Create needed folders for grafana

The host's NixOS configuration sets these up when the host is deployed.

| Folder | Owner | Mode |
| --- | --- | --- |
| `/opt/docker/volumes/victoriametrics/grafana-data` | `101000:101000` | Not set |

<details>
<summary>Manual steps, instead of nixos-sync.yml</summary>

```bash
projectName="victoriametrics"
mkdir -p /opt/docker/volumes/$projectName/grafana-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/grafana-data
```

</details>
