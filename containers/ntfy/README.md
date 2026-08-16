# Initial Deployment Requirements
## How to include ntfy in a stack

```yaml
services:
  ntfy:
    extends:
      file: ../../containers/ntfy/compose.yaml
      service: .ntfy
```
