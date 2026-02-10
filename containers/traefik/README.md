# How to use this in a stack
## How to include Traefik in a stack

```yaml
services:
  Traefik:
    extends:
      file: ../../containers/Traefik/compose.yaml
      service: .Traefik
```