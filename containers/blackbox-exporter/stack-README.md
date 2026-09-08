# Initial Deployment Requirements
## Prerequisites for using blackbox-exporter

# Create and Setup Required Folders
## Create needed folders for blackbox-exporter

The compose file mounts this config as `./config/blackbox.yml`, and that path is relative to `containers/blackbox-exporter/` rather than to the stack directory, because Compose resolves a relative bind mount against the file that declares it. So it belongs in this container's own `config/` folder, inside whichever checkout of this repo the stack runs from:

```bash
cp containers/blackbox-exporter/config/blackbox.yml.example \
   containers/blackbox-exporter/config/blackbox.yml
```

Edit that copy to add or adjust probe modules. Create it before the first start. Docker creates an empty directory in place of a missing bind-mount file, which makes blackbox-exporter fail at startup with nothing obvious to point at.

## vmagent scrape config

blackbox_exporter is a multi-target proxy, so vmagent needs a scrape job with `relabel_configs` rewriting the target into a `/probe` query param. Example addition to `vmagent`'s `prometheus.yml`:

```yaml
- job_name: 'blackbox-http'
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - https://vault.myah-mitchell.com
        - https://ntfy.home.myah-mitchell.com
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: blackbox-exporter:9115
```

Pair with a `vmalert` rule (`probe_success == 0`) notifying through `ntfy` (Phase 2). That is the "is it actually up" signal Icinga used to provide.
