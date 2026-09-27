# One-run provisioning

`site.yml` in the ansible repo takes a host from an inventory entry to running Stacks in one run. For each host in `target` it:

1. Creates the VM through OpenTofu, if fleet-private's `opentofu/prod.tfvars` describes one for the host and it does not exist yet.
2. Waits for the VM's first boot and cloud-init to finish.
3. Runs `provision.yml` against the host over SSH, under its own inventory name, so its own `docker_stacks` list and host vars apply.
4. Reboots a new VM once, on its first run, if the package upgrade asks for it.
5. Runs Komodo's `fleet` Resource Sync for the host's Stacks, which creates or updates them and deploys them, then waits for them to be running.

Hosts with no VM in the tfvars file skip steps 1, 2 and 4, so the same run also brings a hand-built host's Stacks in line with the inventory.

Each fact lives in one file in fleet-private, keyed by the host's name:

| File | Holds |
| --- | --- |
| `hosts.yml` | What the host is: its address, roles, and `docker_stacks` |
| `opentofu/prod.tfvars` | Its VM: the Proxmox server, size, disks, VLAN and address |
| `komodo/stacks/<host>.toml` | Its Komodo Stacks, generated from the other two by `komodo-sync.yml` |

This replaces [Provisioning a VM](provision-a-vm.md) and the per-host Stack steps in each runbook for hosts that are described in the inventory. It does not replace km01's bootstrap, or ci01's, since Semaphore runs on ci01. Neither can be built by a run that depends on it.

Status: written and tested against a mocked Komodo API and a mocked Proxmox API. Not yet run end to end against the real fleet.

## Contents

- [What the run needs](#what-the-run-needs)
- [1. Switch the cloud-init snippet to minimal](#1-switch-the-cloud-init-snippet-to-minimal)
- [2. Create a Komodo service user](#2-create-a-komodo-service-user)
- [3. Create one onboarding key](#3-create-one-onboarding-key)
- [4. Create the Resource Sync](#4-create-the-resource-sync)
- [5. Add the secrets to Semaphore](#5-add-the-secrets-to-semaphore)
- [6. Create the site Template](#6-create-the-site-template)
- [Describing a host](#describing-a-host)
- [Generating the Komodo files](#generating-the-komodo-files)
- [Running it](#running-it)
- [What the run overwrites](#what-the-run-overwrites)
- [Limits](#limits)

## What the run needs

- The OpenTofu pieces already in place: a `tofu@pve` token and its role on each standalone server and each cluster (see the opentofu repo's README, and add `VM.Migrate` to the role on a cluster), and the `tofu_state` database on Semaphore's Postgres (see [The OpenTofu state database](semaphore-setup.md#the-opentofu-state-database)).
- Semaphore's inventory read from the fleet-private repo, as [step 10 of the Semaphore setup](semaphore-setup.md#load-it-into-semaphore) sets it up. The run reads the tfvars and Komodo files next to it.
- The identity values in `hosts.yml` rather than the Variable Group, as [Where the identity values go](semaphore-setup.md#where-the-identity-values-go) describes. The run asks for nothing, so a missing one stops it.
- `tofu` on the PATH of whatever runs ansible. The Semaphore image ships OpenTofu 1.9.0, which the opentofu repo supports.
- The `cloud.terraform` collection, listed in the ansible repo's `requirements.yml`. Check the first Semaphore run's log to confirm it was installed.

## 1. Switch the cloud-init snippet to minimal

By default the PVE vendor snippet makes each clone provision itself, as the `ubuntu_docker` example host. That run ignores the host's own inventory entry and races the one `site.yml` starts over SSH.

Set this in fleet-private's `group_vars/all/private.yml`:

```yaml
pve_cloudinit_mode: "minimal"
```

Then re-run the `pve-cloudinit` tag against every PVE host so the snippet is rewritten. Each node gets its own copy, and each cluster's first node also builds the template. In minimal mode a clone only installs and starts the guest agent, and creates the `ansible` login with `ansible_ssh_public_keys` and passwordless sudo. It does not upgrade packages, so first boot is quick and never reboots. `site.yml` does the rest: `provision.yml` upgrades the packages, and on the VM's first run `site.yml` reboots it afterwards if the upgrade asks for one, before any Stack is deployed. Later runs never reboot, even when an upgrade asks for it. unattended-upgrades handles those overnight, as on every other host.

The snippet is shared by every clone on the node, so hand-made clones stop provisioning themselves too. Follow [Provisioning a VM](provision-a-vm.md) for one of those and run `provision.yml` against it by hand, or give it an inventory entry and let `site.yml` do it.

## 2. Create a Komodo service user

In Komodo's UI, go to *Settings > Users* and create a service user, for example `ansible`. Make it an admin. It runs the `fleet` Resource Sync from step 4, which creates Stacks, and reads Servers and Stacks; the narrowest permissions that allow that have not been worked out. Create an API key for it and copy the key and the secret.

## 3. Create one onboarding key

Go to *Settings > Onboarding* and create a key with an expiry, not privileged. One key onboards every new host until it expires, so it can live as a Semaphore secret rather than being generated for each host. Anyone holding it can add a Server under a new name, which is what the expiry and the non-privileged setting limit. Replace it when it expires.

A rebuilt host does not use the key at all. It keeps Periphery's private key on its persistent disk and reconnects as the Server it already was.

## 4. Create the Resource Sync

Komodo reads each host's Stacks from fleet-private, so it needs a read token for that repo. Add one under *Settings > Providers* for `github.com`: a fine-grained PAT with read-only *Contents* access to fleet-private alone.

Then go to *Syncs* and create a Resource Sync named `fleet`:

| Field | Value |
| --- | --- |
| *Mode* | Git Repo |
| *Git Provider* | `github.com`, with the account from above |
| *Repo* | `myah-mitchell/fleet-private` |
| *Branch* | `main` |
| *Resource Paths* | `komodo/stacks` |
| *Delete Unmatched Resources* | Off |
| *Managed* | Off |

Leave deletion off. The sync only lists the Stacks `site.yml` manages, and with deletion on, every other resource in Komodo would be removed. Do not add a webhook or run the sync as a whole from the UI either. `site.yml` runs it for one host's Stacks at a time, after that host is prepared, and a full run would deploy every host's Stacks at once, including ones whose host is not ready.

The sync's *Pending* view still shows what differs from the files for every host, which is a useful check after a push.

## 5. Add the secrets to Semaphore

The run reads two kinds of values. Ansible variables go in the Variable Group's *Extra Variables* like everything else. OpenTofu and the Komodo role read theirs from the environment, so those go in *Environment Variables*, which [step 11 of the Semaphore setup](semaphore-setup.md#which-of-the-four-fields-to-use) otherwise leaves empty. `provision.yml` ignores them, so adding them to the existing **fleet-private** Variable Group is safe.

*Secrets* tab, *Environment Variables*:

| Name | Value |
| --- | --- |
| `TF_ENCRYPTION` | The encryption block from the opentofu repo's README, with the real passphrase |
| `PG_CONN_STR` | `postgres://tofu:<password>@postgres:5432/tofu_state?sslmode=disable` |
| `TF_VAR_server_api_tokens` | A JSON object with one token per server in the tfvars file, for example `{"vh01": "tofu@pve!tf=<secret>"}` |
| `KOMODO_API_KEY` | The service user's key from step 2 |
| `KOMODO_API_SECRET` | Its secret |

With a single server, its token can go in `PROXMOX_VE_API_TOKEN` instead of `TF_VAR_server_api_tokens`.

*Secrets* tab, *Extra Variables*, alongside what is already there:

```json
{
  "komodo_onboarding_key": "<the key from step 3>"
}
```

And in fleet-private's `group_vars/all/private.yml`, which is not secret:

```yaml
komodo_stacks_sub_domain_name: "home."
```

## 6. Create the site Template

Create a Template the same way as [provision](semaphore-setup.md#12-create-the-template), with the same `target` Survey Variable. These fields differ:

| Field | Value |
| --- | --- |
| *Name* | `site` |
| *Playbook Filename* | `site.yml` |
| *Tags* | empty |

Leave *Tags* empty so every step runs. The playbook's own tags (`vms`, `wait`, `reboot`, `komodo`, and every role tag in `provision.yml`) still work from the CLI with `--tags` or `--skip-tags`.

## Describing a host

A host that `site.yml` builds has an entry in `hosts.yml`, as any other:

```yaml
docker_host:
  hosts:
    ap01:
      ansible_host: 172.16.1.106
      serverHostname: "ap01"
      docker_stacks_bootstrap: true
      docker_stacks:
        - system-agent
        - traefik-agent
      komodo_stack_env:
        system-agent:
          DOCKNS_WAN_IP: "[[DOCKNS_WAN_IP_DMZ]]"
```

and a VM in `opentofu/prod.tfvars`, keyed by its `serverHostname` in lower case:

```hcl
servers = {
  lab = {
    endpoint       = "https://172.16.0.11:8006/"
    insecure       = true
    template_node  = "vh01"
    template_vm_id = 2604001
  }
}

vms = {
  ap01 = {
    server       = "lab"
    node_name    = "vh02"
    cores        = 2
    memory_mb    = 4096
    vlan_id      = 7
    ipv4_address = "172.16.1.106/24"
    ipv4_gateway = "172.16.1.1"
    dns_servers  = ["172.16.1.1"]

    extra_disks = {
      persist = { interface = "scsi2", size_gb = 20 }
    }
  }
}
```

`servers` lists each standalone Proxmox server and each cluster, reached through one node's API. `template_node` is the node holding the cloud-init template: the cluster's first PVE host in `hosts.yml`, which is the one the `pve` role builds it on. `insecure = true` skips the certificate check while the certificate is self-signed. The opentofu repo's `envs/prod/terraform.tfvars.example` and `variables.tf` list every key.

The VM's address must match its `ansible_host`, without the prefix. The run checks, and stops if they differ. `scsi2` is the persistent disk the docker role mounts at `/srv/persist`.

ap01 is pinned by `node_name`: it is cloned on vh01 and migrated to vh02, and if it is ever moved off vh02, the next run that includes it moves it back while it keeps running. Without `node_name`, a VM is created on the template node, and afterwards stays wherever you or HA move it. To move a pinned VM for good, change its `node_name` and run `site.yml` against it, which migrates it.

Hosts already built by hand have no VM in the tfvars file and OpenTofu never sees them. Do not add one for a running host. OpenTofu would try to create a second VM under the same name and address.

`docker_stacks_bootstrap: true` keeps ap01 in bootstrap mode, as described in [step 10 of the Semaphore setup](semaphore-setup.md#add-a-real-host-group-to-fleet-private). The run then deploys traefik-bootstrap in place of the stacks that need the rest of the fleet, and sets `TRAEFIK_AUTH_CHAIN` to `chain-no-auth@file`. Remove the line once tf01, id01 and pk01 are live.

`komodo_stack_env` sets values in a Stack's Environment beyond the ones every Stack gets. Every key must already have a line in that stack's `komodo.env`, so a misspelt key stops the run. `SERVER_NAME`, `SUB_DOMAIN_NAME`, `DOMAIN_NAME` and `TRAEFIK_AUTH_CHAIN` are filled in automatically wherever the file has them.

## Generating the Komodo files

`komodo/stacks/<host>.toml` is generated, never edited by hand. From a checkout of the ansible repo, with fleet-private checked out next to it:

```bash
ansible-playbook -i ../fleet-private/hosts.yml komodo-sync.yml
cd ../fleet-private
git diff komodo/
git add komodo/ && git commit -m "Regenerate Komodo stacks" && git push
```

Nothing connects to the hosts. Run it again after any of these, and commit before running `site.yml`:

- a host's `docker_stacks`, `docker_stacks_bootstrap` or `komodo_stack_env` changes
- a host is added, or stops running Stacks
- a stack's `komodo.env` changes in docker-stacks

`site.yml` renders the host's file itself and stops if the committed copy differs, naming the command to run. That keeps what Komodo reads from the repo and what the host was prepared for in step.

## Running it

In Semaphore, run **site** with *Target* set to the host, or to a group.

From a shell, with the same environment variables exported and the identity values in the inventory:

```bash
ansible-playbook -i ../fleet-private/hosts.yml site.yml -e target=ap01
```

Anything the inventory does not set, `server_password` included, is asked for once at the start.

Add `--check` to see OpenTofu's plan and confirm the Komodo files are current, without changing anything. The sync is skipped. Check mode stops at the plan for a VM that does not exist yet, so `provision.yml` fails to reach it. That is expected.

Only the VMs of the hosts in `target` are created. OpenTofu is still given every VM in the tfvars file, so it never plans to destroy one outside the run, and a plan that would destroy anything is refused.

## What the run overwrites

A Stack's Environment comes from the committed Komodo file, which is built from `stacks/<name>/komodo.env` and the inventory. An edit made to it in the Komodo UI is undone by the next sync. Put it in `komodo_stack_env` instead, or in a Komodo Variable or Secret the file references.

The sync deploys a Stack when it is not running or its config changed. The run then waits until every one of the host's Stacks is running, and stops naming any that are not.

The Stacks are named as the runbooks name them. system-agent, traefik-agent, traefik-bootstrap and the other `-agent` stacks get the host name on the end, like `system-agent-ci01`, and the rest keep their plain names. A Stack created by hand under the same name is taken over, not duplicated.

## Limits

- A stack whose `komodo.env` references a Komodo Variable or Secret that does not exist yet deploys with the literal `[[...]]` string, and usually fails. Create them first, from that stack's runbook.
- Leaving bootstrap mode does not delete a host's `traefik-bootstrap-<host>` Stack. Delete it in Komodo as [traefik-agent](traefik-agent-setup.md) step 6 describes, then remove `docker_stacks_bootstrap`, regenerate the Komodo files, and run `site.yml` to deploy traefik-agent.
- Likewise, a Stack whose host no longer lists it stays in Komodo, since the sync never deletes. Delete it there.
- Running the sync for only some Stacks, and whether a sync that also lists Stacks for a Server not yet in Komodo still runs for the others, are both unverified against a real Komodo. Only a mocked API has been tested.
- A pinned clone for a node other than its cluster's template node is migrated after cloning, and a pinned VM moved in Proxmox is migrated back. Both have been planned against a mocked API but not yet run against a real cluster.
- Every run reads the VM list of each server in the tfvars file, to find where unpinned VMs are now. A node that is down is missing from that list, and a run that includes an unpinned VM on it fails.
- A brand-new VM's SSH host key is accepted on first contact (`StrictHostKeyChecking=accept-new`), then pinned. Set `site_accept_new_host_keys: false` to turn that off.
