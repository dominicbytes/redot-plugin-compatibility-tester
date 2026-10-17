# Security policy

## Execution warning

Redot/Godot plugins are arbitrary code. An editor plugin can read and write files, start processes, access the network, load native libraries, or consume resources with the same rights as the engine process.

- `inspect` is static-only and must never execute package content.
- Docker materially reduces exposure, but it is **not a universal security boundary** against hostile native code, daemon defects, mount mistakes, or kernel exploits.
- Trusted host mode is process containment, not a sandbox. It refuses dynamic work without a trusted-source designation and explicit consent through `--allow-unsafe-host-execution`.
- Windows host processes are released only after a package-owned launcher is assigned to a kill-on-close Job Object. This owns descendants but does not restrict their filesystem or network rights.
- The Docker worker requires an immutable image identity and expected in-image Redot hash. A read-only controller heartbeat stops/removes the container after abrupt host-controller loss.
- Never expose normal credentials, editor state, source checkouts, the Docker socket, or broad writable mounts to a dynamic run.
- Intentionally hostile native submissions require a disposable VM or remote worker outside the version 0.1 threat model.

## Harness event authentication

Each phase gets a freshly generated 32-byte random session key in a disposable `harness.json` containing the run ID, selected plugin ID, mode, and declarative probes. The only harness environment variable is `REDOT_COMPAT_HARNESS_JSON`, containing its path. The runtime/editor harness reads and best-effort deletes this file before invoking plugin activation or declarative probes. Import mode waits for the editor filesystem scan to finish before reporting success.

Protocol v2 emits `REDOT_COMPAT_EVENT <hmac_sha256_hex> <json>`. The MAC covers the exact UTF-8 JSON bytes; the host uses constant-time comparison and validates schema, run ID, sequencing, and terminal evidence. An unauthenticated event makes the result `INCONCLUSIVE` with `HARNESS_EVENT_UNAUTHENTICATED` and action `REVIEW_PACKAGE_TAMPERING`, never a claimed pass or a port recommendation. Normal exit without terminal evidence is `HARNESS_INCOMPLETE`. Authenticated tester/configuration corruption remains a tester error. Truncated logs require a new run with a higher retained log limit (`RAISE_LOG_LIMIT`).

This MAC raises the bar for forged console output; it is not a sandbox boundary. Code shares the engine process and could in principle recover the key from memory, intercept harness operations, or read configuration before deletion (including during engine script loading). Best-effort deletion can also fail. Host filesystem and process access remain governed by the chosen execution backend. A hostile plugin with a stolen key can forge authenticated evidence; native-code isolation still requires a disposable VM or remote worker.

Engine canaries distinguish reproducible baseline diagnostics and shutdown crashes from plugin evidence. Editor canaries activate a shipped no-op addon through the normal enable/check path. All canary logs and original plugin exit codes are retained. If an error-free authenticated terminal pass is followed by a crash that up to three canaries do not reproduce, at most two additional same-phase plugin attempts may run in fresh isolated projects/state. A clean authenticated exit-0 pass can yield a reviewed intermittent-crash warning and medium confidence; all raw attempts remain in `phase_retry_attempts`. Pre-pass crashes, error findings, incomplete or unauthenticated output, protocol failures, and timeouts are never retried into success. Repeated crashes remain failures. Neither baseline matching nor an intermittent retry pass proves engine causation or package safety; this rule does not weaken the trust/containment gate.

## Supported versions

Security fixes are applied to the latest released version and the default branch. No stable release exists yet.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for `dominicbytes/redot-plugin-compatibility-tester` after the repository is published. Before publication, contact the repository owner privately. Do not include live tokens, private plugin source, or exploit payloads in public issues.

Include the tester version, operating system, source kind, exact reproduction steps, expected containment boundary, actual effect, and sanitized evidence paths. The project will acknowledge a report, reproduce it against a trusted fixture, and suspend affected dynamic recommendations until a fix passes the relevant Gauntlet.

## Scope boundaries

- No claim is made for macOS without a macOS worker.
- The default container profile is Linux x86-64 only.
- The standard Redot editor is not treated as .NET-capable. The optional local .NET gate used the separately hashed official Redot 26.2 Mono build and an offline .NET 8.0.423 fixture.
- A process exit without schema-valid terminal harness evidence is not success.
