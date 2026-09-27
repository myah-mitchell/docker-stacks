# Initial Deployment Requirements
## How to include semaphore in a stack

```yaml
services:
  semaphore:
    extends:
      file: ../../containers/semaphore/compose.yaml
      service: .semaphore

  postgres:
    extends:
      file: ../../containers/postgres/compose.yaml
      service: .postgres

  nix:
    extends:
      file: ../../containers/nix/compose.yaml
      service: .nix
```

No `socket-proxy` needed. Semaphore never talks to Docker, only outbound git/SSH to the fleet.
