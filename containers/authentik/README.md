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
```