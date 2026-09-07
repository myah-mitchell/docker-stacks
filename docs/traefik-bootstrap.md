# traefik-bootstrap

`stacks/traefik-bootstrap` is a temporary, per-VM Traefik for the window before `pk01` and `id01` exist. Deploy it on a VM, use it, and tear it down once that VM's real `system-agent` stack is ready. It is not meant to be long-lived.

## Why it exists

Most stacks in this plan are reachable only through a real Traefik, gated behind `chain-authentik@file` for forward-auth and with TLS issued by step-ca. `pk01` runs step-ca and `id01` runs Authentik, and until both exist neither half works.

The alternative was an SSH tunnel straight to a container IP, bypassing Traefik entirely. That is what the `ci01` runbook originally did to reach Semaphore, and it tests nothing about the routing that will actually be used later.

`traefik-bootstrap` is a real Traefik on the real `proxy` network, serving real hostnames, with two substitutions:

| Real stack | Bootstrap stack |
| --- | --- |
| ACME or step-ca cert resolver | Traefik's own auto-generated self-signed certificate |
| `chain-authentik@file` | `chain-no-auth@file`, which is rate-limit, secure-headers, and compress with no Authentik dependency |

Its `compose.yaml` overrides the base Traefik service's `command` wholesale rather than diffing it, because Compose `extends` replaces list keys instead of merging them. The only real removals from the base list are the ACME directives.

Every other stack picks up its auth chain from `${TRAEFIK_AUTH_CHAIN:-chain-authentik@file}`, so deploying a stack behind this one means setting that single variable to `chain-no-auth@file`. Nothing else about that stack changes.

## When to deploy it

On any VM that needs to serve stacks through real Traefik routing before `pk01` and `id01` exist. `ci01` is the first case, in [`ci01-bootstrap.md`](ci01-bootstrap.md).

## How to deploy it

The target VM must already be a connected Komodo Server resource, and must already have the `proxy` Docker network. Its own bootstrap doc covers both.

### 1. Create the runtime folders

On the target VM:

```bash
projectName="traefik"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/logs/$projectName/traefik
sudo chown 101000:101000 /opt/docker/logs/$projectName/traefik

mkdir -p /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-*
```

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

### 2. Open the firewall

```bash
sudo ufw allow 80/tcp comment 'Traefik HTTP'
sudo ufw allow 443/tcp comment 'Traefik HTTPS'
sudo ufw allow 8443/tcp comment 'Traefik HTTPS (alt)'
sudo ufw status
```

Those three are the ports `containers/traefik/compose.yaml` publishes. `ansible`'s base provisioning enables UFW with a default-deny inbound policy and opens only what each host's own roles need. Traefik is not part of base provisioning, so nothing opens these for you.

### 3. Create the Stack resource

In Komodo's UI, go to *Resources > Stacks* and create a Stack named `traefik-bootstrap`. Set its target *Server* to the VM you are deploying onto.

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks`. No credential needed, the repo is public |
| *Branch* | `main` |
| *Run Directory* | `stacks/traefik-bootstrap` |
| *File Path* | `compose.yaml`, relative to the run directory |

### 4. Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/traefik-bootstrap/komodo.env` in this repo, copy its full contents, and paste them in.

Komodo's parser accepts the `KEY: value` lines this repo uses, as well as `KEY = value`, comments, and quoted values, so it pastes in unchanged.

Leave the separate *env_file_path* field at its default of `.env`. That is only where Komodo writes the resolved result on the target VM before running Compose.

Three keys need a real value:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | The VM's hostname, for example `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, for example `myah-mitchell.com` |

`PROJECT_NAME` drives every hostname and label in the stack, but it is already committed as `traefik` rather than left blank, so it needs no edit.

Leave the four hostname keys alone. `TRAEFIK_HOSTNAME` defaults to `traefik` and only matters if you want the dashboard under a different name. `ERROR_PAGES_HOSTNAME`, `SOCKET_PROXY_HOSTNAME`, and `LOGROTATE_HOSTNAME` are container hostnames with no reason to change.

Leave every `[[GLOBAL_...]]` reference as pasted. Komodo resolves them from the instance-wide Variables created in [step 14](komodo-bootstrap.md#14-create-komodos-global-variables) of the `km01` runbook. Deploying before those exist fails with Compose trying to interpolate the literal string `[[GLOBAL_CPUS_LIMIT]]` into a numeric field. Create the Variables and click **Deploy** again.

Six keys in the pasted text are unused by this stack's `compose.yaml`: `CF_API_EMAIL`, `CF_DNS_API_TOKEN`, `CROWDSEC_LAPI_KEY`, `CROWDSEC_LAPI_HOST`, `AUTHENTIK_HOST`, and `TRAEFIK_EXTRA_COMMAND`. There is no ACME resolver, no CrowdSec wiring, and no Authentik forward-auth here. Clear them to blank or leave them; either way they go nowhere.

### 5. Deploy

Save the Stack resource, then click **Deploy**. Watch the deploy log.

Confirm `traefik`, `error-pages`, `socket-proxy`, `socket-proxy-rw`, and `logrotate` all show running and healthy, either in Komodo's container view or with `docker compose ps` on the target VM.

> [!NOTE]
> Omitting the cert-resolver directives entirely, rather than setting them blank, is expected to make Traefik fall back to its own self-signed certificate. That follows Traefik's documented behaviour but has never been run: no Docker daemon existed anywhere this stack was written. Check it first if the stack does not come up cleanly.

## Putting a stack behind it

Set that stack's `TRAEFIK_AUTH_CHAIN` to `chain-no-auth@file` in its own Komodo *Environment* text when you deploy it. The comment above that key in its `komodo.env` says the same thing.

Then browse to the stack's normal hostname over HTTPS, for example `https://semaphore.ci01.home.myah-mitchell.com`.

Your browser will warn about the certificate. That is expected: it is self-signed, not issued by a CA your browser trusts. Accept it and continue.

This is real routing through real Traefik, at the hostname the stack will keep using once the real setup lands.

## Tearing it down

Do this per VM, once that VM's `system-agent` stack is deployable for real.

Delete the `traefik-bootstrap` Stack resource in Komodo, or `docker compose down` it directly on the VM. Then clear the `TRAEFIK_AUTH_CHAIN` override on every stack that was set to `chain-no-auth@file`, so each falls back to `chain-authentik@file` on its next deploy.

> [!WARNING]
> Do not run `traefik-bootstrap` and `system-agent` on the same VM at once. Both publish `:80`, `:443`, and `:8443` on the host and will fight over them.
