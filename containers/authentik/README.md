# Initial Deployment Requirements
## How to include authentik in a stack

```yaml
services:
  authentik-server:
    extends:
      file: ../../containers/authentik/compose.yaml
      service: .authentik-server

  authentik-worker:
    extends:
      file: ../../containers/authentik/compose.yaml
      service: .authentik-worker

  postgres:
    extends:
      file: ../../containers/postgres/compose.yaml
      service: .postgres

  redis:
    extends:
      file: ../../containers/redis/compose.yaml
      service: .redis
    command: --save 60 1 --loglevel warning

  geoipupdate:
    extends:
      file: ../../containers/geoipupdate/compose.yaml
      service: .geoipupdate

  socket-proxy:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy
    environment:
      EVENTS: 1 #optional
      IMAGES: 1 #optional
      INFO: 1 #optional
      PING: 1 #optional
      POST: 1 #optional
      VERSION: 1 #optional
```