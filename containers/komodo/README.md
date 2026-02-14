# Initial Deployment Requirements
## How to include komodo in a stack

```yaml
services:
  komodo:
    extends:
      file: ../../containers/komodo/compose.yaml
      service: .komodo

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