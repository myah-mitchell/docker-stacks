# Stack Information and Overview

## Dozzle Based Stacks

### Dozzle Stack (Server) Overview

This will start up a Dozzle stack with an instance of Dozzle running as a server to connect to instances of Dozzle running in agent mode. This will also start up a local Dozzle agent instance so you do not need to also start the Dozzle Agent stack on the same server as this. This server will need access to all other servers running Dozzle on port 7007. This compose file should only be ran once per server but can ran on as many servers as you would like as there is no interferance with multiple servers running.

### Dozzle Stack (Agent) Overview

This will start up a Dozzle stack with Dozzle running in agent mode collecting logs. This server will only need port 7007 inbound open for the Dozzle server to connect to this agent on. This compose file should only be ran once per server but can ran on as many servers as you would like.

## Traefik Based Stacks

For each server you will start one of the following stacks. Only one should be run per server as they have overlapping services.

### Traefik Stack (Basic) Overview

The `stacks\traefik-basic\compose.yaml` will start up a basic Traefik stack without Traefik-kop support or any monitoring/log collection. This is a working Traefik stack with a socket-proxy, custom error pages, and access log rotation.

### Traefik Stack (Monitored) Overview

The `stacks\traefik-monitored\compose.yaml` will start up a basic Traefik stack with monitoring and log collection but without Traefik-kop support. This is a working Traefik stack with a socket-proxy, custom error pages, access log rotation, vlagent, vmagent, and vector.

### Traefik-kop Central Stack (Server) Overview

The `stacks\traefik-server\compose.yaml` will start up a Traefik stack with Traefik-kop and a password-protected Redis server that all Traefik-kop services can write to. This server will need to allow inbound 6379 (Redis) and then port 80/443 (HTTP/HTTPS). This compose file should only be deployed to one server.

### Traefik-kop Stack (Agent) Overview

The `stacks\traefik-agent\compose.yaml` will start up a Traefik stack with Traefik-kop. This server will only need port 80/443 (HTTP/HTTPS) inbound open. This server will need port 6379 (Redis) outbound open to talk to the `traefik-server` stack. This compose file can be run on as many servers as you would like. Each server just needs to be able to access the Redis server (6379 outbound) and be accessed by the DMZ servers (443 inbound).

### Bastion Host Stack (DMZ) Overview

The `stacks\traefik-dmz\compose.yaml` will start up a Traefik stack that is configured to have Redis replicate data from the server stack. Then using a Traefik provider add routers and services from Redis to the proxy config. This stack is intended to be used on the edge of your network in a heavily restricted DMZ network. Only Port 443 (HTTPS) to your internal Traefik servers, and port 6379 (Redis) to the server running `traefik-server` need to be opened out of the DMZ. This compose file can be deployed to one or more servers in the DMZ. This is your HTTP/HTTPS Bastion host.

* Note: For this to work the _TRAEFIK_EXTRA_COMMAND_ Env Var must be set to **"--providers.redis.endpoints=redis:6379"**. This will enable Traefik to load labels out of the local Redis database.