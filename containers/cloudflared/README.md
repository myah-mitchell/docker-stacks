# Initial Deployment Requirements
## How to include cloudflared in a stack

```yaml
services:
  cloudflared:
    extends:
      file: ../../containers/cloudflared/compose.yaml
      service: .cloudflared
```

Belongs in the same stack as `traefik-dmz` (`stacks/traefik-dmz`) on the home DMZ VM — it needs to reach that stack's Traefik service over the `proxy` network by container name, which is exactly what `config.yml`'s ingress rules should point at (e.g. `http://traefik-dmz-traefik:80`), never a WAN port. No `socket-proxy` needed — cloudflared never talks to Docker.
