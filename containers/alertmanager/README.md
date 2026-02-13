# Initial Deployment Requirements
## How to include alertmanager in a stack

```yaml
services:
  alertmanager:
    extends:
      file: ../../containers/alertmanager/compose.yaml
      service: .alertmanager
```