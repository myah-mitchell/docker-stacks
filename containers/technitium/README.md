# Initial Deployment Requirements
## How to include technitium in a stack

```yaml
services:
  technitium:
    extends:
      file: ../../containers/technitium/compose.yaml
      service: .technitium
```

## Note: Web console is exposed directly on the host
`compose.yaml` publishes the HTTPS web console directly on the host (`53443:53443`) in addition to routing it through Traefik with `chain-authentik@file` SSO. The direct port bypasses that SSO gate entirely — access via `:53443` relies solely on Technitium's own login. 

## `TECHNITIUM_BIND_IP` has no default
The DNS service port binding (`"${TECHNITIUM_BIND_IP}:53:53/udp"`) requires `TECHNITIUM_BIND_IP` to be set to the host's LAN IP address before deploying. It ships blank in `komodo.env`/`testing.env` with no fallback if left unset, the port binding becomes malformed (`:53:53/udp`) and the stack will fail to start. Set it explicitly per-server before deployment.