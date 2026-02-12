# Initial Deployment Requirements
## How to include postgres in a stack

```yaml
services:
  postgres:
    extends:
      file: ../../containers/postgres/compose.yaml
      service: .postgres
```