# Initial Deployment Requirements
## How to include error-pages in a stack

```yaml
services:
  error-pages:
    extends:
      file: ../../containers/error-pages/compose.yaml
      service: .error-pages
```