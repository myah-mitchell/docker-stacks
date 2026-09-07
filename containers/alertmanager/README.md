# Initial Deployment Requirements
## How to include alertmanager in a stack

```yaml
services:
  alertmanager:
    extends:
      file: ../../containers/alertmanager/compose.yaml
      service: .alertmanager
```

## Alert routing is unconfigured by default
`config/alertmanager.yml` ships with `route.receiver: blackhole` and no other receivers defined. As shipped, every alert Alertmanager receives is silently discarded. Nothing is emailed, or posted to Slack, a webhook, ntfy, or anywhere else. Before relying on this stack for real alerting, edit `config/alertmanager.yml` to add a receiver (e.g. `email_configs`, `slack_configs`, `webhook_configs`) and update `route.receiver` to point at it.