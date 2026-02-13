# Initial Deployment Requirements
## How to include victoriametrics in a stack

```yaml
services:
  victoriametrics:
    extends:
      file: ../../containers/victoriametrics/compose.yaml
      service: .victoriametrics
```