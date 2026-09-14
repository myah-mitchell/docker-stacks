# Initial Deployment Requirements
## How to include mailpit in a stack

```yaml
services:
  mailpit:
    extends:
      file: ../../containers/mailpit/compose.yaml
      service: .mailpit
```

On its own, Mailpit only catches whatever is sent to its SMTP port. In core-infra it sits next to `postfix`, which sends it a copy of everything it relays.
