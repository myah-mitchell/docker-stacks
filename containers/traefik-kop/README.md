# Initial Deployment Requirements
## How to include traefik-kop in a stack

```yaml
services:
  traefik-kop:
    extends:
      file: ../../containers/traefik-kop/compose.yaml
      service: .traefik-kop
```