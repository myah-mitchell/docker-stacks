# Dozzle Stack (Server) Overview

This will start up a Dozzle stack with an instance of Dozzle running as a server to connect to instances of Dozzle running in agent mode. It runs no agent of its own and reads no Docker socket. Every host it shows, its own included, is an agent named in `DOZZLE_REMOTE_AGENT`, which system-agent runs on each VM. This server will need access to every server running a Dozzle agent on port 7007. This compose file should only be ran once per server but can ran on as many servers as you would like as there is no interferance with multiple servers running.
