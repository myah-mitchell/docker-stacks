# Initial Deployment Requirements
## How to include cadvisor in a stack

```yaml
services:
  cadvisor:
    extends:
      file: ../../containers/cadvisor/compose.yaml
      service: .cadvisor
```