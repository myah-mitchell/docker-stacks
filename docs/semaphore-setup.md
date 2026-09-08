# Deploying Semaphore and wiring it to ansible

Semaphore is the first stack on ci01. This doc takes it from an empty host to a Template that runs against the fleet: runtime folders, the Komodo Stack resource, then a Project, an SSH credential, the ansible repo, a real inventory, and the private variables.

A Semaphore that is up but unwired is worth nothing, so there is no useful place to stop partway.

This is the point of building ci01 before anything else. Until Semaphore can reach the fleet, every shared secret in ansible has to be fixed by hand, host by host, over SSH.

## Contents

- [The problem this solves](#the-problem-this-solves)
- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Create the runtime folders](#1-create-the-runtime-folders)
- [2. Generate Semaphore's three encryption keys](#2-generate-semaphores-three-encryption-keys)
- [3. Create the Stack resource for semaphore-server](#3-create-the-stack-resource-for-semaphore-server)
- [4. Verify](#4-verify)
- [5. First access](#5-first-access)
- [6. Create the bootstrap SSH key](#6-create-the-bootstrap-ssh-key)
- [7. Create the Project](#7-create-the-project)
- [8. Add the SSH key to the Key Store](#8-add-the-ssh-key-to-the-key-store)
- [9. Add the ansible repository](#9-add-the-ansible-repository)
- [10. Create the inventory](#10-create-the-inventory)
- [11. Create the ansible-private Variable Group](#11-create-the-ansible-private-variable-group)
- [12. Create the Template](#12-create-the-template)
- [13. Fix existing hosts before running](#13-fix-existing-hosts-before-running)
- [14. Replace this key once step-ca is live](#14-replace-this-key-once-step-ca-is-live)
- [What's next](#whats-next)

## The problem this solves

The ansible repo ships `node_exporter_password: "CHANGEME"` in the monitoring role's defaults.

That password is the HTTP basic-auth credential guarding each host's node_exporter metrics endpoint. `roles/monitoring/tasks/node-exporter.yml` bcrypt-hashes it into `/etc/node-exporter/config.yml` as the password for the user `node-exporter-user`, alongside a self-signed TLS cert. Prometheus later scrapes each host with those credentials.

`CHANGEME` is a placeholder committed to a public repo. Every host provisioned so far is running with it. It has to become a real value, everywhere, and stay that way for every host built afterwards.

The real value belongs in ansible-private's `group_vars/all/private.yml`, which is where all real values live. But committing it there only fixes hosts provisioned later. Existing hosts need a re-run, and that is what Semaphore is for.

## Prerequisites

- ci01 is provisioned and shows connected and healthy in Komodo, through step 2 of [ci01 bootstrap](ci01-bootstrap.md). Step 2 in particular: without traefik-bootstrap there is no way to reach Semaphore's UI once it deploys.
- km01's `[[GLOBAL_...]]` Variables exist, from step 14 of [km01 bootstrap](komodo-bootstrap.md). Step 3 below fails without them.
- You have ansible-private checked out somewhere you can commit and push from.
- You know the four identity values the fleet was provisioned with, listed under [Placeholders](#placeholders).

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<km-ip>` | km01's address, from its own runbook |
| `<ci-ip>` | ci01's address, from its own runbook |
| `<short_name>` | Fleet identity value, the organisation short name |
| `<abbr_name>` | Fleet identity value, its abbreviation |
| `<location_abbr>` | Fleet identity value, the site letter |
| `<domain_name>` | Fleet identity value, the real domain |
| `<same>` | The value that host was already provisioned with, recovered rather than guessed |

## 1. Create the runtime folders

On ci01, as the user Periphery runs as:

```bash
projectName="semaphore"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/semaphore-data
mkdir -p /opt/docker/volumes/$projectName/semaphore-config
mkdir -p /opt/docker/volumes/$projectName/semaphore-tmp
sudo chown 101000:101000 /opt/docker/volumes/$projectName/semaphore-*

mkdir -p /opt/docker/volumes/$projectName/postgres-data
mkdir -p /opt/docker/volumes/$projectName/postgres-backup-data
sudo chown 100000:100000 /opt/docker/volumes/$projectName/postgres-*
```

See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000) if those owners look arbitrary.

Unlike km01, you do not clone docker-stacks onto ci01 yourself. Periphery clones it into `/opt/docker/repos/` the first time you point a Stack resource at it. The folders above still have to exist with the right ownership before that first deploy, because neither Periphery nor Compose creates host bind-mount directories. These are Semaphore's. The other stack on ci01 has its own set, in step 3 of [VictoriaMetrics setup](victoriametrics-setup.md).

This list mirrors the [generated README for semaphore-server](../stacks/semaphore-server/README.md), which `scripts/build.py` rebuilds. That file wins if the two disagree.

## 2. Generate Semaphore's three encryption keys

Three of Semaphore's values are base64-encoded 32-byte keys rather than plain passwords, so `scripts/build.py` deliberately does not generate them. Generate them once, now:

```bash
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_HASH
head -c32 /dev/urandom | base64  # SEMAPHORE_COOKIE_ENCRYPTION
head -c32 /dev/urandom | base64  # SEMAPHORE_ACCESS_KEY_ENCRYPTION
```

> [!IMPORTANT]
> These three must stay stable across restarts. Rotating any of them invalidates every stored SSH key, every stored vault secret, and every active session.

They go into Komodo Secrets in step 2, not into any file in this repo.

## 3. Create the Stack resource for semaphore-server

In Komodo's UI, go to *Resources > Stacks* and create a new Stack named `semaphore-server`. Set its target *Server* to **ci01**, the resource created by [step 5 of Provisioning a VM](provision-a-vm.md#5-give-the-host-an-onboarding-key).

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/semaphore-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

The repo is public, so Komodo needs no credential to clone it.

### Paste the environment

*Environment* is a plain text editor with no option to point at a file. Open `stacks/semaphore-server/komodo.env` in this repo, copy its full contents, and paste them into that field.

Four keys in the pasted text need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `ci01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |
| `TRAEFIK_AUTH_CHAIN` | `chain-no-auth@file`, so it routes through traefik-bootstrap |

Authentik does not exist yet, so the real `chain-authentik@file` default has nothing behind it. Clear that override later, once id01 is live and system-agent has replaced traefik-bootstrap here.

Three more keys are blank and stay that way: `POSTGRES_BACKUP_DB`, `POSTGRES_BACKUP_USER`, and `POSTGRES_BACKUP_PASSWORD`. This stack's `compose.yaml` points all three at the same database, user, and password its own Postgres service already resolves.

Leave every `[[...]]` reference in the pasted text exactly as it is. Komodo resolves them at deploy time from its own Variables and Secrets, which is the next step.

### Create the nine Semaphore Secrets

The `[[GLOBAL_...]]` references already resolve, from km01's step 14. The `[[SEMAPHORE_...]]` ones do not exist yet.

Go to *Settings > Secrets* on km01 and create all nine by name. These are real credentials, so Secrets rather than Variables: Komodo resolves both identically, but Secrets stay masked in the UI.

| Secret | Value |
| --- | --- |
| `SEMAPHORE_ADMIN_USER` | Your choice |
| `SEMAPHORE_ADMIN_NAME` | Your choice |
| `SEMAPHORE_ADMIN_EMAIL` | Your choice |
| `SEMAPHORE_ADMIN_PASSWORD` | Your choice, alphanumeric only |
| `SEMAPHORE_COOKIE_HASH` | First value from step 1 |
| `SEMAPHORE_COOKIE_ENCRYPTION` | Second value from step 1 |
| `SEMAPHORE_ACCESS_KEY_ENCRYPTION` | Third value from step 1 |
| `SEMAPHORE_POSTGRES_USER` | Your choice |
| `SEMAPHORE_POSTGRES_PASSWORD` | Your choice, alphanumeric only |

The last two feed the `POSTGRES_USER` and `POSTGRES_PASSWORD` lines in the pasted text. Do not edit those two lines themselves.

The alphanumeric-only rule matters here for the same reason it does everywhere else. See [Conventions](conventions.md#alphanumeric-only).

Deploying before all nine exist fails the same way a missing `GLOBAL_*` does, with Compose trying to interpolate the literal string `[[SEMAPHORE_ADMIN_PASSWORD]]` into the container's environment. Create the Secrets and click **Deploy** again.

### Deploy

Save the Stack resource, then click **Deploy**. Watch the deploy log. Komodo clones the repo onto ci01, reads the compose file, and runs the equivalent of `docker compose up -d` through Periphery.

## 4. Verify

Confirm all three services show running and healthy, in Komodo's container view for the resource:

```text
semaphore
postgres
postgres-backup
```

To check from the host instead, SSH to ci01 and run `docker compose ps` in the stack's own directory under `/opt/docker/repos/`, where Periphery cloned it.

## 5. First access

Browse to `https://semaphore.ci01.home.myah-mitchell.com`, substituting whatever `SUB_DOMAIN_NAME` and `DOMAIN_NAME` you actually set. This is real Traefik routing, through the traefik-bootstrap deployed in [step 2 of the ci01 runbook](ci01-bootstrap.md#2-deploy-traefik-bootstrap-onto-ci01).

Your browser will warn about the certificate. That is expected: it is self-signed, not issued by a CA your browser trusts. Accept it and continue.

Log in with the `SEMAPHORE_ADMIN_USER` and `SEMAPHORE_ADMIN_PASSWORD` you set in step 2.

If the page does not load at all, the likeliest causes are ci01's traefik-bootstrap not actually healthy, or `TRAEFIK_AUTH_CHAIN` not overridden in step 2. See [Traefik bootstrap](traefik-bootstrap.md).

## 6. Create the bootstrap SSH key

Semaphore reaches every host as the `ansible` service account. The users role creates it with `NOPASSWD: ALL` sudo and an `authorized_keys` file built from `ansible_ssh_public_keys`.

Generate the keypair:

```bash
ssh-keygen -t ed25519 -C "semaphore-bootstrap" -f ./semaphore-bootstrap -N ""
```

Add the public half, `semaphore-bootstrap.pub`, to ansible-private's `group_vars/all/private.yml` under `ansible_ssh_public_keys`. That is a list, so append rather than replace. Commit and push.

Hosts provisioned after this point pick the key up automatically on first boot. Hosts that already exist do not, and Semaphore cannot fix that yet because it has no way in. Break the loop by hand, once per existing host, over SSH:

```bash
cd /tmp/ansible
ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' \
  --tags users
```

Use the same argument-recovery trick from [Provisioning a VM](provision-a-vm.md#recover-the-original-provisioning-arguments) if you do not know the four values for that host.

If `/tmp/ansible` is gone on a host, re-clone it and re-apply the private overlay first, the same way [step 5 of Provisioning a VM](provision-a-vm.md#5-give-the-host-an-onboarding-key) does.

Do this on km01 and ci01 at minimum. This static key is the same kind of bootstrap exception as Komodo's own manual first start, and [step 14](#14-replace-this-key-once-step-ca-is-live) replaces it later.

## 7. Create the Project

In Semaphore, create a Project named `fleet-provisioning`.

A Semaphore Project is the top-level container: Key Store, Repositories, Inventory, Variable Groups, and Templates all live inside one.

Do not name it `ansible`. Three things one level down inside it are already called `ansible`: the Repository in step 4, the service account it connects as, and the key credential in step 3.

## 8. Add the SSH key to the Key Store

Go to *Key Store* and click **New Key**.

| Field | Value |
| --- | --- |
| *Name* | `ansible-bootstrap-key` |
| *Type* | **SSH Key** |
| *Username* | `ansible` |
| *Private Key* | The contents of `semaphore-bootstrap`, the private half from step 1 |

The *Username* field here is what becomes `ansible_user` on every connection, so the inventory in step 5 does not need to set it.

## 9. Add the ansible repository

Go to *Repository* and click **New Repository**.

| Field | Value |
| --- | --- |
| *Name* | `ansible` |
| *URL* | `https://github.com/myah-mitchell/ansible` |
| *Branch* | `main` |
| *Access Key* | **None** |

The ansible repo is public, so no deploy key is needed, the same as the docker-stacks Stack resource in Komodo.

The dotfiles repo needs no Repository entry at all. Its own Ansible role clones it directly over plain HTTPS.

## 10. Create the inventory

This is the step with real work in it. The `hosts.yml` in both ansible and ansible-private is built for local runs. Its localhosts group holds three entries, ubuntu, ubuntu_docker, and wsl, and points all of them at 127.0.0.1, because every Docker VM so far was provisioned by cloud-init with `-c local`.

Semaphore connects over SSH from ci01. Pointed at `ubuntu_docker`, it would run against `127.0.0.1`, which is ci01 itself, every time. There is no group in the shipped inventory that names a real remote Docker host.

So the fleet's real Docker hosts have to be added as new entries. They do not exist yet in any file.

### Add a real host group to ansible-private

Open ansible-private's `hosts.yml` and add a group alongside the existing `pve_host_h` and `pbs_host_h` ones. The `_h` suffix is the `location_abbr`, so keep the same shape:

```yaml
docker_host_h:
  hosts:
    km01:
      ansible_host: <km-ip>
      serverHostname: "km01"
    ci01:
      ansible_host: <ci-ip>
      serverHostname: "ci01"

  vars:
    ntp_service: "chrony"

    FIREWALL: true
    firewall_service: "ufw"

    SWAP: true
    swap_size: "512M"
    swap_file: "/swapfile"

    AUTOUPDATE: true
    DOCKER: true
    KOMODO: true
    NODE_EXPORTER: true
```

Those uppercase flags are what gate each role in `provision.yml`. They are copied from the shipped `ubuntu_docker` entry, but hoisted into a group-level `vars:` block so every host added later inherits them instead of repeating the list.

`serverHostname` is optional. It falls back to the live `ansible_facts.hostname`, but pinning it documents intent and is what `komodo_connect_as` keys off.

Do not set `ansible_user` here. Step 3's Key Store entry supplies it.

Add each new VM to this group as you build it. tf01, id01, pk01, and the rest all belong here.

Commit and push ansible-private.

### Load it into Semaphore

Go to *Inventory* and click **New Inventory**.

| Field | Value |
| --- | --- |
| *Name* | `ansible-fleet` |
| *Type* | **Static YAML** |
| *User Credentials* | **ansible-bootstrap-key** from step 3 |

Paste the full contents of ansible-private's `hosts.yml`, including the group you just added. Semaphore stores inventory inline rather than cloning it from a repo, so this is a copy, not a reference.

> [!IMPORTANT]
> That copy does not update itself. Every time you add a host to ansible-private's `hosts.yml`, paste the new content into this Inventory too, or Semaphore keeps running against the old list.

## 11. Create the ansible-private Variable Group

Go to *Variable Groups*, click **New Group**, and name it `ansible-private`.

### Which of the four fields to use

The Variable Group has two tabs, *Variables* and *Secrets*, and each tab is split into two sections. Four boxes, and only two of them do anything useful here.

| Section | What it does | Use it? |
| --- | --- | --- |
| *Variables* tab, *Extra Variables* | Passed as `--extra-vars`. Real Ansible variables | Yes, for everything non-sensitive |
| *Secrets* tab, *Extra Variables* | Passed as `--extra-vars`, masked in the UI and logs | Yes, for credentials |
| *Variables* tab, *Environment Variables* | Set as OS environment variables on the `ansible-playbook` process | No |
| *Secrets* tab, *Environment Variables* | Same, masked | No |

Ansible never sees an OS environment variable as a Jinja variable unless a role explicitly calls `lookup('env', ...)`, and none of `provision.yml`'s roles do. Anything put in an *Environment Variables* section is silently ignored: the run does not error, it just keeps using the `CHANGEME` and blank defaults as though you set nothing.

Leave both *Environment Variables* sections empty.

### Secrets tab, Extra Variables

Add these as name and value pairs:

| Variable | Value |
| --- | --- |
| `ansible_private_repo_token` | The real GitHub PAT from `private.yml` |
| `node_exporter_password` | A real password, alphanumeric only. Pick it now |
| `server_password` | The fleet's admin password |

Commit that same real `node_exporter_password` to ansible-private's `group_vars/all/private.yml` as well. That key is not in the file yet, and adding it there is what overrides the monitoring role's `CHANGEME` default. Semaphore's copy fixes existing hosts; the committed one is what fresh hosts get on their very first cloud-init boot, before Semaphore ever touches them. Both need it.

### Variables tab, Extra Variables

Everything else from `private.yml` that is not a credential goes here: the two SSH public-key lists, the Komodo Core address and public key, the CA certificates, the SSH banner text, and the client account name. You do not have to transcribe them, since the command below builds the whole object for you.

Use the *JSON* toggle at the top of the field rather than entering every field as a table row. Generate the object from the file itself, dropping the keys that belong on the *Secrets* tab:

```bash
cd /path/to/ansible-private
yq -o=json 'del(.ansible_private_repo_token, .node_exporter_password, .server_password)' \
  group_vars/all/private.yml
```

Without `yq`, use Python:

```bash
python3 -c "
import yaml, json
data = yaml.safe_load(open('group_vars/all/private.yml'))
for k in ('ansible_private_repo_token', 'node_exporter_password', 'server_password'):
    data.pop(k, None)
print(json.dumps(data, indent=2))
"
```

Check the output before pasting. It should be one JSON object, and it must not contain `ansible_private_repo_token` or `node_exporter_password`. `server_password` is never in that file, so deleting it is only a guard in case someone adds it later.

Then add the four identity values, which are not in `private.yml` at all:

```json
{
  "short_name": "<short_name>",
  "abbr_name": "<abbr_name>",
  "location_abbr": "<location_abbr>",
  "domain_name": "<domain_name>"
}
```

Paste the merged object into the *JSON* editor, replacing the empty `{}`, then click **Save**.

### Why the identity values go here and not in the inventory

`provision.yml` declares six values as `vars_prompt`: target, server_password, and the four identity values. Semaphore runs non-interactively, so an unanswered prompt hangs the job.

An inventory or `group_vars` value does not suppress a `vars_prompt`. Ansible evaluates prompts at play parse time, before host selection and before inventory variables are in scope, so the prompt still fires and the answer still wins. Only `--extra-vars` suppresses one.

That is why these live in the Variable Group's *Extra Variables*, which Semaphore passes as `--extra-vars`. Putting them in `hosts.yml` looks like it should work and does not.

Five of the six are fleet-wide constants, so setting them once here means you never type them again. The sixth, `target`, is per-run, and step 7 handles it.

## 12. Create the Template

Go to *Task Templates*, click **New Template**, and choose the **Ansible Playbook** app.

| Field | Value |
| --- | --- |
| *Name* | `provision-monitoring` |
| *Playbook Filename* | `provision.yml` |
| *Repository* | **ansible** from step 4 |
| *Inventory* | **ansible-fleet** from step 5 |
| *Variable Groups* | **ansible-private** from step 6 |
| *Tags* | `monitoring` |

The tag is `monitoring`, not `docker`. The password is consumed by `roles/monitoring/tasks/node-exporter.yml`, and `provision.yml` tags that role `monitoring`.

This Template needs no `komodo_onboarding_key`. Each host's key is single-use and generated fresh right before that host's own provisioning run.

### Add target as a Survey Variable

Open the Template's *Survey Variables* tab and add one entry:

| Field | Value |
| --- | --- |
| *Variable* | `target` |
| *Type* | **String** |
| *Required* | **Yes** |

Semaphore passes Survey Variables as `--extra-vars` too, so this suppresses the `target` prompt the same way step 6 suppresses the other five. It is a separate field because `target` changes per run and the other five never do.

Answer it with a host or group name from the inventory: ci01 for one host, `docker_host_h` for every Docker VM at once.

## 13. Fix existing hosts before running

`roles/monitoring/tasks/node-exporter.yml` writes `/etc/node-exporter/config.yml` only `when: not node_exporter_config.stat.exists`.

Every host provisioned before now already has that file, holding the bcrypt hash of `CHANGEME`. Running the Template against them changes nothing and reports no error. The task simply reports as skipped, and the host keeps the old password.

The role is idempotent for a fresh host and not idempotent for a password rotation. Delete the stale config first, on each already-provisioned host:

```bash
sudo rm -f /etc/node-exporter/config.yml
sudo systemctl restart node_exporter
```

Then run the Template against them.

Hosts built once `node_exporter_password` is committed to ansible-private never hit this. They get the real password on their first cloud-init run, and `config.yml` never exists with the wrong hash to begin with.

## 14. Replace this key once step-ca is live

Once step-ca's SSH CA is running on pk01, replace the static key from step 1 with a dedicated semaphore service principal using a short-lived, auto-renewed step-ca certificate.

Do not skip this. A static private key stored in Semaphore that grants passwordless root on every host in the fleet is exactly what step-ca exists to remove.

## What's next

Semaphore can now reach the fleet, and shared secrets stop being a per-host chore.

ci01 has one stack left. [VictoriaMetrics setup](victoriametrics-setup.md) deploys the fleet's metrics, logs, and traces backend, and its step 1 depends on the real `node_exporter_password` step 13 above just pushed.

After that, tf01 is the next VM. See [Running order](README.md#running-order).
