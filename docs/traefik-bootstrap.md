# traefik-bootstrap

traefik-bootstrap is a temporary, per-VM Traefik for the window before pk01 and id01 exist. Deploy it on a VM, use it, and tear it down once that VM's real [traefik-agent](traefik-agent-setup.md) stack is ready. It is not meant to be long-lived.

Read [Conventions](conventions.md) first. This page assumes its naming and secrets rules.

## Why it exists

Most stacks in this plan are reachable only through a real Traefik, gated behind `chain-authentik@file` for forward-auth and with TLS issued by step-ca. pk01 runs step-ca and id01 runs Authentik, and until both exist neither half works.

traefik-bootstrap is a real Traefik on the real `proxy` network, serving real hostnames, with two substitutions:

| Real stack | Bootstrap stack |
| --- | --- |
| ACME or step-ca cert resolver | Traefik's own auto-generated self-signed certificate |
| `chain-authentik@file` | `chain-no-auth@file`, which is rate-limit, secure-headers, and compress with no Authentik dependency |

Its `compose.yaml` runs the same Traefik service as every other stack, with no `command` or `labels` override of its own. Both substitutions come from three variables:

| Variable | Here | Everywhere else |
| --- | --- | --- |
| `TRAEFIK_TLS_OPTIONS` | `tls-opts-selfsigned@file` | `tls-opts@file` |
| `TRAEFIK_CERT_RESOLVER` | blank | `letsencrypt` |
| `TRAEFIK_AUTH_CHAIN` | `chain-no-auth@file` | blank, which takes `chain-authentik@file` |

`build.py` fills those three from whichever `komodo.env` block matches the service variant a stack extends: `.traefik-bootstrap` here, `.traefik` everywhere else. The two variants are the same service under two names, so there is no second copy of the command list to keep in step.

The TLS options are the part that makes this stack work at all. `tls-opts@file` sets `sniStrict: true` and rejects any handshake whose SNI has no matching real certificate. This stack has no resolver, so its self-signed default never matches the hostname being asked for, and `sniStrict` would refuse every request. `tls-opts-selfsigned@file` is the same options with `sniStrict` off.

A blank `TRAEFIK_CERT_RESOLVER` reaches Traefik as an empty resolver name on the dashboard entrypoint and on the default certificate store. An empty name matches no resolver, so neither ever asks for a certificate and both fall back to the self-signed one. The `letsencrypt` resolver is still defined, because Traefik accepts a resolver it never uses as long as it has a storage location, and nothing here points at it.

Every other stack picks up its auth chain from `${TRAEFIK_AUTH_CHAIN:-chain-authentik@file}`, so deploying a stack behind this one means setting that single variable to `chain-no-auth@file`. Nothing else about that stack changes.

## When to deploy it

On any VM that needs to serve stacks through real Traefik routing before pk01 and id01 exist. ci01 is the first case, in [step 2 of ci01 bootstrap](ci01-bootstrap.md#2-deploy-traefik-bootstrap-onto-ci01).

## How to deploy it

The target VM must already be a connected Komodo Server resource, and must already have the `proxy` Docker network. Its own bootstrap doc covers both.

### 1. Create the runtime folders

The ansible `stacks` role creates these from `stacks/traefik-bootstrap/setup.yaml`, and opens step 2's ports in the same run.

On ci01, which deploys this stack before Semaphore exists, follow [Run the stacks role without Semaphore](provision-a-vm.md#run-the-stacks-role-without-semaphore) with `<stack>` set to `traefik-bootstrap`.

On any later host, you do not list this stack at all. Run the **provision-stacks** Template from [step 12](semaphore-setup.md#create-the-provision-stacks-template) with *Target* answered with that host and *Bootstrap* answered `true`. The role then prepares this stack in place of the ones it leaves out, on any host where something still needs a Traefik and nothing left provides one.

Check the result on the target VM:

```bash
sudo ls -ln /opt/docker/logs/traefik /opt/docker/volumes/traefik
```

The `traefik` log folder and both `traefik-` volume folders are owned by `101000`, and the log folder is mode `755`.

<details>
<summary>Manual steps, instead of ansible</summary>

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
sudo chmod 755 /opt/docker/logs/$projectName/traefik

mkdir -p /opt/docker/volumes/$projectName/traefik-certs
mkdir -p /opt/docker/volumes/$projectName/traefik-plugins
sudo chown 101000:101000 /opt/docker/volumes/$projectName/traefik-*
```

</details>

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

The `755` mode on the Traefik log directory matters. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so a directory left group-writable by the default umask makes the logrotate container exit 1 every five minutes and access.log grows forever.

### 2. Open the firewall

Step 1's run opened these. Confirm them on the target VM:

```bash
sudo ufw status
```

`80/tcp`, `443/tcp`, and `8443/tcp` show `ALLOW` from `Anywhere`.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
sudo ufw allow 80/tcp comment 'Traefik HTTP'
sudo ufw allow 443/tcp comment 'Traefik HTTPS'
sudo ufw allow 8443/tcp comment 'Traefik HTTPS (alt)'
sudo ufw status
```

</details>

Those three are the ports `containers/traefik/compose.yaml` publishes. Base provisioning enables UFW with a default-deny inbound policy and opens only what each host's own roles need. Traefik is not part of base provisioning, which is why the `stacks` role opens them.

### 3. Create the Stack resource

In Komodo's UI, go to *Resources > Stacks* and create a Stack named `traefik-bootstrap-<host>`, for example `traefik-bootstrap-ci01`. Set its target *Server* to that same VM.

Komodo requires every Stack name to be unique, and this stack runs on several VMs at once, so the host name goes on the end.

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/traefik-bootstrap` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### 4. Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/traefik-bootstrap/komodo.env` in this repo, copy its full contents, and paste them in.

Komodo's parser accepts the `KEY: value` lines this repo uses, as well as `KEY = value`, comments, and quoted values, so it pastes in unchanged.

Leave the separate *env_file_path* field at its default of `.env`. That is only where Komodo writes the resolved result on the target VM before running Compose.

Three keys need a real value:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | The VM's hostname, for example `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |

`PROJECT_NAME` drives every hostname and label in the stack, but it is already committed as `traefik` rather than left blank, so it needs no edit.

Leave the four hostname keys alone. `TRAEFIK_HOSTNAME` defaults to `traefik` and only matters if you want the dashboard under a different name. The other three are container hostnames with no reason to change.

Leave the `[[GLOBAL_...]]` references as pasted, with the two exceptions below. Komodo resolves them from the instance-wide Variables created in [step 14](komodo-bootstrap.md#14-create-komodos-global-variables) of the km01 runbook. Deploying before those exist fails with Compose trying to interpolate the literal string `[[GLOBAL_CPUS_LIMIT]]` into a numeric field. Create the Variables and click **Deploy** again.

### Keys to clear

Seven keys come across in the paste that this stack has no working use for. Clear each one to blank.

| Keys | Why they do nothing here |
| --- | --- |
| `CF_API_EMAIL`, `CF_DNS_API_TOKEN` | They reach the Traefik container, but there is no ACME resolver to use them |
| `AUTHENTIK_HOST` | Also reaches the container, but nothing here forwards auth to Authentik |
| `CROWDSEC_LAPI_KEY`, `CROWDSEC_LAPI_HOST` | The base Traefik service keeps its CrowdSec lines commented out |
| `TRAEFIK_EXTRA_COMMAND` | An escape hatch for one extra Traefik argument, and blank is the normal answer |
| `LE_EMAIL` | Only the ACME resolver reads it, and nothing here points at that resolver |

Leave `TRAEFIK_TLS_OPTIONS`, `TRAEFIK_CERT_RESOLVER`, and `TRAEFIK_AUTH_CHAIN` exactly as pasted. They already carry this stack's values, including the deliberately blank resolver, and they are what make it a bootstrap Traefik rather than a real one.

The first three keys in the table are worth clearing rather than ignoring: they are all still passed into the container.

`AUTHENTIK_HOST` and `CROWDSEC_LAPI_HOST` are the two exceptions to leaving `[[GLOBAL_...]]` alone. They arrive as references that step 14 does not create, so clearing them is what keeps an unresolved `[[...]]` string out of the container's environment.

### 5. Deploy

Save the Stack resource, then click **Deploy**. Watch the deploy log.

Confirm all five services show running and healthy, either in Komodo's container view or with `docker compose ps` on the target VM:

```text
traefik
error-pages
socket-proxy
socket-proxy-rw
logrotate
```

> [!NOTE]
> Naming no cert resolver, by leaving `TRAEFIK_CERT_RESOLVER` blank, is expected to make Traefik fall back to its own self-signed certificate. That follows Traefik's documented behaviour, but this stack has not been run against a live Traefik yet. Check it first if the stack does not come up cleanly.

## Putting a stack behind it

Set that stack's `TRAEFIK_AUTH_CHAIN` to `chain-no-auth@file` in its own Komodo *Environment* text when you deploy it. The comment above that key in its `komodo.env` says the same thing.

Then browse to the stack's normal hostname over HTTPS, for example `https://semaphore.ci01.home.myah-mitchell.com`.

Your browser will warn about the certificate. That is expected: it is self-signed, not issued by a CA your browser trusts. Accept it and continue.

The hostname does not change when traefik-agent replaces this stack later. Only the certificate and the auth chain do.

## Tearing it down

Do this per VM, once that VM's traefik-agent stack is deployable for real. [traefik-agent](traefik-agent-setup.md) does it as its step 6, so follow that page rather than this section if you are deploying the replacement now.

Delete the VM's `traefik-bootstrap-<host>` Stack resource in Komodo, or `docker compose down` it directly on the VM. Then clear the `TRAEFIK_AUTH_CHAIN` override on every stack that was set to `chain-no-auth@file`, so each falls back to `chain-authentik@file` on its next deploy.

> [!WARNING]
> Do not run traefik-bootstrap and traefik-agent on the same VM at once. Both publish `:80`, `:443`, and `:8443` on the host and will fight over them.
