# Initial Deployment Requirements
## How to include crowdsec in a stack

For the Crowdsec LAPI Server:

```yaml
services:
  crowdsec-server:
    extends:
      file: ../../containers/crowdsec/compose.yaml
      service: .crowdsec-server

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

For the Crowdsec Agent that will connect to LAPI Server:

```yaml
services:
  crowdsec-agent:
    extends:
      file: ../../containers/crowdsec/compose.yaml
      service: .crowdsec-agent

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