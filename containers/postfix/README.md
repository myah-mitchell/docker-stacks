# Initial Deployment Requirements
## How to include postfix in a stack

```yaml
services:
  postfix:
    extends:
      file: ../../containers/postfix/compose.yaml
      service: .postfix
```

Requires `mailpit` in the same stack, on the `backend` network, because every message is copied to it. Without it the copies wait in Postfix's deferred queue, and after five days Postfix gives up and sends a bounce to whoever sent the original.
