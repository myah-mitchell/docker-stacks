# Initial Deployment Requirements
## How to include postgres-backup in a stack

```yaml
services:
  postgres-backup:
    extends:
      file: ../../containers/postgres-backup/compose.yaml
      service: .postgres-backup
    environment:
      # Point at this stack's own postgres service/credentials — never share one
      # postgres-backup instance across stacks. Match POSTGRES_BACKUP_DB to whatever
      # this stack's postgres service actually uses (a ${POSTGRES_DB} var, or a
      # literal like "postgres" for the FerretDB/Komodo case).
      POSTGRES_BACKUP_DB: ${POSTGRES_DB}
      POSTGRES_BACKUP_USER: ${POSTGRES_USER}
      POSTGRES_BACKUP_PASSWORD: ${POSTGRES_PASSWORD}
```

One `postgres-backup` instance per stack that has a `postgres`/`postgres-documentdb` service, pointed at that stack's own database only. `depends_on: postgres (service_healthy)` is already set in the base service, so it won't start dumping before the database is actually up.
