# Initial Deployment Requirements
## How to include vmagent in a stack

For using with a Traefik stack
```yaml
services:
  vmagent:
    extends:
      file: ../../containers/vmagent/compose.yaml
      service: .vmagent-traefik
```

For using host data colletion
```yaml
services:
  vmagent:
    extends:
      file: ../../containers/vmagent/compose.yaml
      service: .vmagent-host
```