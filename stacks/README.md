# Stack Information and Overview

## Traefik Based Stacks

For each server you will start one of the follwoing stacks, only one should be ran per server as the have overlaping services.

**Traefik Stack (Basic)** The `traefik-basic\compose.yaml` will start up a basic Traefik stack without Traefik-kop support. This is a working Traefik stack with a socket-proxy and custom error pages.

**Traefik-kop Central Stack (Server)** The `traefik-server\compose.yaml` will start up a Traefik stack with Traefik-kop and a password protected Redis server that all Traefik-kop services can write too. This server will need to allow inbound 6379 (Redis) and then port 80/443 (HTTP/HTTPS). This compose file should only be deployed to one server. 

**Traefik-kop Stack (Agent)** The `traefik-agent\compose.yaml` will start up a Traefik stack with Traefik-kop. This server will only need port 80/443 (HTTP/HTTPS) inbound open. This server will need port 6379 (Redis) outbound open to talk to the `traefik-server` stack. This compose file can be ran on as many servers as you would like. Each server just needs to be able to acces the Redis server (6379 outbound) and be accessed by the DMZ servers (443 inbound). 

**Bastion Host Stack (DMZ)** The `traefik-dmz\compose.yaml` will start up a Traefik stack that is configured to have Redis replicate data from the server stack. Then using a Traefik provider add routers and services from Redis to the proxy config. This stack is intended to be used on the edge of your network in a heavily restricted DMZ network. Only Port 443 (HTTPS) to your internal Traefik servers, and port 6379 (Redis) to the server running `traefik-server` need to be opened out of the DMZ. This compose file can be deployed to one or more servers in the DMZ. This is your HTTP/HTTPS Bastion host.
* Note: For this to work the _TRAEFIK_EXTRA_COMMAND_ Env Var must be set to **"--providers.redis.endpoints=redis:6379"**. This will enable Traefik to load labels out of the local Redis database.


