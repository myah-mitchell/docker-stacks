# Wiring Semaphore to the ansible repo

Semaphore is running after [`ci01-bootstrap.md`](ci01-bootstrap.md), but it is not connected to anything. This doc connects it: a Project, an SSH credential, the `ansible` repo, a real inventory, the private variables, and a Template that runs against the fleet.

This is the point of building `ci01` before anything else. Until Semaphore can reach the fleet, every shared secret in `ansible` has to be fixed by hand, host by host, over SSH.

## The problem this solves

`ansible`'s `roles/monitoring/defaults/main.yml` ships `node_exporter_password: "CHANGEME"`.

That password is the HTTP basic-auth credential guarding each host's node_exporter metrics endpoint. `roles/monitoring/tasks/node-exporter.yml` bcrypt-hashes it into `/etc/node-exporter/config.yml` as the password for the user `node-exporter-user`, alongside a self-signed TLS cert. Prometheus later scrapes each host with those credentials.

`CHANGEME` is a placeholder committed to a public repo. Every host provisioned so far is running with it. It has to become a real value, everywhere, and stay that way for every host built afterwards.

The real value belongs in `ansible-private`'s `group_vars/all/private.yml`, which is where all real values live. But committing it there only fixes hosts provisioned later. Existing hosts need a re-run, and that is what Semaphore is for.

## Prerequisites

- Semaphore's UI loads and you can log in, through step 13 of [`ci01-bootstrap.md`](ci01-bootstrap.md).
- You have `ansible-private` checked out somewhere you can commit and push from.
- You know the four identity values used to provision the fleet: `short_name`, `abbr_name`, `location_abbr`, and `domain_name`.

## 1. Create the bootstrap SSH key

Semaphore reaches every host as the `ansible` service account, which `ansible`'s `users` role creates with `NOPASSWD: ALL` sudo and an `authorized_keys` file built from `ansible_ssh_public_keys`.

Generate the keypair:

```bash
ssh-keygen -t ed25519 -C "semaphore-bootstrap" -f ./semaphore-bootstrap -N ""
```

Add the public half, `semaphore-bootstrap.pub`, to `ansible-private`'s `group_vars/all/private.yml` under `ansible_ssh_public_keys`. That is a list, so append rather than replace. Commit and push.

Hosts provisioned after this point pick the key up automatically on first boot. Hosts that already exist do not, and Semaphore cannot fix that yet because it has no way in. Break the loop by hand, once per existing host, over SSH:

```bash
cd /tmp/ansible
ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' \
  --tags users
```

Use the same argument-recovery trick from [step 5](ci01-bootstrap.md#recover-the-original-provisioning-arguments) if you do not know the four values for that host.

Do this on `km01` and `ci01` at minimum. This static key is the same necessary-bootstrap-exception as Komodo's own manual first start, and [step 9](#9-replace-this-key-once-step-ca-is-live) replaces it later.

## 2. Create the Project

In Semaphore, create a Project named `fleet-provisioning`.

A Semaphore Project is the top-level container: Key Store, Repositories, Inventory, Variable Groups, and Templates all live inside one.

Do not name it `ansible`. Three things one level down inside it are already called `ansible`: the Repository in step 4, the service account it connects as, and the key credential in step 3.

## 3. Add the SSH key to the Key Store

Go to *Key Store > New Key*.

| Field | Value |
| --- | --- |
| *Name* | `ansible-bootstrap-key` |
| *Type* | `SSH Key` |
| *Username* | `ansible` |
| *Private Key* | The contents of `semaphore-bootstrap`, the private half from step 1 |

The *Username* field here is what becomes `ansible_user` on every connection, so the inventory in step 5 does not need to set it.

## 4. Add the ansible repository

Go to *Repository > New Repository*.

| Field | Value |
| --- | --- |
| *Name* | `ansible` |
| *URL* | `https://github.com/myah-mitchell/ansible` |
| *Branch* | `main` |
| *Access Key* | `None` |

`ansible` is public, so no deploy key is needed, the same as `docker-stacks`'s own Stack resource in Komodo.

`dotfiles` needs no Repository entry at all. Its own Ansible role clones it directly over plain HTTPS.

## 5. Create the inventory

This is the step with real work in it. The `hosts.yml` in both `ansible` and `ansible-private` is built for local runs: its `localhosts` group points `ubuntu`, `ubuntu_docker`, and `wsl` at `127.0.0.1`, because every Docker VM so far was provisioned by cloud-init with `-c local`.

Semaphore connects over SSH from `ci01`. Pointed at `ubuntu_docker`, it would run against `127.0.0.1`, which is `ci01` itself, every time. There is no group in the shipped inventory that names a real remote Docker host.

So the fleet's real Docker hosts have to be added as new entries. They do not exist yet in any file.

### Add a real host group to ansible-private

Open `ansible-private`'s `hosts.yml` and add a group alongside the existing `pve_host_h` and `pbs_host_h` ones. The `_h` suffix is the `location_abbr`, so keep the same shape:

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

Add each new VM to this group as you build it. `tf01`, `id01`, `pk01`, and the rest all belong here.

Commit and push `ansible-private`.

### Load it into Semaphore

Go to *Inventory > New Inventory*.

| Field | Value |
| --- | --- |
| *Name* | `ansible-fleet` |
| *Type* | `Static YAML` |
| *User Credentials* | `ansible-bootstrap-key` from step 3 |

Paste the full contents of `ansible-private`'s `hosts.yml`, including the group you just added. Semaphore stores inventory inline rather than cloning it from a repo, so this is a copy, not a reference.

> [!IMPORTANT]
> That copy does not update itself. Every time you add a host to `ansible-private`'s `hosts.yml`, paste the new content into this Inventory too, or Semaphore keeps running against the old list.

## 6. Create the ansible-private Variable Group

Go to *Variable Groups > New Group* and name it `ansible-private`.

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

Commit that same real `node_exporter_password` to `ansible-private`'s `group_vars/all/private.yml` as well, replacing the `CHANGEME` default. Semaphore's copy fixes existing hosts; the committed one is what fresh hosts get on their very first cloud-init boot, before Semaphore ever touches them. Both need it.

### Variables tab, Extra Variables

Everything else from `private.yml` that is not a credential goes here: `admin_ssh_public_keys`, `ansible_ssh_public_keys`, `client_ssh_public_keys`, `komodo_core_address`, `komodo_core_public_key`, `ca_certificates`, `client_account`, and so on.

Use the *JSON* toggle at the top of the field rather than entering every field as a table row. Generate the object from the file itself, dropping the three keys that belong on the *Secrets* tab:

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

Check the output before pasting. It should be one JSON object, and it must not contain any of those three keys.

Then add the four identity values, which are not in `private.yml` at all:

```json
{
  "short_name": "<short_name>",
  "abbr_name": "<abbr_name>",
  "location_abbr": "<location_abbr>",
  "domain_name": "<domain_name>"
}
```

Paste the merged object into the *JSON* editor, replacing the empty `{}`, and save.

### Why the identity values go here and not in the inventory

`provision.yml` declares `target`, `server_password`, `short_name`, `abbr_name`, `location_abbr`, and `domain_name` as `vars_prompt`. Semaphore runs non-interactively, so an unanswered prompt hangs the job.

An inventory or `group_vars` value does not suppress a `vars_prompt`. Ansible evaluates prompts at play parse time, before host selection and before inventory variables are in scope, so the prompt still fires and the answer still wins. Only `--extra-vars` suppresses one.

That is why these live in the Variable Group's *Extra Variables*, which Semaphore passes as `--extra-vars`. Putting them in `hosts.yml` looks like it should work and does not.

Five of the six are fleet-wide constants, so setting them once here means you never type them again. The sixth, `target`, is per-run, and step 7 handles it.

## 7. Create the Template

Go to *Task Templates > New Template* and choose the **Ansible Playbook** app.

| Field | Value |
| --- | --- |
| *Name* | `provision-monitoring` |
| *Playbook Filename* | `provision.yml` |
| *Repository* | `ansible` from step 4 |
| *Inventory* | `ansible-fleet` from step 5 |
| *Variable Groups* | `ansible-private` from step 6 |
| *Tags* | `monitoring` |

The tag is `monitoring`, not `docker`. `node_exporter_password` is consumed by `roles/monitoring/tasks/node-exporter.yml`, which `provision.yml` tags `monitoring`.

This Template needs no `komodo_onboarding_key`. Each host's key is single-use and generated fresh right before that host's own provisioning run.

### Add target as a Survey Variable

Open the Template's *Survey Variables* tab and add one entry:

| Field | Value |
| --- | --- |
| *Variable* | `target` |
| *Type* | `String` |
| *Required* | Yes |

Semaphore passes Survey Variables as `--extra-vars` too, so this suppresses the `target` prompt the same way step 6 suppresses the other five. It is a separate field because `target` changes per run and the other five never do.

Answer it with a host or group name from the inventory: `ci01` for one host, `docker_host_h` for every Docker VM at once.

## 8. Fix existing hosts before running

`roles/monitoring/tasks/node-exporter.yml` writes `/etc/node-exporter/config.yml` only `when: not node_exporter_config.stat.exists`.

Every host provisioned before now already has that file, holding the bcrypt hash of `CHANGEME`. Running the Template against them changes nothing and reports no error. The task simply reports as skipped, and the host keeps the old password.

The role is idempotent for a fresh host and not idempotent for a password rotation. Delete the stale config first, on each already-provisioned host:

```bash
sudo rm -f /etc/node-exporter/config.yml
sudo systemctl restart node_exporter
```

Then run the Template against them.

Hosts built once `node_exporter_password` is committed to `ansible-private` never hit this. They get the real password on their first cloud-init run, and `config.yml` never exists with the wrong hash to begin with.

## 9. Replace this key once step-ca is live

Once step-ca's SSH CA is running on `pk01`, replace the static key from step 1 with a dedicated `semaphore` service principal using a short-lived, auto-renewed step-ca certificate.

Do not skip this. A static private key stored in Semaphore that grants passwordless root on every host in the fleet is exactly what step-ca exists to remove.

## What's next

Semaphore can now reach the fleet, and shared secrets stop being a per-host chore.

`tf01` is the next VM. See [Running order](README.md#running-order).
