# Linux worker image

The worker recipe pins its Python base by OCI digest and requires an HTTPS Redot archive plus its published SHA-256 at build time. It runs as numeric user `10001:10001`. The host command builder applies no network, read-only root/input, dropped capabilities, no-new-privileges, PID/CPU/memory limits, bounded tmpfs mounts, isolated HOME/XDG paths, no Docker socket, controlled output, and a read-only controller heartbeat.

The locally verified Redot 26.2 Linux archive inputs were:

```text
URL: https://github.com/Redot-Engine/redot-engine/releases/download/redot-26.2-stable/Redot_v26.2-stable_linux_x64.zip
SHA-256: f474d890806c41af15513cf5a8600243e241882e11b68dbb95660e3465b5b1e4
```

Build from trusted release inputs:

```console
docker build --file docker/Dockerfile.worker \
  --build-arg REDOT_URL=https://github.com/Redot-Engine/redot-engine/releases/download/redot-26.2-stable/Redot_v26.2-stable_linux_x64.zip \
  --build-arg REDOT_SHA256=f474d890806c41af15513cf5a8600243e241882e11b68dbb95660e3465b5b1e4 \
  --tag redot-compat-worker:0.1.0 .
docker image inspect redot-compat-worker:0.1.0 --format '{{json .RepoDigests}} {{.Id}}'
```

The final local evidence identity was `redot-compat-worker@sha256:3e7f1dcfa10a2fdafe5ffc44bd78ba623899b9add88fd0f7dc079dd83108c9d2`; it is not a registry publication. The in-image engine SHA-256 was `11d299e0f01a63574e612c64718ca3037a65540139dec7b93a87650ee9aab2f3`.

Building alone does not pass G-03. Every new image digest must repeat the write, network, identity, resource, teardown, descendant, and abrupt-controller scenarios before configuration or publication.
