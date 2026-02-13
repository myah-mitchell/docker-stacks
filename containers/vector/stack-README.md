# Initial Deployment Requirements
## Prerequisites for using vector

### Setting Up Syslog Collection [vector-host]

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

sudo ufw app update WebProxy
sudo ufw app list
sudo ufw allow WebProxy

# Create and Setup Requried Folders
## Create needed folders for vector

```bash
mkdir -p /opt/docker/volumes/$projectName/vector-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vector-*
```