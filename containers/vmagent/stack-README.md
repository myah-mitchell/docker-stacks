# Initial Deployment Requirements
## Prerequisites for using vmagent

### Setting Up Node Exporter

Node Exporter is expected to be installed by the Agent stack and is used to collect metrics off of the host.

These steps are a combination of the guides from the following two sites:
* [Setting Up Node Exporter - Techdox Docs](https://docs.techdox.nz/node-exporter/)
* [Securing Node Exporter Metrics - DEV Community](https://dev.to/cod3mason/securing-node-exporter-metrics-2ome)

#### Download Node Exporter

Begin by downloading Node Exporter using the wget command:

```bash
cd /tmp
wget https://github.com/prometheus/node_exporter/releases/download/v1.10.2/node_exporter-1.10.2.linux-amd64.tar.gz
```

Note: Ensure you are using the latest version of Node Exporter and the correct architecture build for your server. The provided link is for amd64. For the latest releases, check here - [Prometheus Node Exporter Releases](https://github.com/prometheus/node_exporter/releases)


#### Extract the Contents

After downloading, extract the contents with the following command:

```bash
tar xvf node_exporter-*.linux-amd64.tar.gz
```

#### Move the Node Exporter Binary

Move the node_exporter binary to /usr/local/bin:

```bash
sudo cp node_exporter-*.linux-amd64/node_exporter /usr/local/bin
```

Then, clean up by removing the downloaded tar file and its directory:

```bash
rm -rf ./node_exporter-*.linux-amd64*
```

#### Create Certificate

Generate a new self-signed certificate (replace "MyState", "MyCity", "MyOrg", and "ServerFQDN" with real data):

```bash
sudo mkdir /etc/node-exporter
sudo openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -keyout /etc/node-exporter/node_exporter.key -out /etc/node-exporter/node_exporter.crt -subj "/C=US/ST=MyState/L=MyCity/O=MyOrg/CN=node-exporter" -addext "subjectAltName = DNS:ServerFQDN"
```

#### Create Authentication Hash

Now generate node-exporter password creator by creating `/etc/node-exporter/gen-pass.py`

```python
#!/usr/bin/python3

import getpass
import bcrypt

password = getpass.getpass("password: ")
hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
print(hashed_password.decode())
```

And now running the script to hash your node-exporter password:

```bash
python3 gen-pass.py
```

#### Setup and Configure `node-exporter`

Add certificates and authentication into `/etc/node-exporter/config.yml`

```yaml
tls_server_config:
  cert_file: /etc/node-exporter/node_exporter.crt
  key_file: /etc/node-exporter/node_exporter.key
basic_auth_users:
  node-exporter-user: <HASHED-PASSWD>
```

#### Set proper permissions

```bash
sudo chmod 775 /etc/node-exporter
sudo chmod 644 /etc/node-exporter/*
sudo chmod 400 /etc/node-exporter/node_exporter.key
```

#### Create a Node Exporter User

Create a dedicated user for running Node Exporter:

```bash
sudo useradd --no-create-home --shell /bin/false node_exporter
```

Assign ownership permissions of the node_exporter binary to this user:

```bash
sudo chown node_exporter:node_exporter -R /etc/node-exporter
```

#### Configure the Service

To ensure Node Exporter automatically starts on server reboot, configure the systemd service:

```bash
sudo vi /etc/systemd/system/node_exporter.service
```

Then, paste the following configuration:
```bash
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter --web.config.file=/etc/node-exporter/config.yml
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Save and exit the editor.

#### Enable and Start the Service

Reload the systemd daemon:

```bash
sudo systemctl daemon-reload
```

Enable the Node Exporter service:

```bash
sudo systemctl enable node_exporter
```

Start the service:

```bash
sudo systemctl start node_exporter
```

To confirm the service is running properly, check its status:

```bash
sudo systemctl status node_exporter.service
```

#### Open Port in UFW for Node-Exporter

We need to create a UFW application so that we can let vmagent scrape Node-Exporter

```bash
sudo vi /etc/ufw/applications.d/node-exporter
```

```bash
[Node-Exporter]
title=Node-Exporter
description=Allows incoming traffic for Node-Exporter on port 9100
ports=9100/tcp
```

We then can enable this new application

```bash
sudo ufw app update Node-Exporter
sudo ufw app list
sudo ufw allow Node-Exporter
```

sudo ufw app update WebProxy
sudo ufw app list
sudo ufw allow WebProxy

# Create and Setup Requried Folders
## Create needed folders for vmagent

```bash
mkdir -p /opt/docker/volumes/$projectName/vmagent-data
sudo chown 101000:101000 /opt/docker/volumes/$projectName/vmagent-*
```