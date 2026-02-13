# Initial Deployment Requirements
## How to include victorialogs in a stack

```yaml
services:
  victorialogs:
    extends:
      file: ../../containers/victorialogs/compose.yaml
      service: .victorialogs
```