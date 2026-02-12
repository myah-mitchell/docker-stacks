# Initial Deployment Requirements
## How to include crowdsec in a stack

For the Crowdsec LAPI Server:

```yaml
services:
  crowdsec-server:
    extends:
      file: ../../containers/crowdsec/compose.yaml
      service: .crowdsec-server

  postgres:
    extends:
      file: ../../containers/postgres/compose.yaml
      service: .postgres
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
      EVENTS: 1 #optional
      INFO: 1 #optional
      PING: 1 #optional
      VERSION: 1 #optional
```