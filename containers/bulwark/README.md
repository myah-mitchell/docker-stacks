# Initial Deployment Requirements
## How to include bulwark in a stack

```yaml
services:
  bulwark:
    extends:
      file: ../../containers/bulwark/compose.yaml
      service: .bulwark
```

Needs a JMAP server to talk to. It is written for `stalwart`, and defaults `JMAP_SERVER_URL` to Stalwart's public URL.
