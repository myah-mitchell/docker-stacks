# Initial Deployment Requirements
## How to include mailrise in a stack

```yaml
services:
  mailrise:
    extends:
      file: ../../containers/mailrise/compose.yaml
      service: .mailrise
```

Requires `ntfy` in the same stack (or reachable on the `backend` network) — `mailrise.conf` routes everything to it.
