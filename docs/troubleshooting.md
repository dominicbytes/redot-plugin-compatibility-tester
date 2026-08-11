# Troubleshooting

## No plugin root detected

Confirm the package contains `addons/<id>/plugin.cfg`, a `.gdextension`, or an explicit test manifest. If several independent roots exist, select one with `--plugin-id`.

## Wrong release asset

Pin an exact tag or asset. The report records the resolved commit, asset identity, redirects, and independently calculated SHA-256.

## Missing native binary

Inspect `.gdextension` selectors and the worker platform. A Windows DLL cannot satisfy a Linux worker. Static findings never load the candidate library.

## .NET engine mismatch

Register an exact Redot Mono executable. The standard editor is not substituted merely because its help output contains `--build-solutions`. The retained optional gate uses the Mono archive's offline NuGet feed; an ordinary network restore is not part of that proof.

## Headless or display failure

Use the GUI-capable worker only for a manifest-approved display probe. `DISPLAY_REQUIRED` is a scoped result, not a compatibility failure.

## Docker unavailable

Check both `docker version` client and server output. Supply a registry/local `repository@sha256:<digest>` identity and the SHA-256 of `/opt/redot/redot`; a mutable tag is rejected. The tester does not silently fall back to unsafe host execution. A newly rebuilt image has a new digest and must pass G-03 before use.

## Godot control unavailable

Pass an exact compatible binary with `--godot-control`. The bundled Godot 4.5.0 JSON is reference-only and never substitutes for a Godot 4.5.2 control. The command rejects a control whose compatibility version does not exactly match Redot's recorded lineage.

## Warning, timeout, or crash

Review the retained phase logs and first decisive finding. A warning needs a reviewed, scoped, expiring allowlist rule. Timeouts and crashes remain results; limits are not silently extended.
