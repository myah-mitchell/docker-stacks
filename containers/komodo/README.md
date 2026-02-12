# Initial Deployment Requirements
## How to include komodo in a stack

```yaml
services:
  komodo:
    extends:
      file: ../../containers/komodo/compose.yaml
      service: .komodo
```