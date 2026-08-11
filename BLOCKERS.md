# Blockers

No active blocker remains for the implemented `0.1.0` alpha scope. The five preflight blockers were resolved locally on 2026-08-10; reproducible identities and capture locations are summarized in [gate closure evidence](docs/gamedev/references/gate-closure-evidence.md).

## Resolved preflight blockers

### BLOCK-0001: Redot 26.2 fresh extension API dump crashed — resolved

The failure belonged to the earlier local installation. A clean extraction of the official Redot 26.2 Windows archive produced two isolated snapshots with identical SHA-256 `177E7796166929B2193C9CCE2FD32F59601A0147D0D1E7FE904B94E8F69F6577`. G-02 passed twice.

### BLOCK-0002: Exact Godot 4.5.2 control was unavailable — resolved

Godot `4.5.2.stable.official.6ce3de25a` was installed from its official Windows archive, hashed, doctored, and snapshotted twice. Its snapshot SHA-256 is `481ED7DC8EFC79E951081187CD5D651D6B34E2365A463F4F12ADEAB2F63475C8`. G-05 passed twice with real PASS/PASS and Redot-only API-gap fixtures plus the complete classification matrix.

### BLOCK-0003: Docker daemon was unavailable — resolved

Docker Desktop answered through engine `29.2.1`. The final local worker identity is `redot-compat-worker@sha256:3e7f1dcfa10a2fdafe5ffc44bd78ba623899b9add88fd0f7dc079dd83108c9d2`. The image is a local evidence identity, not a claim that it has been pushed to a registry.

### BLOCK-0004: Redot 26.2 Mono was unavailable — resolved

The official Mono archive and a portable .NET 8.0.423 SDK were retained by digest. A trusted C# fixture restored from the archive's offline NuGet feed, built, and ran without errors or warnings in two consecutive clean runs.

### BLOCK-0005: Process/container containment was unproven — resolved

Windows now assigns a package-owned waiting launcher to a kill-on-close Job Object before releasing the target command. The final Docker profile passed read-only root/input, output/home writes, no-network, no-socket, UID/GID, capabilities, seccomp, no-new-privileges, CPU, memory, PID, explicit teardown, and abrupt-controller watchdog scenarios twice.

## Remaining release limitations

These are intentionally retained scope limits, not regressions in the implemented alpha:

- G-01 still needs a canonical Linux CI capture rather than only local deterministic oracle runs.
- The complete G-04 export, GUI/display, native dependency, and platform fixture matrix is not implemented.
- No macOS result is claimed.
- G-06 and the full version 1.0 release audit remain open; package version stays `0.1.0` alpha.
- Publishing, remote creation, signing, and registry upload require separate owner authorization.
