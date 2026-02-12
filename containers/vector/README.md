# Initial Deployment Requirements
## How to include vector in a stack

For using with a Traefik stack
```yaml
services:
  vector:
    extends:
      file: ../../containers/vector/compose.yaml
      service: .vector-traefik
```

For using host data colletion
```yaml
services:
  vector:
    extends:
      file: ../../containers/vector/compose.yaml
      service: .vector-host

  socket-proxy:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy
    environment:
      CONTAINERS: 1 #optional
      EVENTS: 1 #optional
      INFO: 1 #optional
      PING: 1 #optional
      POST: 1 #optional
      VERSION: 1 #optional
```