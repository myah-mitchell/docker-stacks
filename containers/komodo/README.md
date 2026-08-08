# Initial Deployment Requirements
## How to include komodo in a stack

```yaml
services:
  komodo:
    extends:
      file: ../../containers/komodo/compose.yaml
      service: .komodo

  ferretdb:
    extends:
      file: ../../containers/ferretdb/compose.yaml
      service: .ferretdb

  # FerretDB Postgres with DocumentDB Included
  postgres:
    extends:
      file: ../../containers/ferretdb/compose.yaml
      service: .postgres
```

## Note: Admin UI is currently exposed on the host, without an SSO gate
`compose.yaml` publishes the Komodo UI directly on the host (`9120:9120`) in addition to routing it through Traefik. Unlike Dozzle/Technitium, the Traefik route uses `chain-no-auth@file`, not `chain-authentik@file` so neither path puts an SSO gate in front of it, and the direct host port also bypasses any Traefik-layer protections (rate limiting, CrowdSec bouncer, IP allow-lists). Access currently relies solely on Komodo's own `local_auth` setting (`config/core.config.toml`). This should be closed at some point but is helpful during initial deployment.