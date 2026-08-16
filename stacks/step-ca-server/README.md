# Create and Setup Required Folders
## Create Stack Folders

```bash
projectName="projectName"
mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName
```

## Create needed folders for step-ca

```bash
mkdir -p /opt/docker/volumes/$projectName/step-ca-data
sudo chown 1000:1000 /opt/docker/volumes/$projectName/step-ca-data

mkdir -p /opt/docker/stacks/$projectName/step-ca/secrets
```

## Generate the CA password once

```bash
head -c32 /dev/urandom | base64 > /opt/docker/stacks/$projectName/step-ca/secrets/password
chmod 600 /opt/docker/stacks/$projectName/step-ca/secrets/password
```

This password protects both the root and intermediate private keys at rest (step-ca's own encryption, independent of the extra age/GPG layer applied to the extracted root key below). Store a copy of it in Vaultwarden **and** in the same offline/outside-Vaultwarden location as the root key backups — losing this password after the root key is already offline means losing the ability to ever unlock it again, defeating the whole point of keeping a backup.

## First boot: generate root + intermediate, then verify

```bash
docker compose up -d step-ca
docker logs -f ${projectName}-step-ca   # watch for "Provisioners" / bootstrap-complete output
docker exec -it ${projectName}-step-ca step ca health --ca-url https://127.0.0.1:9000
```

At this point `/home/step/secrets/` inside the container holds **both** `root_ca_key` and `intermediate_ca_key`. That's only safe for the few minutes it takes to complete the next section — do it now, before this CA issues anything real.

## Extract and offline the root key (do this immediately after first boot)

This is the one part of Phase 5 that can't be templated — a real runbook, run once, by hand:

1. Copy the root key + cert out of the container (binary-safe, not `docker exec cat`):

   ```bash
   docker cp ${projectName}-step-ca:/home/step/secrets/root_ca_key ./root_ca_key
   docker cp ${projectName}-step-ca:/home/step/certs/root_ca.crt ./root_ca.crt
   ```

2. Add a second, independent encryption layer on top of step-ca's own password-protection (belt and suspenders for a file that's about to sit on a USB stick in a safe / with a trusted third party) — pick a strong, freshly generated passphrase, DIFFERENT from the CA password above, and write it down somewhere durable and NOT solely inside Vaultwarden (see the plan's "Break-glass access" section — same reasoning as every other break-glass secret in this plan):

   ```bash
   age -p -o root_ca_key.age root_ca_key
   ```

3. Copy `root_ca_key.age` + `root_ca.crt` to **two physically separate durable locations** (e.g. an encrypted USB key in a home safe, plus a second copy off-site — a bank box, a trusted person, anywhere not co-located with the first). Either copy alone is sufficient to recover; no reconstruction ceremony.

4. Wipe every plaintext/working copy from this machine and from the container:

   ```bash
   shred -u root_ca_key root_ca.crt root_ca_key.age
   docker exec ${projectName}-step-ca rm /home/step/secrets/root_ca_key
   ```

5. Confirm the CA still issues certs fine via the intermediate alone:

   ```bash
   docker restart ${projectName}-step-ca
   docker exec -it ${projectName}-step-ca step ca health --ca-url https://127.0.0.1:9000
   ```

## Test the recovery procedure once in a sandbox (an untested backup isn't a backup)

On a throwaway/sandbox machine, decrypt either of the 2 backup copies (prompts for the age passphrase):

```bash
age -d -o root_ca_key root_ca_key.age
```

Re-sign a throwaway intermediate from the offline root — confirms both the key and the step-ca password backup are actually usable, not just that the file exists:

```bash
step certificate create "sandbox intermediate" intermediate.crt intermediate.key \
  --ca ./root_ca.crt --ca-key ./root_ca_key --profile intermediate-ca
```

Then wipe the plaintext again:

```bash
shred -u root_ca_key intermediate.crt intermediate.key
```

## Traefik internal cert resolver (wiring — verify during implementation)

`containers/traefik/compose.yaml` has a commented-out `internalca` certificatesresolvers block pointed at this CA's ACME directory endpoint. The **DNS-01 challenge specifics are not yet confirmed** — step-ca's ACME server can issue without external domain-ownership proof since it's a private CA you already control, but the exact Traefik-side resolver flags (challenge type, whether a dnschallenge provider is even needed for an internal-only zone) need real testing against a running step-ca instance before uncommenting. Don't copy the letsencrypt resolver's DNS-01/Cloudflare config verbatim without checking it actually applies here.

## Root/intermediate trust distribution

Add step-ca's `root_ca.crt` (the public cert, not the key) to the `ansible/roles/certificates` role's file list — it already installs an internal CA cert into every host's trust store; this just adds a second file to that same mechanism.
