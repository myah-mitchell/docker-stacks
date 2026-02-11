# Initial Deployment Requirements
## How to include socket-proxy in a stack

For a Read-Only Proxy:

```yaml
services:
  socket-proxy:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy
    environment:
      <PATHS TO Allow>: 1
```

For a Read-Write Proxy:

```yaml
services:
  socket-proxy-rw:
    extends:
      file: ../../containers/socket-proxy/compose.yaml
      service: .socket-proxy-rw
    environment:
      <PATHS TO Allow>: 1
```