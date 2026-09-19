# Initial Deployment Requirements
## Prerequisites for using postfix

A relay to send through, unless this host's public address can deliver mail itself. Most mail providers junk or refuse mail sent directly from a residential address, and Postfix here does no DKIM signing, so plan on an authenticated relay such as a mail host's SMTP submission service.

# Create and Setup Required Folders
## Create needed folders for postfix

Postfix runs as the image's own root, so its queue directory belongs to host UID `100000` rather than `101000`. Postfix creates the queue's subdirectories itself on first start.

## Open the firewall for postfix

Scope it to the internal subnet. Postfix relays for any private address with no login, which is fine for a LAN-only relay and not fine for anything wider.

## Point services at it

| Setting | Value |
| --- | --- |
| Server | This VM's LAN address |
| Port | `${POSTFIX_SMTP_PORT}`, default `25` |
| Encryption | None |
| Authentication | None |
| From address | Any address in `POSTFIX_ALLOWED_SENDER_DOMAINS`, which defaults to `DOMAIN_NAME` |

The sender check is an exact match on the domain. `pve@myah-mitchell.com` is relayed, while `root@pve.home.myah-mitchell.com` is refused until that sub-domain is added to the list.

Postfix also refuses a recipient whose domain has no DNS record, so a typo in a recipient domain fails at the sending service rather than bouncing later.
