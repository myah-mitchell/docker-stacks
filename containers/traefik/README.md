# How to use this in a stack
## How to include Traefik in a stack

Note: Traefik needs a socket-proxy service to work.

```yaml
services:
  traefik:
    extends:
      file: ../../containers/traefik/compose.yaml
      service: .traefik

  socket-proxy:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy
    environment:
      CONTAINERS: 1 #optional
      EVENTS: 1 #optional
      INFO: 1 #optional
      LOG_LEVEL: err #optional
      NETWORKS: 1 #optional
      NODES: 1 #optional
      PING: 1 #optional
      SERVICES: 1 #optional
      TASKS: 1 #optional
      VERSION: 1 #optional
```

## CrowdSec bouncer integration is currently disabled (WIP)
`compose.yaml` has the CrowdSec bouncer plugin partially wired up but disabled: the plugin `modulename` is commented out, the bouncer middleware is commented out on both the `http` and `https` entrypoints, `CROWDSEC_LAPI_KEY`/`CROWDSEC_LAPI_HOST` env vars are commented out, and `rules/middlewares-crowdsec.yaml` is entirely commented out. No stack currently deploys it. This is work-in-progress scaffolding, not a bug.