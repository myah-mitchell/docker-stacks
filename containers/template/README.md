# Initial Deployment Requirements
## How to include imageName in a stack

```yaml
services:
  imageName:
    extends:
      file: ../../containers/imageName/compose.yaml
      service: .imageName
```