# Initial Deployment Requirements
## How to include uptime-kuma in a stack

```yaml
services:
  uptime-kuma:
    extends:
      file: ../../containers/uptime-kuma/compose.yaml
      service: .uptime-kuma
```
