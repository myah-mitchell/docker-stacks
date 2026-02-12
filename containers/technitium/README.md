# Initial Deployment Requirements
## How to include technitium in a stack

```yaml
services:
  technitium:
    extends:
      file: ../../containers/technitium/compose.yaml
      service: .technitium
```