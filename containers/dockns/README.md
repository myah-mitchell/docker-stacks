# Initial Deployment Requirements
## How to include dockns in a stack

```yaml
services:
  dockns:
    extends:
      file: ../../containers/dockns/compose.yaml
      service: .dockns

  socket-proxy:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy
    environment:
      CONTAINERS: 1 #optional
      INFO: 1 #optional
      VERSION: 1 #optional
```