# Initial Deployment Requirements
## How to include logrotate in a stack

```yaml
services:
  logrotate:
    extends:
      file: ../../containers/logrotate/compose.yaml
      service: .logrotate
```