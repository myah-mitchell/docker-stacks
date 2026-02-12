# Initial Deployment Requirements
## How to include geoipupdate in a stack

```yaml
services:
  geoipupdate:
    extends:
      file: ../../containers/geoipupdate/compose.yaml
      service: .geoipupdate
```