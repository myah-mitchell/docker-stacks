# Initial Deployment Requirements
## How to include vmauth in a stack

```yaml
services:
  vmauth:
    extends:
      file: ../../containers/vmauth/compose.yaml
      service: .vmauth
```