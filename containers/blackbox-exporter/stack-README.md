# Initial Deployment Requirements
## Prerequisites for using blackbox-exporter

# Create and Setup Required Folders
## Create needed folders for blackbox-exporter

The config is copied from the tracked example only when it is not already there, so local edits are never overwritten.

Edit that copy to add or adjust probe modules. It is usable unchanged, defining probe modules and nothing host-specific.

Do all of this before the first deploy. Docker creates an empty directory in place of a missing bind-mount file, which makes blackbox-exporter fail at startup with nothing obvious to point at. The file lives here rather than in the repo checkout because Periphery re-clones over its run directory, which would take any file written inside it along with it.

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
