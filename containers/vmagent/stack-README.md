# Initial Deployment Requirements
## Prerequisites for using vmagent

### Setting Up Node Exporter [vmagent-host, vmagent-system]

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
