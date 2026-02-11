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