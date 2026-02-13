# Initial Deployment Requirements
## How to include victoriatraces in a stack

```yaml
services:
  victoriatraces:
    extends:
      file: ../../containers/victoriatraces/compose.yaml
      service: .victoriatraces
```