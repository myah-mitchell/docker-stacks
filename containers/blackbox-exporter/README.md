# Initial Deployment Requirements
## How to include blackbox-exporter in a stack

```yaml
services:
  blackbox-exporter:
    extends:
      file: ../../containers/blackbox-exporter/compose.yaml
      service: .blackbox-exporter
```

Add a scrape job to `vmagent`'s config pointing at this container's `/probe` endpoint with the target/module as query params (standard Prometheus blackbox_exporter multi-target pattern) — see `stack-README.md` for an example.
