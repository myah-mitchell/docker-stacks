# Initial Deployment Requirements
## Prerequisites for using blackbox-exporter

# Create and Setup Required Folders
## Create needed folders for blackbox-exporter

```bash
mkdir -p /opt/docker/stacks/$projectName/blackbox-exporter/config
```

Copy `config/blackbox.yml.example` to `config/blackbox.yml` (or edit in place) to add/adjust probe modules.

## vmagent scrape config

blackbox_exporter is a multi-target proxy — vmagent needs a scrape job with `relabel_configs` rewriting the target into a `/probe` query param. Example addition to `vmagent`'s `prometheus.yml`:

```yaml
- job_name: 'blackbox-http'
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - https://vaultwarden.example.com
        - https://ntfy.example.com
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: blackbox-exporter:9115
```

Pair with a `vmalert` rule (`probe_success == 0`) notifying through `ntfy` (Phase 2) — this is the "is it actually up" signal Icinga used to provide.
