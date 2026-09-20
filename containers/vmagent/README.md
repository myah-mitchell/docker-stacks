# Initial Deployment Requirements
## How to include vmagent in a stack

For the per-VM system stack, which scrapes everything on the host, including a
Traefik stack if one runs there
```yaml
services:
  vmagent:
    extends:
      file: ../../containers/vmagent/compose.yaml
      service: .vmagent-system
```

For using host data colletion with node-exporter
```yaml
services:
  vmagent:
    extends:
      file: ../../containers/vmagent/compose.yaml
      service: .vmagent-host
```