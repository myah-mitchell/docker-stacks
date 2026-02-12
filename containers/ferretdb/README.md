# Initial Deployment Requirements
## How to include ferretdb in a stack

```yaml
services:
  ferretdb:
    extends:
      file: ../../containers/ferretdb/compose.yaml
      service: .ferretdb

  postgres:
    extends:
      file: ../../containers/ferretdb/compose.yaml
      service: .postgres-documentdb
```