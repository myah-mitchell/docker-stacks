# Initial Deployment Requirements
## How to include dozzle in a stack

Dozzle Server that can connect to multiple Dozzle Agents.

```yaml
services:
  dozzle-server:
    extends:
      file: ../../containers/dozzle/compose.yaml
      service: .dozzle-server
```

Dozzle Agent that the Dozzle Server can connect to.

```yaml
services:
  dozzle-agent:
    extends:
      file: ../../containers/dozzle/compose.yaml
      service: .dozzle-agent

  socket-proxy:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy
    environment:
      CONTAINERS: 1 #optional
      EVENTS: 1 #optional
      INFO: 1 #optional
      PING: 1 #optional
      VERSION: 1 #optional
```