# Initial Deployment Requirements
## Prerequisites for using vmagent

### Setting Up Node Exporter [vmagent-host, vmagent-system]

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
