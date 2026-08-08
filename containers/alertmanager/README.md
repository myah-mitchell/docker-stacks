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
`config/alertmanager.yml` ships with `route.receiver: blackhole` and no other receivers defined. As-is, **every alert Alertmanager receives is silently discarded** nothing is emailed, posted to Slack/webhook/ntfy/etc. Before relying on this stack for real alerting, edit `config/alertmanager.yml` to add a receiver (e.g. `email_configs`, `slack_configs`, `webhook_configs`) and update `route.receiver` to point at it.