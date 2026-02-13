# Initial Deployment Requirements
## How to include vmalert in a stack

```yaml
services:
  vmalert:
    extends:
      file: ../../containers/vmalert/compose.yaml
      service: .vmalert
```