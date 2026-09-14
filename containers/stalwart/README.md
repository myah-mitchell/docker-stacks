# Initial Deployment Requirements
## How to include stalwart in a stack

```yaml
services:
  stalwart:
    extends:
      file: ../../containers/stalwart/compose.yaml
      service: .stalwart
```

Publishes host ports 25, 465, 587, and 993, so only one stack per host can include it. Nearly all of its configuration lives in its own WebUI rather than in this repo.
