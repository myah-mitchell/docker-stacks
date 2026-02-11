# Initial Deployment Requirements
## How to include vlagent in a stack

```yaml
services:
  vlagent:
    extends:
      file: ../../containers/vlagent/compose.yaml
      service: .vlagent
```