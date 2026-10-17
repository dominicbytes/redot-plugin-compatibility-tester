# Linux worker image

The multi-stage worker pins both Python stages by OCI digest. Only the download stage installs `curl` and `unzip`; the final image contains the engine, runtime libraries, and hash-locked Python dependencies. It runs as numeric user `10001:10001`.

The default engine is Redot **26.3-stable**, from release tag `redot-26.3-stable`:

```text
URL: https://github.com/Redot-Engine/redot-engine/releases/download/redot-26.3-stable/Redot_v26.3-stable_linux_x64.zip
SHA-512: d370f50a85efa1c62549743c9c55f56fdac3f4ea66f353bfa3135d4c4fe68ef47849db7ce5d37b6ab9b09c5aa6ee748e10f44dc2c55485f3e799f5dfe2344166
Archive member: redot.linuxbsd.editor.x86_64
```

The public archive was downloaded into a fresh directory outside the repository, verified against the official SHA-512, and listed without executing the binary. The archive contains exactly the member shown above. The build verifies the archive with `sha512sum -c`, requires exactly one occurrence of that exact member, and installs it as `/opt/redot/redot`. A generated SHA-256 manifest verifies the binary after copying it into the final stage.

Build from the verified defaults, or explicitly supply both version and matching archive digest:

```console
docker build --file docker/Dockerfile.worker \
  --build-arg REDOT_VERSION=26.3-stable \
  --build-arg REDOT_SHA512=d370f50a85efa1c62549743c9c55f56fdac3f4ea66f353bfa3135d4c4fe68ef47849db7ce5d37b6ab9b09c5aa6ee748e10f44dc2c55485f3e799f5dfe2344166 \
  --tag redot-compat-worker:0.1.0 .
docker image inspect redot-compat-worker:0.1.0 --format '{{json .RepoDigests}} {{.Id}}'
```

Configure the controller with the resulting immutable image identity and the SHA-256 of `/opt/redot/redot`. The host command builder applies no network, read-only root/input, dropped capabilities, no-new-privileges, PID/CPU/memory limits, bounded tmpfs mounts, isolated HOME/XDG paths, no Docker socket, controlled output, and a read-only controller heartbeat.

Building alone does not pass G-03. Every new image digest must repeat the write, network, identity, resource, teardown, descendant, and abrupt-controller scenarios before configuration or publication. The old 26.2 image evidence does not validate this 26.3 recipe.
