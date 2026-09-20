# Provisioning a VM

Every VM in the fleet except km01 is provisioned this way: cloned from the cloud-init template, given one onboarding key by hand, and left to join Komodo on its own. km01 is the exception because it is the Komodo Core that the rest of this depends on, and it was built before any of this existed.

Nothing here is host-specific. Each host's own runbook supplies the values in [Placeholders](#placeholders) and any caveat particular to it, then sends you here.

This ends when the host shows connected and healthy under *Resources > Servers*. Everything after that is that host's own stacks.

Read [Conventions](conventions.md) first. This doc assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Clone the template into a VM](#1-clone-the-template-into-a-vm)
- [2. Size and network the VM](#2-size-and-network-the-vm)
- [3. Start the VM](#3-start-the-vm)
- [4. Verify base provisioning](#4-verify-base-provisioning)
- [5. Give the host an onboarding key](#5-give-the-host-an-onboarding-key)
- [6. Confirm the host shows as a Komodo Server](#6-confirm-the-host-shows-as-a-komodo-server)
- [Run the stacks role without Semaphore](#run-the-stacks-role-without-semaphore)
- [Growing the persistent disk](#growing-the-persistent-disk)
- [What's next](#whats-next)

## Prerequisites

- km01 is finished, through step 14 of [km01 bootstrap](komodo-bootstrap.md). Its four containers are healthy, its admin account exists, its firewall allows inbound 9120, and its global `[[GLOBAL_...]]` Variables are created.
- The real Komodo Core address and public key are committed and pushed in ansible-private's `group_vars/all/private.yml`. That is step 13 of the km01 runbook, and the new host reads both at first boot.
- The cloud-init template exists on the target PVE host, the same one km01 was cloned from. Its name follows the Ubuntu version, so `ubuntu-server-2604` at 26.04.
- You can open Komodo's UI when you reach step 5. The onboarding key is single-use and short-lived, so there is nothing to prepare ahead of time.

## Placeholders

The first seven are in the Placeholders table of the host runbook that sent you here. The last five are the same for every host.

| Placeholder | Value |
| --- | --- |
| `<host>` | The hostname being built, for example `ci01` |
| `<cores>` | Core count, sized for the stacks that host carries |
| `<memory>` | Memory in MB, sized the same way |
| `<data-size>` | Size in GB of the disk that holds the host's stack data, sized the same way |
| `<gateway-ip>` | Gateway for the VLAN that host sits on |
| `<vmid>` | VMID to give the new VM, yours to pick |
| `<ip>` | Static address for it, on the VLAN the host runbook names |
| `<template-vmid>` | VMID of the cloud-init template, the same one km01 used |
| `<vm-storage>` | The Proxmox storage that holds VM disks, `local-zfs` on a host built with the pve role's defaults |
| `<km-ip>` | km01's address, from its own runbook |
| `<same>` | The value cloud-init already used, recovered in step 5 rather than guessed |
| `<ansible-private-url>` | Clone URL for ansible-private, from the ansible repo's README |

There is no single fleet gateway. Every host in the running order sits on the internal VLAN except bh01, which is the DMZ edge and takes the DMZ VLAN's gateway instead. Take `<gateway-ip>` and `<ip>` from the same VLAN the host runbook names.

## 1. Clone the template into a VM

On the PVE host:

```bash
qm clone <template-vmid> <vmid> --name <host> --full
```

## 2. Size and network the VM

```bash
qm set <vmid> --cores <cores> --memory <memory>
qm set <vmid> --ipconfig0 ip=<ip>/24,gw=<gateway-ip>
qm set <vmid> --scsi2 <vm-storage>:<data-size>,discard=on,ssd=1,iothread=1
```

The last line adds the disk the template does not carry. It is the persistent disk, mounted at `/srv/persist`, and it is the one disk on this VM worth keeping. Its `volumes` folder is bind mounted onto `/opt/docker/volumes`, where every stack keeps its state, its `logs` folder onto `/opt/docker/logs`, and its `host` folder holds what makes this VM itself: the SSH host keys and Periphery's private key. The template's own second disk becomes `/var/lib/docker` and holds only images, so it is thrown away with the VM. Add the data disk before the first boot: the ansible docker role stops when it cannot find it.

Size cores and memory for every stack the host will end up carrying, rather than resizing later. Each host's runbook gives the numbers and says what drives them. The data disk is the exception. It is thin provisioned and grows while the VM runs, so start with the size the runbook gives, and see [Growing the persistent disk](#growing-the-persistent-disk) when it fills. Container log files now share that disk with the data, so a stack that logs heavily counts against the same size.

Replacing an existing host instead of adding a new one? Skip the `--scsi2` line and follow [Rebuilding a VM](rebuild-a-vm.md), which moves the old host's data disk across.

Confirm the VLAN tag the template carries is the one that host belongs on, and that `<gateway-ip>` is that VLAN's gateway. The template comes tagged for the internal VLAN, which is right for every host except bh01.

## 3. Start the VM

```bash
qm start <vmid>
```

Cloud-init provisions the host on first boot the same way km01 was, installing Docker, the firewall, NTP, swap, node_exporter, and Komodo Periphery with no manual step. See [what the vendor snippet does](komodo-bootstrap.md#what-the-vendor-snippet-does) if you need the internals.

In the PVE web UI, expand *Datacenter* to the new VM and open its *Console*. There is no account to SSH in as until cloud-init creates one.

## 4. Verify base provisioning

SSH in once cloud-init finishes:

```bash
docker version
docker network inspect proxy --format '{{.Name}}'
systemctl status ufw
sudo -u komodo XDG_RUNTIME_DIR=/run/user/$(id -u komodo) systemctl --user status periphery.service
systemctl status node_exporter
sudo test -s /etc/node-exporter/scrape-password && echo present
```

All four services should be up and running, the network check should print `proxy`, and the last line should print `present`.

The last command needs that exact shape. Periphery runs as a `--user` systemd service under a dedicated `komodo` OS account, so a plain `systemctl status periphery` from your own login finds nothing. Ansible's docker role is what creates that account.

The docker role also creates the `proxy` network. Every deployable stack's `compose.yaml` declares it `external: true`, and Compose never creates an external network, so a host without it fails its first deploy with nothing to attach to.

The last two lines check the monitoring role. On its first run it generates this host's own Node Exporter password and publishes a copy to `scrape-password` for the host's vmagent, so nothing needs running from Semaphore afterwards. A missing file means the role failed during cloud-init. Re-run it from the `/tmp/ansible` checkout, the same way step 5 re-runs the docker role but with `--tags monitoring` and no onboarding key, rather than finding out later as a missing `node` series in system-agent.

Then check the two disks:

```bash
findmnt /var/lib/docker
findmnt /srv/persist
findmnt /opt/docker/volumes
findmnt /opt/docker/logs
sudo ls /srv/persist/host /srv/persist/host/komodo
lsblk -D
systemctl is-enabled fstrim.timer
```

Each `findmnt` should print a mount, and `/opt/docker/volumes` and `/opt/docker/logs` should show the `volumes` and `logs` folders of `/srv/persist` as their sources. The `host` folder should hold `ssh` and `komodo`. The `komodo` folder stays empty until step 5, when Periphery writes its key there. `lsblk -D` should show a nonzero `DISC-GRAN` on both disks, and the timer should print `enabled`. Discard and that timer are what hand deleted space back to the Proxmox pool. A VM without them keeps the space on the pool after its files are deleted, so a thin disk only ever grows.

Docker will not start if any of these mounts is missing. The docker role installs a systemd drop-in that requires them, because otherwise a missing data disk would send every container's data to the root disk without any error. SSH is deliberately not held back the same way. The docker role keeps a copy of the host keys on the persistent disk and restores them into `/etc/ssh`, so sshd never reads from the disk and a detached one cannot lock you out.

## 5. Give the host an onboarding key

This is the one manual step, and it is permanent. Every new host needs its own fresh onboarding key at provision time, the same way every new host needs its own SSH host key accepted. A host that is being rebuilt does not. It keeps Periphery's private key on its persistent disk and reconnects as it was, see [Rebuilding a VM](rebuild-a-vm.md#7-check-it-reconnected).

The ansible repo ships `komodo_onboarding_key` blank in the docker role's defaults, because a real value is single-use and must never be committed. Periphery needs one to make its first outbound connection to Core. After that, Core and the new host trust each other by their own Ed25519 keypairs and the onboarding key is discarded. Periphery's private key is written to `/srv/persist/host/komodo/periphery.key`, on the persistent disk rather than the OS disk, so it survives a rebuild.

In Komodo's UI on km01, at `http://<km-ip>:9120`, go to *Settings > Onboarding* and click **New Onboarding Key**.

> [!NOTE]
> Once Semaphore is up on ci01, the re-run below can also be done from a Semaphore Task Template, the same way [provision-monitoring](semaphore-setup.md#12-create-the-template) runs the monitoring role, with the `docker` tag and the onboarding key as a secret Survey Variable. The manual steps here work either way.

### Recover the original provisioning arguments

The re-run below has to pass the same four identity values cloud-init used the first time. Read them off the VM rather than guessing:

```bash
sudo grep -o "\-e '{[^']*}'" /var/lib/cloud/instance/scripts/runcmd
```

If that file is gone, the same values are in the vendor snippet on the PVE host, at `/var/lib/vz/snippets/cloudinit-vendor.yml`. Snippets live on the `local` storage.

### Re-run provisioning with the key

```bash
cd /tmp/ansible
ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' \
  -e '{"komodo_onboarding_key":"<the key you just generated>"}' \
  --tags docker
```

The `--tags docker` scoping keeps this from repeating the whole provisioning run.

`/tmp/ansible` is still the checkout cloud-init made in step 3, with the private overlay's real `hosts.yml` and `group_vars/all/private.yml` already copied in. Re-run in place.

> [!WARNING]
> Do not `git pull` that checkout first. Those two files are locally modified relative to git, because the overlay copies over them rather than committing. Pulling either refuses outright or silently reverts them to the public repo's sanitised placeholders.

If `/tmp/ansible` really is gone, re-clone the public repo and re-apply the overlay before provisioning:

```bash
git clone https://github.com/myah-mitchell/ansible /tmp/ansible
cd /tmp/ansible && ./scripts/bootstrap-private.sh <ansible-private-url>
```

Get that URL from the [ansible repo's README](https://github.com/myah-mitchell/ansible). Never paste a credentialed clone URL into docker-stacks, which is public.

### Confirm it connected

On the new host:

```bash
sudo -u komodo grep -A1 'core_address\|connect_as' /home/komodo/.config/komodo/periphery.config.toml
```

## 6. Confirm the host shows as a Komodo Server

Step 5's onboarding key created the Server resource the moment Periphery made its first outbound connection. There is nothing to add by hand.

In Komodo's UI on km01, check *Resources > Servers* and confirm the host shows connected and healthy before continuing. Re-check step 5 if it is not listed at all.

## Run the stacks role without Semaphore

The ansible `stacks` role sets a host up for a docker-stacks stack: it creates the stack's folders, seeds its config files, and opens its ports. It reads all three from the stack's generated `setup.yaml`, the same file every runbook's manual commands come from. Once Semaphore is up, hosts get this from the **provision-stacks** Template in [step 12 of Semaphore setup](semaphore-setup.md#create-the-provision-stacks-template).

km01, and the first two stacks on ci01, come before Semaphore exists. Those run the role on the host itself, from the `/tmp/ansible` checkout cloud-init left there. If that checkout is gone, re-create it as in [step 5](#re-run-provisioning-with-the-key) first.

The checkout can predate the role. Update everything in it except the two overlay files, which a pull would revert:

```bash
cd /tmp/ansible
git fetch origin
git checkout origin/main -- . ':(exclude)hosts.yml' ':(exclude)group_vars/all/private.yml'
```

Then run the role. Use the four identity values [recovered in step 5](#recover-the-original-provisioning-arguments), and set `<stack>` to the stack's directory name under `stacks/`, such as `komodo-server`:

```bash
ansible-playbook -i hosts.yml -c local provision.yml \
  -e '{"target":"ubuntu_docker","server_password":"","short_name":"<same>","abbr_name":"<same>","location_abbr":"<same>","domain_name":"<same>"}' \
  -e '{"docker_stacks":"<stack>"}' \
  --tags stacks
```

A stack that opens a port to the internal subnet also needs `docker_stacks_internal_subnet` in the second `-e`, set to that subnet in CIDR form. The role stops and says so when it is missing. None of the stacks run this way open one.

## Growing the persistent disk

The disk grows while the VM runs. On the PVE host:

```bash
qm resize <vmid> scsi2 +20G
```

Then on the VM, grow the filesystem into the new space:

```bash
sudo resize2fs /dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi2
df -h /srv/persist
```

The device path is the docker role's `docker_persist_device`. A disk only grows this way. Proxmox cannot shrink one, and thin provisioning makes that unnecessary, since the pool only holds what the filesystem is using once trim has run.

## What's next

Go back to the host's own runbook. What comes next is that host's stacks, which is the part no two hosts share.
