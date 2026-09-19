# mx01 bootstrap runbook

mx01 runs Stalwart, a mail server that holds real mailboxes for the domain, and Bulwark, a webmail client for it. Accounts come from Authentik: SCIM creates each mailbox, and people sign in with their Authentik login.

This host is optional. Nothing else in the fleet depends on it, and the mail other services send already goes through Postfix on ci01. Skip this page if you do not want to host your own mailboxes.

It assumes a paid Stalwart Enterprise license. SCIM provisioning, which is what keeps mailboxes in step with Authentik, is an Enterprise feature.

Its stack is stalwart-server: Stalwart and Bulwark, two services.

> [!WARNING]
> This page was written from Stalwart's and Bulwark's documentation, and several details in it are unconfirmed. They are listed in [What is unconfirmed](#what-is-unconfirmed). Read that list before you start, and correct this page as you follow it.

Read [Conventions](conventions.md) first. This runbook assumes its naming and secrets rules.

## Contents

- [Prerequisites](#prerequisites)
- [Placeholders](#placeholders)
- [1. Provision the VM](#1-provision-the-vm)
- [2. Check the public address can handle mail](#2-check-the-public-address-can-handle-mail)
- [3. Forward the mail ports and open the firewall](#3-forward-the-mail-ports-and-open-the-firewall)
- [4. Deploy system-agent onto mx01](#4-deploy-system-agent-onto-mx01)
- [5. Create the runtime folders](#5-create-the-runtime-folders)
- [6. Create the Authentik application](#6-create-the-authentik-application)
- [7. Create the Komodo Secrets](#7-create-the-komodo-secrets)
- [8. Create the Stack resource](#8-create-the-stack-resource)
- [9. Run Stalwart's setup wizard](#9-run-stalwarts-setup-wizard)
- [10. Finish Stalwart's server settings](#10-finish-stalwarts-server-settings)
- [11. Publish the web hostnames through bh01](#11-publish-the-web-hostnames-through-bh01)
- [12. Add the domain, its DNS records, and a certificate](#12-add-the-domain-its-dns-records-and-a-certificate)
- [13. Turn on SCIM provisioning](#13-turn-on-scim-provisioning)
- [14. Sign in through Authentik](#14-sign-in-through-authentik)
- [15. Verify](#15-verify)
- [Recovering admin access](#recovering-admin-access)
- [What is unconfirmed](#what-is-unconfirmed)
- [What's next](#whats-next)

## Prerequisites

- system-agent can be deployed on a new VM, meaning ci01, id01, pk01, and tf01 are all live. See [system-agent prerequisites](system-agent-setup.md#prerequisites).
- bh01 is finished, through [bh01 bootstrap](bh01-bootstrap.md), and Authentik is published on `auth.myah-mitchell.com` through its tunnel. Stalwart and Bulwark both check sign-ins against that public address.
- A Stalwart Enterprise license key for the domain.
- A static public IPv4 address, an ISP that will set its reverse DNS record, and inbound port 25 not blocked by that ISP.
- The same DMZ VLAN bh01 uses, with a firewall that lets mx01 reach the internal services system-agent needs, and lets it out to the internet on TCP 25 and 443.
- A Cloudflare API token with DNS edit rights on the zone, for Stalwart's DNS records and certificate.

## Placeholders

The first six are the ones [Provisioning a VM](provision-a-vm.md) takes from this page. It lists four more that are the same for every host.

| Placeholder | Value |
| --- | --- |
| `<host>` | `mx01` |
| `<cores>` | `2` |
| `<memory>` | `4096` |
| `<vmid>` | VMID to give the new VM, yours to pick |
| `<ip>` | Static address for mx01, on the DMZ VLAN |
| `<gateway-ip>` | The DMZ VLAN's gateway |
| `<public-ip>` | The site's static public IPv4 address |
| `<proxy-subnet>` | The `proxy` Docker network's subnet on mx01, read in step 10 |
| `<client-id>` | The Authentik application's client ID, from step 6 |
| `<client-secret>` | The Authentik application's client secret, from step 6 |
| `<license-key>` | Your Stalwart Enterprise license key |
| `<cf-api-token>` | The Cloudflare API token from the prerequisites |
| `<scim-token>` | The Stalwart API key created in step 13 |
| `<recovery-password>` | A throwaway password, chosen only when you need [recovery](#recovering-admin-access) |

## 1. Provision the VM

Follow [Provisioning a VM](provision-a-vm.md), six steps ending with mx01 connected and healthy under *Resources > Servers*.

> [!IMPORTANT]
> At step 2 there, set the VLAN tag to the DMZ one, and take both `<ip>` and `<gateway-ip>` from the DMZ network, the same as bh01.

Two cores and 4 GB is enough for a household's mail. Stalwart is a single binary with an embedded store, and Bulwark is one Node process.

mx01 sits in the DMZ because, unlike every other host, it takes connections straight from the internet on its mail ports.

## 2. Check the public address can handle mail

Do this before building anything else. A residential range that other mail servers refuse is the most common reason self-hosted mail fails, and no setting on mx01 fixes it.

Check the reverse DNS record, from any machine:

```bash
dig -x <public-ip> +short
```

Expect `mx.myah-mitchell.com.`. If it returns your ISP's own name, ask the ISP to set the PTR record for `<public-ip>` to `mx.myah-mitchell.com`.

Check blocklists by entering `<public-ip>` at `https://check.spamhaus.org`. A listing on the PBL means your ISP has marked the range as not meant to send mail directly, and many providers will refuse mail from it.

Check that outbound port 25 is open, from mx01:

```bash
nc -vz -w 5 gmail-smtp-in.l.google.com 25
```

Expect `succeeded`. A timeout means the ISP blocks it.

If the PBL check or the port 25 check fails, Stalwart can still receive mail directly and send through a relay such as MXroute instead. Set that up in Stalwart's outbound routing once step 12 is done. The rest of this page is the same either way.

## 3. Forward the mail ports and open the firewall

On the router, forward these WAN ports to `<ip>`, TCP only:

| Port | Used for |
| --- | --- |
| `25` | Mail arriving from other servers |
| `465` | Mail clients sending, implicit TLS |
| `587` | Mail clients sending, STARTTLS |
| `993` | Mail clients reading, IMAP over TLS |

Do not forward 80, 443, or 8080. The web side reaches the internet through bh01's tunnel, never through a port forward.

Then let the ansible `stacks` role open them on mx01. In ansible-private's `hosts.yml`, add mx01 to the `docker_host` group if it is not there yet, and add the `stalwart-server` stack to its `docker_stacks` list, as in [step 10 of Semaphore setup](semaphore-setup.md#add-a-real-host-group-to-ansible-private). Commit and push it, and paste the new contents into Semaphore's **ansible-fleet** Inventory, as in [Load it into Semaphore](semaphore-setup.md#load-it-into-semaphore).

Run **provision-stacks** with *Target* answered `mx01`. The same run creates step 5's folders. Confirm the ports:

```bash
sudo ufw status
```

`25/tcp`, `465/tcp`, `587/tcp`, and `993/tcp` show `ALLOW` from `Anywhere`.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
sudo ufw allow 25/tcp comment 'Stalwart SMTP'
sudo ufw allow 465/tcp comment 'Stalwart submissions'
sudo ufw allow 587/tcp comment 'Stalwart submission'
sudo ufw allow 993/tcp comment 'Stalwart IMAPS'
sudo ufw status
```

</details>

## 4. Deploy system-agent onto mx01

mx01 skips traefik-bootstrap. Everything system-agent needs already exists by the time you reach this page, so it can have its real Traefik from the start.

Follow [system-agent](system-agent-setup.md), with Stack name `system-agent-mx01`. Skip its step 7, since there is no traefik-bootstrap to tear down.

Clear the four Cloudflare dockns keys to blank in its step 5, even though mx01 hosts public services. The public names come from tunnel routes in step 11 and from Stalwart in step 12, and a dockns record for the same name would fight both.

## 5. Create the runtime folders

Step 3's run created these. Check them on mx01:

```bash
sudo ls -ln /opt/docker/volumes/mail /opt/docker/volumes/mail/bulwark-data
```

The two `stalwart-` folders are owned by `102000`, and `bulwark-data` and the four folders inside it by `101001`.

<details>
<summary>Manual steps, instead of ansible</summary>

```bash
projectName="mail"

mkdir -p /opt/docker/logs/$projectName
sudo chmod 750 /opt/docker/logs/$projectName/
sudo chown $USER:101000 /opt/docker/logs/$projectName

mkdir -p /opt/docker/volumes/$projectName
sudo chmod 750 /opt/docker/volumes/$projectName/
sudo chown $USER:101000 /opt/docker/volumes/$projectName

mkdir -p /opt/docker/volumes/$projectName/stalwart-config
mkdir -p /opt/docker/volumes/$projectName/stalwart-data
sudo chown 102000:102000 /opt/docker/volumes/$projectName/stalwart-*

mkdir -p /opt/docker/volumes/$projectName/bulwark-data/settings
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/admin
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/admin-state
mkdir -p /opt/docker/volumes/$projectName/bulwark-data/telemetry
sudo chown -R 101001:101001 /opt/docker/volumes/$projectName/bulwark-data
```

</details>

Neither service uses the fleet's shared `PUID`. Each runs as its own image's user, so the owners are that user's ID plus Docker's `100000` offset: `102000` for Stalwart's UID 2000, and `101001` for Bulwark's UID 1001. See [Why 100000 and 101000](komodo-bootstrap.md#why-100000-and-101000).

`stalwart-data` holds every mailbox, account, and setting you make in Stalwart's WebUI. Back it up.

## 6. Create the Authentik application

One Authentik application covers both services. Bulwark signs people in through it, and Stalwart accepts the tokens it issues.

### Create the group

In Authentik's admin interface, go to *Directory > Groups* and create a group named `mail-users`. Add yourself to it.

Only members of this group get a mailbox. That matters because the Stalwart license is sold by mailbox count.

### Create the application and provider

Go to *Applications > Applications* and click **Create with provider**. Fill in the application:

| Field | Value |
| --- | --- |
| *Name* | `Mail` |
| *Slug* | `mail` |

Choose *OAuth2/OpenID Provider* as the provider type, then fill in the provider:

| Field | Value |
| --- | --- |
| *Client type* | Confidential |
| *Redirect URIs* | Regex, `https://webmail\.myah-mitchell\.com/.*` |
| *Signing Key* | `authentik Self-signed Certificate` |

Copy the *Client ID* and *Client Secret* shown on that page. They are `<client-id>` and `<client-secret>`.

The signing key matters. Without one, Authentik signs tokens with the client secret, and Stalwart cannot check a token signed that way.

The redirect URI is a regex because Bulwark's exact callback path is not documented. Once sign-in works in step 15, tighten it to the path Authentik's logs show.

### Limit it to the group

On the new application, open *Policy / Group / User Bindings*, click **Bind existing policy / group / user**, and bind the `mail-users` group.

The application's issuer is `https://auth.myah-mitchell.com/application/o/mail/`, with the trailing slash. Stalwart needs it in step 14.

## 7. Create the Komodo Secrets

In Komodo's UI, go to *Settings > Secrets* and create these four:

| Secret | Value |
| --- | --- |
| `STALWART_LICENSE_KEY` | `<license-key>` |
| `BULWARK_SESSION_SECRET_KEY` | 96 alphanumeric characters of your choice |
| `MAIL_OIDC_CLIENT_ID` | `<client-id>` |
| `MAIL_OIDC_CLIENT_SECRET` | `<client-secret>` |

`BULWARK_SESSION_SECRET_KEY` encrypts Bulwark's remember-me sessions and synced settings. Changing it later signs everyone out and discards their synced settings.

## 8. Create the Stack resource

In Komodo's UI, go to *Resources > Stacks* and create a Stack named `stalwart-server`. Set its target *Server* to **mx01**.

### Point it at the repo

Under *Choose Mode*, choose **Git Repo**.

| Field | Value |
| --- | --- |
| *Repo* | `myah-mitchell/docker-stacks` |
| *Branch* | `main` |
| *Run Directory* | `stacks/stalwart-server` |
| *File Path* | `compose.yaml`, relative to the run directory |

### Paste the environment

Open `stacks/stalwart-server/komodo.env`, copy its full contents, and paste them into *Environment*.

Four keys need a value from you:

| Key | Value |
| --- | --- |
| `SERVER_NAME` | `mx01` |
| `SUB_DOMAIN_NAME` | This site, with the trailing dot, so `home.` |
| `DOMAIN_NAME` | The real domain, `myah-mitchell.com` |
| `BULWARK_OAUTH_ISSUER_URL` | `https://auth.myah-mitchell.com/application/o/mail`, with no trailing slash |

The issuer is written two ways on purpose. Bulwark wants it without the trailing slash, while Stalwart in step 14 has to match Authentik's issuer exactly, slash included.

Leave `STALWART_SERVICE_NAME` as `mail` and `BULWARK_SERVICE_NAME` as `webmail`. Leave every `[[...]]` reference as pasted, since step 7 created them all.

### Deploy

Save the Stack resource, then click **Deploy**.

Stalwart starts in bootstrap mode, with no mail services running yet. Bulwark waits for Stalwart to be healthy, then starts, though it cannot sign anyone in until step 14.

## 9. Run Stalwart's setup wizard

Read the one-time admin password Stalwart printed on first start, on mx01:

```bash
docker logs mail-stalwart 2>&1 | grep -A8 'bootstrap mode'
```

It changes every time Stalwart starts in bootstrap mode, so read it again after any restart.

Browse to `https://mail.mx01.home.myah-mitchell.com/admin`, substituting whatever sub-domain and domain you set. Sign in as `admin` with that password.

Work through the wizard:

1. Set the server hostname to `mx.myah-mitchell.com`.
2. Keep the default embedded data store.
3. Create the permanent administrator account, and store its password in Vaultwarden.

The wizard writes `config.json` and restarts Stalwart. Sign back in with the permanent administrator account at the same address.

## 10. Finish Stalwart's server settings

### Trust Traefik

Read the `proxy` network's subnet, on mx01:

```bash
docker network inspect proxy --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}'
```

That is `<proxy-subnet>`. In the WebUI, go to *Settings > Network > General* and add `<proxy-subnet>` to the trusted proxy networks.

Do this now, before anything reaches Stalwart from outside. Every web request arrives from Traefik's address, and Stalwart's auto-ban can end up banning Traefik itself, which locks everyone out at once.

### Add the license

Go to *Settings > Enterprise*. Set the license key's source to *Environment Variable*, with the variable name `STALWART_LICENSE_KEY`.

Restart the stalwart container from Komodo so it rereads its settings, then sign out and back in. The Enterprise sections of the WebUI should now be available.

### Add Cloudflare as a DNS provider

Go to *Settings > Network > DNS > DNS Providers* and add a *Cloudflare* provider, with `<cf-api-token>` as its secret.

Stalwart uses it in step 12, both to publish the domain's mail records and to prove it owns `mx.myah-mitchell.com` for a certificate.

## 11. Publish the web hostnames through bh01

Stalwart's web side, Bulwark, and the two well-known names mail software fetches all go through bh01's tunnel. On the admin machine that holds the tunnel credentials:

```bash
cloudflared tunnel route dns home-edge mail.myah-mitchell.com
cloudflared tunnel route dns home-edge webmail.myah-mitchell.com
cloudflared tunnel route dns home-edge autoconfig.myah-mitchell.com
cloudflared tunnel route dns home-edge mta-sts.myah-mitchell.com
```

Then add a matching rule for each one to bh01's `config.yml`, above the catch-all, and redeploy traefik-dmz:

```yaml
  - hostname: mail.myah-mitchell.com
    service: http://traefik-traefik:80
  - hostname: webmail.myah-mitchell.com
    service: http://traefik-traefik:80
  - hostname: autoconfig.myah-mitchell.com
    service: http://traefik-traefik:80
  - hostname: mta-sts.myah-mitchell.com
    service: http://traefik-traefik:80
```

See [step 7 of bh01 bootstrap](bh01-bootstrap.md#7-publish-the-first-hostname) for how the two halves fit together.

Both services do their own authentication, so they are safe to publish before Authentik is wired in. Until step 14, only the administrator account from step 9 can sign in to anything.

Confirm `https://mail.myah-mitchell.com/admin` loads from outside your network, such as from a phone with Wi-Fi off.

## 12. Add the domain, its DNS records, and a certificate

> [!WARNING]
> This step moves the domain's inbound mail to mx01. If `myah-mitchell.com` already receives mail somewhere else, that stops once the MX record changes. Turn off Cloudflare Email Routing for the zone first if it is on, because it owns the MX records while enabled.

### Create the A record by hand

In the Cloudflare dashboard, add an `A` record for `mx.myah-mitchell.com` pointing at `<public-ip>`, with the proxy status set to *DNS only*.

It has to be DNS only. Cloudflare's proxy carries web traffic, not mail.

### Add the domain

In the WebUI, go to *Management > Domains > Domains*. Open `myah-mitchell.com` if the wizard created it, or create it.

Link it to the Cloudflare DNS provider from step 10, so Stalwart publishes and maintains its own records. Stalwart rotates its DKIM keys every 90 days by default, which only works if it can update DNS itself.

Exclude the `autoconfig`, `autodiscover`, and `mta-sts` CNAME records from what Stalwart publishes. Step 11's tunnel routes already own `autoconfig` and `mta-sts`, and a second record for the same name would replace them.

Once it has published, compare the domain's expected zone, shown in its `dnsZoneFile` field, with the zone in the Cloudflare dashboard. Expect MX, SPF, DKIM, DMARC, TLS reporting, MTA-STS, and the mail client SRV records.

If the domain already has an SPF record, merge the two into one. A domain with two SPF records fails SPF entirely.

### Get a certificate for the mail ports

Traefik's certificate covers only the web side. Clients connecting to ports 465, 587, and 993, and servers using STARTTLS on 25, see Stalwart's own certificate.

Add an ACME provider for Let's Encrypt that uses the DNS-01 challenge through the Cloudflare DNS provider, for `mx.myah-mitchell.com`. Restart the stalwart container once it reports the certificate as issued.

Check it from any machine:

```bash
openssl s_client -connect mx.myah-mitchell.com:993 -servername mx.myah-mitchell.com </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer
```

Expect `mx.myah-mitchell.com` as the subject and Let's Encrypt as the issuer. From inside the network this needs hairpin NAT on the router, so use an outside connection if it hangs.

## 13. Turn on SCIM provisioning

SCIM lets Authentik create, update, and disable Stalwart accounts as group membership changes. Without it, a mailbox only exists after its owner has signed in once, and mail sent to them before that is refused.

Do this before step 14. The administrator account from step 9 is the one you use here, and it may stop being able to sign in once Stalwart trusts Authentik.

### On Stalwart

In *Management > Domains > Domains*, open `myah-mitchell.com` and turn on `allowScimProvisioning`.

In *Management > Accounts*, create an account named `scim` in that domain, to act as Authentik's service account. Give it these permissions:

- `scimAccess`
- `authenticate`
- `sysAccountGet`
- `sysAccountCreate`
- `sysAccountUpdate`

On that account, go to *Credentials > API Keys* and create a key in *Replace* mode. Stalwart shows the secret once. That secret is `<scim-token>`.

### On Authentik

Go to *Applications > Providers*, click **Create**, and choose *SCIM Provider*.

| Field | Value |
| --- | --- |
| *Name* | `mail-scim` |
| *URL* | `https://mail.myah-mitchell.com/scim/v2` |
| *Token* | `<scim-token>` |
| *Compatibility mode* | Default |
| *Group* filter | `mail-users` |

Then edit the `Mail` application from step 6 and add `mail-scim` under *Backchannel Providers*.

### Check the first sync

Open the `mail-scim` provider in Authentik and start a sync. In Stalwart, *Management > Accounts* should now list an account for each member of `mail-users`.

Check how the account names came out. Stalwart has to see the same name here as in step 14, which builds it from the Authentik username plus `@myah-mitchell.com`.

If the accounts are named with the bare username instead, add a SCIM property mapping in Authentik under *Customization > Property Mappings* and select it on `mail-scim`:

```python
return {
    "userName": f"{request.user.username}@myah-mitchell.com",
}
```

### Make yourself an administrator

In *Management > Accounts*, open your own SCIM-created account and give it the administrator role. This is the account you manage Stalwart with from step 14 onward.

## 14. Sign in through Authentik

Read [Recovering admin access](#recovering-admin-access) before this step. If this goes wrong, the recovery procedure is how you get back in.

### Create the OIDC directory

In the WebUI, create a directory of type OIDC:

| Field | Value |
| --- | --- |
| `issuerUrl` | `https://auth.myah-mitchell.com/application/o/mail/` |
| `requireAudience` | `<client-id>` |
| `claimUsername` | `preferred_username` |
| `usernameDomain` | `myah-mitchell.com` |
| `claimName` | `name` |

The issuer must match Authentik's exactly, trailing slash included. A mismatch shows up in Stalwart's log as `InvalidIssuer`.

`usernameDomain` turns an Authentik username such as `myah` into the account `myah@myah-mitchell.com`, which is the name SCIM created in step 13.

### Switch authentication to it

Go to *Settings > Authentication > General* and set the directory to the OIDC directory you just created.

In a private browser window, browse to `https://webmail.myah-mitchell.com` and sign in with your Authentik account. Keep the existing admin session open in the first window until this works.

If it fails, check Stalwart's log from mx01:

```bash
docker logs mail-stalwart 2>&1 | grep -iE 'oidc|jwt|issuer|audience'
```

## 15. Verify

Confirm both services show running and healthy in Komodo's container view:

```text
stalwart
bulwark
```

### Receive

From a mailbox outside the domain, send a message to your own address at `myah-mitchell.com`. It should arrive in Bulwark within a minute.

### Send

Reply to it from Bulwark. In the outside mailbox, open the message's original headers and look for `spf=pass`, `dkim=pass`, and `dmarc=pass`.

A `fail` or `none` on any of the three means the DNS records from step 12 are missing or wrong. Fix it before sending real mail, because providers remember an address that sent unauthenticated mail.

### Check port 25 from outside

Use an outside SMTP test, such as MXToolbox's, against `mx.myah-mitchell.com`. Expect Stalwart's banner, working STARTTLS, and no open relay warning.

Then check that Stalwart saw the tester's real address rather than a Docker one:

```bash
docker logs mail-stalwart 2>&1 | tail -50
```

## Recovering admin access

Use this if no administrator can sign in, for example after an OIDC setting in step 14 goes wrong.

Stop the stalwart container from Komodo. Then on mx01, start a one-off copy in recovery mode against the same volumes:

```bash
docker run --rm -it --name mail-stalwart-recovery \
  --volumes-from mail-stalwart \
  -e STALWART_RECOVERY_MODE=1 \
  -e STALWART_RECOVERY_ADMIN=recovery:<recovery-password> \
  -p 127.0.0.1:8080:8080 \
  stalwartlabs/stalwart:v0.16.22
```

Recovery mode runs only the admin interface, with no mail services, and listens only on mx01's loopback address. Reach it from your admin machine through an SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 mx01
```

Browse to `http://127.0.0.1:8080/admin` and sign in as `recovery` with `<recovery-password>`. Fix the problem, press **Ctrl+C** in the recovery container's terminal, and start the stalwart container again from Komodo.

Never add either recovery variable to the stack itself. `STALWART_RECOVERY_ADMIN` is an administrator login that bypasses every directory.

## What is unconfirmed

Each of these came from documentation, not from a running system. Confirm them on the first real run and correct this page.

- The exact WebUI menu paths and field labels in steps 9 through 14. Stalwart moved its configuration into the WebUI in 0.16, and most published guides still describe the older TOML files.
- Whether port 8080 serves the whole WebUI, JMAP, and SCIM after the wizard finishes, or only during bootstrap. The compose file routes all web traffic there.
- Whether Authentik's access tokens carry the client ID as their audience and include `preferred_username`. Stalwart's `requireAudience` and `claimUsername` depend on both.
- The account name Authentik's SCIM provider sends, and whether Stalwart accepts Authentik's default user attributes such as `photos` and `locale`. Stalwart returns an error for attributes it does not recognize.
- Whether the step 9 administrator can still sign in once the OIDC directory is active. This page assumes not, which is why step 13 makes your own account an administrator first.
- Whether OIDC accounts can create app passwords in Stalwart's account manager at `/account`. Stalwart's documentation says both yes and no, and desktop mail clients without OAuth support need them.
- Bulwark's OAuth callback path, hence the regex redirect URI in step 6.
- Whether a port published from Docker shows Stalwart the real client address. Docker normally preserves it for IPv4, and step 15 checks.

## What's next

mx01 is finished. Nothing else in the running order waits on it.

Desktop and phone mail clients are the next thing to try. Clients that support OAuth can sign in through Authentik directly, and the rest need an app password from `https://mail.myah-mitchell.com/account`, if the unconfirmed point above works out.

Two changes are possible later without rebuilding anything here:

- Point ci01's Postfix at Stalwart instead of an outside relay, by setting `POSTFIX_RELAYHOST` to `[mx.myah-mitchell.com]:587`. That needs a Stalwart account Postfix can log in to with a password, which the OIDC directory does not give it.
- Move inbound and outbound mail to a pair of cloud servers that relay to mx01 over a private link. That changes the MX record and Stalwart's outbound route, and removes the need for the port forwards in step 3.

See [Running order](README.md#running-order) for where mx01 sits.
