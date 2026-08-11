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
