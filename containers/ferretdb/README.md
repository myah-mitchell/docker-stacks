# Initial Deployment Requirements
## How to include ferretdb in a stack

```yaml
services:
  ferretdb:
    extends:
      file: ../../containers/ferretdb/compose.yaml
      service: .ferretdb

  # FerretDB Postgres with DocumentDB Included
  postgres:
    extends:
      file: ../../containers/ferretdb/compose.yaml
      service: .postgres
```