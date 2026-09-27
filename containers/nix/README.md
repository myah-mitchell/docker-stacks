# Initial Deployment Requirements

## How to include nix in a stack

nix fills a folder with a working nix and exits. The container that runs nix mounts the same folder at `/nix` and waits for it:

```yaml
services:
  nix:
    extends:
      file: ../../containers/nix/compose.yaml
      service: .nix

  imageName:
    extends:
      file: ../../containers/imageName/compose.yaml
      service: .imageName
    volumes:
      - ${DOCKER_VOLUMES}/${PROJECT_NAME}/nix-data:/nix
    depends_on:
      nix:
        condition: service_completed_successfully
```

Declare `nix-data` in the `setup.yaml` of the container that runs nix, owned by the host ID of the user that container runs as. nix hands the folder's contents to the folder's owner, so that is the one place the user is named.
