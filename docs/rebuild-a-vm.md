# Rebuilding a VM

This replaces a host with a fresh VM cloned from a newer template, and keeps the host's data. It is how the fleet moves to a new Ubuntu release, and how a host gets a clean OS without an in-place upgrade. The old VM's OS disk and Docker disk are thrown away. Its persistent disk, mounted at `/srv/persist`, moves to the new VM.

That works because of how a host is split. Everything on the OS disk comes back from cloud-init and ansible, and Periphery re-clones each stack's checkout on deploy. The only state worth keeping is on the persistent disk: every stack's data and logs, which the host sees at `/opt/docker/volumes` and `/opt/docker/logs`, and the host's own identity, which is its SSH host keys and Periphery's private key. See [Provisioning a VM](provision-a-vm.md#2-size-and-network-the-vm) for how that disk gets there.

Read [Provisioning a VM](provision-a-vm.md) first. This page reuses its steps rather than repeating them.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Shut the old VM down](#1-shut-the-old-vm-down)
- [2. Snapshot the data disk](#2-snapshot-the-data-disk)
- [3. Free the hostname](#3-free-the-hostname)
- [4. Clone the new template](#4-clone-the-new-template)
- [5. Move the data disk across](#5-move-the-data-disk-across)
- [6. Start the new VM](#6-start-the-new-vm)
- [7. Check it reconnected](#7-check-it-reconnected)
- [8. Prepare the host and redeploy](#8-prepare-the-host-and-redeploy)
- [9. Remove the old VM](#9-remove-the-old-vm)
- [Rolling back](#rolling-back)
- [Rebuilding km01](#rebuilding-km01)
- [Order and pacing](#order-and-pacing)
- [Not yet confirmed](#not-yet-confirmed)

## Prerequisites

- The new template exists on the PVE host. Set `pve_template_ubuntu_version` and `pve_template_ubuntu_release` in ansible-private's `group_vars/all/private.yml`, run the pve role's `pve-cloudinit` tag against the PVE host, then run `/usr/local/bin/create-cloud-init-template.sh` on it, or wait for its weekly cron job. The template's VMID and name follow the version, so 28.04 gives VMID `2804001` and name `ubuntu-server-2804`. The old template stays where it is.
- The new release has been proved on a throwaway VM first. Clone the new template, add a data disk with the `--scsi2` line from Provisioning a VM step 2, start it, run [step 4's checks](provision-a-vm.md#4-verify-base-provisioning), then destroy it. This finds a missing package or a Docker apt repo that has not caught up with the release before it costs you a real host.
- The old host is healthy, and PBS has a recent backup of it.
- Both VMs live on the same PVE node. The data disk moves by renaming a volume on that node's storage, so it cannot cross nodes.

## Placeholders

| Placeholder | Value |
| --- | --- |
| `<host>` | The host being rebuilt, for example `id01` |
| `<old-vmid>` | VMID of the VM being replaced |
| `<new-vmid>` | VMID for its replacement, yours to pick |
| `<new-template-vmid>` | VMID of the new release's template, for example `2804001` |
| `<cores>`, `<memory>`, `<ip>`, `<gateway-ip>` | The same values the old VM has. Read them with `qm config <old-vmid>` |

## 1. Shut the old VM down

On the PVE host:

```bash
qm shutdown <old-vmid>
```

The containers stop with it and the data disk unmounts cleanly, which is what makes the disk safe to move. Komodo shows the Server as down until the new VM connects. That is expected.

## 2. Snapshot the data disk

This is the rollback point.

```bash
qm config <old-vmid> | grep '^scsi2'
pvesm path <volume>
```

`<volume>` is the storage and volume name on the `scsi2` line, such as `local-zfs:vm-101-disk-2`. `pvesm path` prints `/dev/zvol/<dataset>`. Snapshot that dataset:

```bash
zfs snapshot <dataset>@pre-rebuild
```

## 3. Free the hostname

Cloud-init names the new VM's OS after the VM itself, so the old VM has to give the name up first:

```bash
qm set <old-vmid> --name <host>-old
```

## 4. Clone the new template

```bash
qm clone <new-template-vmid> <new-vmid> --name <host> --full
qm set <new-vmid> --cores <cores> --memory <memory>
qm set <new-vmid> --ipconfig0 ip=<ip>/24,gw=<gateway-ip>
```

These are the same as [step 2 of Provisioning a VM](provision-a-vm.md#2-size-and-network-the-vm), without the `--scsi2` line. This VM gets its data disk from the old one. Confirm the VLAN tag is the one the old VM had.

## 5. Move the data disk across

```bash
qm disk move <old-vmid> scsi2 --target-vmid <new-vmid> --target-disk scsi2
qm config <new-vmid> | grep '^scsi2'
```

The new VM's `scsi2` line should carry `discard=on,ssd=1,iothread=1`. If the move dropped them, put them back, using the volume name that line prints. Without `discard=on`, deleted files never hand their space back to the pool:

```bash
qm set <new-vmid> --scsi2 <volume>,discard=on,ssd=1,iothread=1
```

Then check the old VM has let go of it. Step 9 relies on that.

```bash
qm config <old-vmid> | grep '^scsi2' || echo "no scsi2 on the old VM"
```

## 6. Start the new VM

```bash
qm start <new-vmid>
```

Cloud-init provisions it the same way as any new host. The docker role finds a disk that already carries an ext4 filesystem labelled `persist` and mounts it as it is. It never reformats a filesystem it finds. It then restores the saved SSH host keys into `/etc/ssh` and points Periphery at the saved private key. Follow [step 4 of Provisioning a VM](provision-a-vm.md#4-verify-base-provisioning), and also check the data came with it:

```bash
sudo ls /opt/docker/volumes /opt/docker/logs
sudo ls /srv/persist/host/komodo
```

The first should show the same project folders the old host had in both places, and the second should show `periphery.key`.

The new VM answers to the old host's SSH keys, so your next `ssh` to it should not warn about a changed host key. If it does, the keys were not restored, and that is worth understanding before going further.

## 7. Check it reconnected

There is nothing to generate. Periphery loaded the same private key the old VM used, and connects as the same Server name, so Core sees the host it already knows. In Komodo's UI on km01, check *Resources > Servers* and confirm `<host>` goes from down to connected within a minute or two.

If it does not, look at Periphery's log on the new host first:

```bash
sudo -u komodo XDG_RUNTIME_DIR=/run/user/$(id -u komodo) journalctl --user -u periphery.service -n 50
```

The fallback is to treat the host as a new one: generate an onboarding key and follow [step 5 of Provisioning a VM](provision-a-vm.md#5-give-the-host-an-onboarding-key). See [Not yet confirmed](#not-yet-confirmed) for what that may do to the Server resource Core already holds.

## 8. Prepare the host and redeploy

Run the ansible `stacks` role for the host's stacks, as in [Run the stacks role without Semaphore](provision-a-vm.md#run-the-stacks-role-without-semaphore), or from the **provision-stacks** Template if Semaphore is up. It creates each folder only when it is missing and never overwrites a config file that is already there, so the data on the moved disk is untouched. What it restores is the firewall rules, which live on the OS disk.

Then **Deploy** each of the host's Stacks in Komodo. Periphery clones a fresh checkout for each one, and the containers start against the data already on the disk.

Check each service the way its own runbook does. Leave the old VM alone until they pass.

## 9. Remove the old VM

Once the new host has run for long enough that you trust it, a few days is reasonable:

```bash
qm config <old-vmid> | grep '^scsi2' || echo "safe to destroy"
qm destroy <old-vmid>
zfs destroy <dataset>@pre-rebuild
```

Do not destroy the old VM while it still shows a `scsi2` line, because `qm destroy` deletes every disk the VM owns, including the data. The snapshot holds every block it covers on the pool until it is destroyed, so do not leave it there.

## Rolling back

If the new host is not healthy and you want the old one back:

```bash
qm shutdown <new-vmid>
qm disk move <new-vmid> scsi2 --target-vmid <old-vmid> --target-disk scsi2
qm set <new-vmid> --name <host>-new
qm set <old-vmid> --name <host>
qm start <old-vmid>
```

The data is as the new VM left it. If you want it as it was at the cutover instead, roll the dataset back before you start the old VM. That discards everything the new VM wrote:

```bash
zfs rollback <dataset>@pre-rebuild
```

Do not change container versions in the same session as a rebuild. A Renovate bump that has already run against the data can make a rollback stop being clean.

## Rebuilding km01

km01 is built by hand, so a few things that ansible restores on other hosts are yours to redo. Its checkout of this repo is on the OS disk and is disposable. Its `.env`, which holds the database passwords Postgres was initialised with, is not: [step 7 of the km01 runbook](komodo-bootstrap.md#7-generate-and-fill-in-the-stacks-env) keeps it at `/opt/docker/volumes/komodo/komodo-server.env` on the persistent disk and links the checkout to it. So nothing needs saving before step 1.

After step 6 above, follow [km01 bootstrap](komodo-bootstrap.md) with these changes:

- Do step 5 and clone this repo again.
- Step 6's folders and step 8's `core.config.toml` are already on the persistent disk. Running step 6's `stacks` role again is harmless.
- Do step 7, but only its link and the `build.py` run. The link finds the saved file, and `build.py` keeps every value in it, including the five you edited the first time, so there is nothing to fill in. Check `SERVER_NAME` and the domain are still right, and do not replace `KOMODO_DB_PASSWORD` or `POSTGRES_PASSWORD`.
- Do steps 9 to 11: the proxy network, the firewall rule for Core, and bringing the stack up.
- Steps 12 to 14 are already done. The admin account, Core's keys, and the global Variables all live in the data. Core's private key is under `komodo-keys` on the persistent disk, so the other hosts keep trusting it, and their Periphery connections should come back on their own.

Skip steps 7 and 8 of this page for km01. Its runbook above covers what it needs, and its own Periphery is not connected to anything yet.

## Order and pacing

Rebuild one host at a time. Start with the host that costs least to lose, and finish with km01. A rebuild that goes wrong on a small host tells you what to fix before it happens on Core.

## Not yet confirmed

Each of these came from documentation and from reasoning about the tools, not from a running system. Confirm them on the first real rebuild and correct this page.

- Whether `qm disk move --target-vmid` on ZFS renames the volume without copying it, and whether it keeps `discard`, `ssd`, and `iothread` on the moved disk. Step 5 checks the second one and repairs it.
- That Periphery reconnects with its saved key and no onboarding key. The Periphery config file says an onboarding key is not needed when connecting as a Server that already exists, but this has not been run. If step 7 fails and you fall back to a new onboarding key, the question becomes what Core does when a new key arrives under a Server name it already knows. The old Server resource is the first thing to look at, and deleting it may detach the Stacks that point at it, so check what is attached first.
- That Periphery accepts `private_key = "file:..."` pointing outside its own root directory and writes a new key there on a first start. The setting is documented in its config file, and the docker role sets it.
- The device names the docker role expects, `/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1` and `-scsi2`. Compare them with `ls -l /dev/disk/by-id` on a real VM.
- That the systemd drop-in keeps Docker from starting when a disk is missing, on an actual boot with the disk detached, and that the `/opt/docker/volumes` and `/opt/docker/logs` bind mounts wait for `/srv/persist` at boot.
- The km01 resume point. Steps 7 (the link and `build.py`) and 9 to 11 are what the reasoning above says is left to do, but no one has rebuilt km01 this way.
