# Stacks

Every stack in `stacks/`, what it deploys, and where it runs. For the order hosts come up in, see [Fleet bootstrap](https://myah-mitchell.github.io/docs/fleet-bootstrap/). For what a stack is made of mechanically, see [Project layout](../scripts/project-layout.md).

A stack is a deployable composition of containers. Only its `compose.yaml` is hand-written, and `scripts/build.py` generates the rest.

The generated files are `komodo.env`, `.env`, `README.md`, and `setup.yaml`.

Each stack's own generated `README.md` carries the per-stack prerequisites and what the stack needs from its host: folders, seed files, and open ports. It is the authoritative source for those.

Every stack also has a reference page on the docs site, under [Stacks](https://myah-mitchell.github.io/docs/fleet-bootstrap/stacks/). Whether a host is built yet is tracked in one place, the [running order](https://myah-mitchell.github.io/docs/fleet-bootstrap/#running-order).

## One stack per host

These are the stacks that define what a specific VM is for.

| Stack | Deploys | Host |
| --- | --- | --- |
| komodo-server | komodo, ferretdb, postgres (DocumentDB), postgres-backup | km01 |
| semaphore-server | semaphore, postgres, postgres-backup, nix | ci01 |
| traefik-server | traefik-agent plus a password-protected redis every traefik-kop writes to | tf01 |
| authentik-server | authentik-server, authentik-worker, postgres, postgres-backup, redis, geoipupdate, socket-proxy | id01 |
| step-ca-server | step-ca | pk01 |
| traefik-dmz | traefik-agent plus redis (replicating from traefik-server) and cloudflared | bh01 |
| victoriametrics-server | victoriametrics, victorialogs, victoriatraces, vmauth, vmalert, grafana, alertmanager | ci01 |
| core-infra | ntfy, mailrise, postfix, mailpit, blackbox-exporter, uptime-kuma | ci01 |
| stalwart-server | stalwart, bulwark | mx01, optional |

traefik-dmz is the public edge. Only port 443 outbound to the internal Traefik hosts and 6379 outbound to traefik-server's Redis need to leave the DMZ.

core-infra is the odd one out in this table. It is not what ci01 is for, it is where the fleet's alerts and uptime checks land and its outgoing mail is relayed, and ci01 is simply the host with the rest of the observability stack on it already. See [Core infrastructure (ci01)](https://myah-mitchell.github.io/docs/fleet-bootstrap/hosts/ci01-core-infra/).

stalwart-server is optional. It gives the domain real mailboxes with accounts from Authentik, and nothing else in the fleet depends on it. See [Mail (mx01)](https://myah-mitchell.github.io/docs/fleet-bootstrap/hosts/mx01-mail/).

## One stack per VM

| Stack | Deploys | Runs on |
| --- | --- | --- |
| system-agent | vmagent, vlagent, vector, cadvisor, dozzle-agent, dockns, socket-proxy | Every VM |
| traefik-agent | traefik, error-pages, logrotate, traefik-kop, socket-proxy, socket-proxy-rw | Every VM that publishes something |
| traefik-bootstrap | traefik, error-pages, socket-proxy, socket-proxy-rw, logrotate | The same VMs, while they are in bootstrap mode |

Komodo requires every Stack name to be unique, so the Stack resource for any of these is named after the stack plus its host, such as `system-agent-ci01` or `traefik-bootstrap-id01`. The one-per-host stacks above keep their plain names. Container and network names are unaffected, because they come from `PROJECT_NAME` rather than the Stack name.

system-agent is what every VM runs: metrics, logs, container DNS, and a Dozzle agent. It carries no Traefik, so it can go on a host whether or not that host publishes anything, and its vector and vmagent pick up a local Traefik when there is one.

traefik-agent is the Traefik half, for the VMs that publish something. That VM's own Traefik terminates TLS and runs the `chain-authentik@file` auth chain for its services directly, without needing tf01. traefik-kop publishes a router into tf01's shared Redis only when a service also carries a `kop-public.traefik.*` label, so reaching the internet is a per-service opt-in rather than a per-VM setting. tf01 and bh01 get all of it through traefik-server and traefik-dmz instead, so they do not list traefik-agent separately.

system-agent needs the monitoring backends on ci01, and traefik-agent needs the auth chain (id01) and tf01's Redis, so neither can run before those exist. Until then a host is in bootstrap mode: ansible leaves both out and deploys traefik-bootstrap in traefik-agent's place. See [Bootstrap mode](https://myah-mitchell.github.io/docs/fleet-bootstrap/concepts/bootstrap-mode/). Do not run both Traefiks on one VM: they fight over ports 80, 443, and 8443.

A VM gets a stack by listing it under `docker_stacks` in the inventory. See [How a host is built](https://myah-mitchell.github.io/docs/fleet-bootstrap/concepts/how-a-host-is-built/).

## Composition layers

These exist so the stacks above can build on each other through Compose `include`. Each one is a working stack on its own, but in this plan they are consumed rather than deployed directly.

| Stack | Deploys | Included by |
| --- | --- | --- |
| traefik-basic | traefik, error-pages, socket-proxy, socket-proxy-rw, logrotate | traefik-agent |
| traefik-agent | traefik-basic plus traefik-kop | traefik-server, traefik-dmz |

The chain runs traefik-basic to traefik-agent to traefik-server or traefik-dmz, each adding one layer. traefik-agent is the only one of the three that is also deployed on its own. traefik-bootstrap is deliberately outside that chain. It runs the same Traefik service as the rest, under a second name that changes only the TLS options, the cert resolver, and the auth chain, so there is no second copy of the argument list to keep in step.

victoriametrics-agent and dozzle-agent are stacks of their own that nothing includes and no host lists. system-agent supersedes both for the per-VM role. It bundles the same agents plus dockns, and publishes the same host ports, so a host runs system-agent or one of those two, never both.

## No host assigned yet

| Stack | Deploys | Note |
| --- | --- | --- |
| dozzle-server | dozzle-server | Connects to every VM's dozzle-agent on port 7007, its own host's included. Likely lands on ci01, not decided |

## Cut from the plan

These stack folders still exist but nothing in the plan deploys them. They are kept rather than deleted because the container definitions still work.

### crowdsec-server and crowdsec-agent

Cloudflare handles edge WAF, DDoS, and rate limiting for the one public hostname, and UniFi CyberSecure covers network-level IDS and IPS. Targeted vmalert rules against existing VictoriaMetrics data cover the rest without adding an always-on service.

### technitium-server

dockns drives UniFi's own DNS directly through its `unifi` provider. Running Technitium alongside it gave hosts two upstream resolvers that disagreed.

## Scaffolding

`template` is the starting point for a new stack. It defines the four standard networks (proxy, frontend, backend, and socket_proxy) and no services.
