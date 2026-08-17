# Initial Deployment Requirements
## How to include step-ca in a stack

```yaml
services:
  step-ca:
    extends:
      file: ../../containers/step-ca/compose.yaml
      service: .step-ca
```

Deploy on its own VM (`vm-pki-stepca` / `pk01.home.myah-mitchell.com`), home-internal/mesh-only — never exposed through the public edge. No `socket-proxy` needed — step-ca never talks to Docker.
