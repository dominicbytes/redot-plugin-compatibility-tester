# Sandboxing and containment

Static `inspect` does not execute package content. Dynamic testing is a separate trust and backend decision.

## Docker Linux backend

Docker mode is eligible only when the operator supplies both `--worker-image repository@sha256:<digest>` and `--worker-engine-sha256 <digest>`, and the daemon answers. `auto` may select that eligible worker but never falls back to host.

The fixed profile runs as numeric user `10001:10001` with no network, read-only root and input, all capabilities dropped, `no-new-privileges`, default seccomp filtering, 256 PIDs, two CPUs, four GiB of memory, one-GiB tmpfs mounts, isolated HOME/XDG directories, no Docker socket, and one controlled output bind. Candidate input is not reachable through the writable output mount. A read-only heartbeat bind lets the worker stop after abrupt controller loss; the owned `--rm` container is also explicitly removed on every normal terminal path.

G-03 exercised root/input/output/home writes, network, identity, capabilities, seccomp, quotas, descendants, normal teardown, and controller death twice against the recorded final image identity. Building another image creates a new identity and requires the gate again.

Docker reduces risk but is not a universal security boundary. Kernel, daemon, profile, image, or mount defects remain possible. Intentionally hostile native code should run in a disposable VM or remote worker.

## Trusted host backend

Host mode accepts repository-owned or operator-designated trusted content only and requires `--trusted-source`, explicit `--backend host`, and `--allow-unsafe-host-execution`. Each run owns isolated user/config/cache/temp roots and uses argument arrays, bounded logs/time, and full process-family ownership.

On Windows, a trusted package-owned launcher waits without starting the target command. The launcher is assigned to a kill-on-close Job Object, then receives and starts the target; descendants inherit ownership. Closing the controller handle kills the family, while psutil remains confirmation/fallback. POSIX uses a new process session/group. G-03 verified timeout and abrupt-controller teardown twice.

Host controls do **not** restrict filesystem or network access. That is why host mode remains trusted-only even though its process ownership gate is green.

## Platform limits

Linux results are Linux-scoped. Windows results are Windows-scoped. No macOS claim exists without a macOS worker. Native selectors and missing binaries are reported per worker platform.
