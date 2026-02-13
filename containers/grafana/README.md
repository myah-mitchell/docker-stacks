# Initial Deployment Requirements
## How to include grafana in a stack

```yaml
services:
  grafana:
    extends:
      file: ../../containers/grafana/compose.yaml
      service: .grafana
```