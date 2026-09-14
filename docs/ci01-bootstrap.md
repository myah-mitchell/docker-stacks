# ci01 bootstrap runbook

ci01 is the first VM deployed by Komodo rather than built by hand. Everything it needs is written down somewhere else, so this page is an overview and five pointers rather than a procedure.

ci01 carries four stacks, deployed in the order they appear below. traefik-bootstrap comes first and is temporary, there only so the other three can be reached at all.

semaphore-server is next. Once it is up and wired to the ansible repo, it becomes the way real shared secrets reach every other server, instead of being fixed by hand host by host.

victoriametrics-server is third. It is the metrics, logs, and traces backend every VM after this one writes to, which is why ci01 sits second in the running order rather than later.

core-infra is last, and it is what turns those metrics into something that reaches you: push notifications, mail relayed from Proxmox, external probes, and an uptime dashboard.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules.

## Prerequisites

- km01 is finished, through step 14 of [km01 bootstrap](komodo-bootstrap.md). Its four containers are healthy, its admin account exists, its firewall allows inbound 9120, and its global `[[GLOBAL_...]]` Variables are created. Step 3 of [Semaphore setup](semaphore-setup.md) fails without those Variables.
- The rest of what step 1 needs is in that doc's own [Prerequisites](provision-a-vm.md#prerequisites).

## Placeholders

The first six are the ones [Provisioning a VM](provision-a-vm.md) takes from this page. It lists four more that are the same for every host.

| Placeholder | Value |
| --- | --- |
| `<host>` | `ci01` |
| `<cores>` | `4` |
| `<memory>` | `8192` |
| `<vmid>` | VMID to give the new VM, yours to pick |
| `<ip>` | Static address for ci01, on the internal VLAN |
| `<gateway-ip>` | The internal VLAN's gateway |

## 1. Provision the VM

Follow [Provisioning a VM](provision-a-vm.md), six steps ending with ci01 connected and healthy under *Resources > Servers*.

Four cores and 8 GB is a floor rather than a target. Semaphore, Postgres, and postgres-backup are light on their own, but victoriametrics-server adds twelve more services, including Grafana and three VictoriaMetrics databases. Both metrics and log retention grow on disk, so watch `/opt/docker/volumes/victoriametrics` once it exists.

ci01 sits on the internal VLAN. It is not in the DMZ.

## 2. Deploy traefik-bootstrap onto ci01

semaphore-server publishes no port directly, and its Traefik labels are gated behind `chain-authentik@file`. Neither Traefik nor Authentik exists anywhere in the plan yet, so without this step there is no way to reach Semaphore's UI once it deploys.

traefik-bootstrap fills that gap: a real Traefik with self-signed TLS and `chain-no-auth@file` in place of a cert resolver and Authentik.

Follow [How to deploy it](traefik-bootstrap.md#how-to-deploy-it), five steps ending with all five services healthy. Set its `SERVER_NAME` to `ci01`. Whatever sub-domain and domain you give it, use the same pair for every stack on this host. The rest of that page covers what this stack does and when it gets torn down.

## 3. Deploy Semaphore

Semaphore goes before VictoriaMetrics on purpose. Once it is up and wired to the ansible repo, it becomes the way real shared secrets reach every other server, instead of being fixed by hand host by host.

Follow [Semaphore setup](semaphore-setup.md), thirteen steps covering semaphore-server from its runtime folders to a Template that runs against the fleet.

Only its last step can be left: replacing the bootstrap SSH key waits on pk01. Everything before it should be done before the next step here, because that Template is how the next step installs Node Exporter on ci01.

## 4. Deploy the VictoriaMetrics backend

victoriametrics-server is the fleet's metrics, logs, and traces backend, and it lands on ci01 alongside Semaphore. Every VM after this one runs vmagent, vlagent, and vector as sidecars in its traefik stack, all pointed here, so building it now is what lets those hosts ship from their first deploy.

Follow [VictoriaMetrics setup](victoriametrics-setup.md), which is seven steps from host prep to Grafana.

## 5. Deploy core-infra

VictoriaMetrics collects and stores. core-infra is what does something with it. ntfy delivers push notifications, mailrise turns Proxmox's mail into those notifications, blackbox-exporter probes services from outside, and uptime-kuma is the at-a-glance version of the same question.

It goes last on ci01 because blackbox-exporter has nothing scraping it until the previous step is done.

Follow [Core infrastructure setup](core-infra-setup.md), eight steps from runtime folders to a working notification path out of Proxmox.

## What's next

ci01 is finished once all five linked docs are, apart from [step 13 of Semaphore setup](semaphore-setup.md#13-replace-this-key-once-step-ca-is-live), which waits on pk01.

id01 is the next VM. See [Running order](README.md#running-order).

ci01 runs traefik-bootstrap until the whole fleet is up. Come back to it once id01 and pk01 exist, and replace it here with [system-agent](system-agent-setup.md) like every other VM.
