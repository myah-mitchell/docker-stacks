# Initial Deployment Requirements
## How to include redis in a stack

Public Redis that other stacks can also access. Note requires password.

```yaml
services:
  redis:
    extends:
      file: ../../containers/redis/compose.yaml
      service: .redis-public
```

Replica of Public Redis stack. Note requires password.

```yaml
services:
  redis:
    extends:
      file: ../../containers/redis/compose.yaml
      service: .redis-replica
```

Internal Redis that only current stack can use. No password required.

```yaml
services:
  redis:
    extends:
      file: ../../containers/redis/compose.yaml
      service: .redis
```