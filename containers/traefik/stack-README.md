# Initial Deployment Requirements
## Prerequisites for using traefik

# Create and Setup Required Folders
## Create needed folders for traefik

The log folder is mode 755 rather than group-writable. logrotate runs as root and refuses to rotate a file whose parent directory is writable by a group other than root, so it would exit 1 every five minutes and access.log would grow forever.
