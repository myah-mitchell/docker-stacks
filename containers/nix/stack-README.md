# Initial Deployment Requirements

## Prerequisites for using nix

nix runs one time for each deploy and exits. On the first deploy it copies `/nix` from its own image into `nix-data`, and hands the copy to the owner of that folder. On every later deploy it finds the folder filled and leaves it as it is.

The Komodo Stack has to list `nix` under `ignore_services`. Komodo otherwise reports the stack as unhealthy, because one of its services has exited.

The fill runs as the image's root, inside Docker's user namespace, and needs Docker's default capabilities, `CAP_CHOWN` and `CAP_DAC_OVERRIDE` among them, to write the folder and hand it over. Do not add `cap_drop: ALL` to this service.

The image tag sets the nix version of a new fill only. To move a filled folder to the image's version, stop the stack, empty `nix-data`, and deploy again.
