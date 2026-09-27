# VictoriaMetrics Control Stack (Server) Overview
This will start up a VictoriaMetrics server stack with VictoriaMetrics, VictoriaLogs, VictoriaTraces, Grafana, and many other services. This compose file should only be deployed to one server. It holds the backends only. The host's own metrics and logs come from system-agent, deployed beside it like on every other VM.

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

## Create needed folders for victoriametrics

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/victoriametrics-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/victoriametrics-data
```

## Create needed folders for victorialogs

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/victorialogs-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/victorialogs-data
```

## Create needed folders for victoriatraces

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/victoriatraces-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/victoriatraces-data
```

## Create needed folders for grafana

Generated from `setup.yaml`, which the ansible `stacks` role also applies.

```bash
mkdir -p /opt/docker/volumes/$projectName/grafana-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/grafana-data
```
