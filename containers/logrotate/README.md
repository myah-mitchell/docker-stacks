# Initial Deployment Requirements
## How to include logrotate in a stack

Note: Logrotate needs a socket-proxy service to work. Also Logrotate be default looks for Traefik, log if you want it to manage other logs, you will need to add volumn mappings.

```yaml
services:
  logrotate:
    extends:
      file: ../../containers/logrotate/compose.yaml
      service: .logrotate

  socket-proxy-rw:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy-rw
    environment:
      CONTAINERS: 1 #optional
      INFO: 1 #optional
      LOG_LEVEL: err #optional
      PING: 1 #optional
      POST: 1 #optional
      VERSION: 1 #optional
```