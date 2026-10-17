# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [Unreleased]

### Added

- `inspect`, `test`, `doctor`, `api index`, `api diff`, `batch`, `report`, version, and schema commands.
- Safe local/archive/HTTPS/GitHub/Codeberg acquisition with immutable provenance and hostile ZIP/TAR rejection.
- Static package/native/version inventory and the Godot 4.5.2 baseline policy.
- Isolated trusted-host runner, typed Redot editor/runtime harnesses, declarative manifests, strict sentinel parsing, ordered classification, and hash-checking reproduction scripts.
- Content-addressed cache primitive and resumable static batch reports.
- Digest-pinned Linux worker backend with fixed containment profile, verified engine hash, host-path artifact translation, and controller-loss heartbeat teardown.
- Clean, deterministic Redot 26.2 and exact Godot 4.5.2 API snapshot command and G-02 evidence.
- Exact-control host differential execution with complete G-05 outcome/precedence coverage and a real post-baseline API-gap fixture.
- Kill-on-close Windows Job Object ownership before target execution.
- Optional exact Redot 26.2 Mono/.NET 8 offline build-and-run fixture.
- MIT/community files, pinned read-only CI, trusted manual integration workflow, and non-publishing release dry run.
- Wheel/sdist, clean-install smoke, dependency/license inventory, vulnerability audit, SPDX SBOM, and checksums for the alpha dry run.

### Changed

- Preserve authenticated pre-shutdown failure evidence when Redot or its exact Godot control crashes after terminal pass/fail: retry even with API errors, use a non-crashing retry's result, or derive PASS/FAIL after exhausted post-terminal crashes with medium confidence and retained raw attempts.

- Exercise no-op addon activation in editor canaries and retry eligible post-pass shutdown crashes at most twice; retain raw attempts, report intermittent recovery at medium confidence, and keep pre-pass or deterministic crashes decisive.
- Forward configured `[limits]` (also `[archive]`) quotas through inspect/test/batch, local and remote acquisition, and Docker workers; invalidate batch resume when limits change.
- Accept both verified Redot 26.2 console and 26.3 LLVM console hashes in the real differential oracle.

- Support Redot 26.3-stable with an explicit Redot/Godot lineage table; doctor cross-checks the extension API header against binary identity. Both Redot 26.2 and 26.3 track Godot 4.5.2.
- Attribute the official Redot 26.3 headless shutdown crash and leak-at-exit diagnostics through engine-only canary phases instead of blaming plugins.
- Authenticate harness protocol v2 events with HMAC, detect crashes, and preserve NOT_COMPARABLE differential outcomes.
- Classify Godot 3 packages as PORT_REQUIRED_MAJOR_UPGRADE, never policy-skip .NET Godot SDK evidence, honor GDExtension compatibility_maximum, and scope version evidence to the selected plugin.
- Sanitize Markdown reports and omit untrusted free-form text from agent port briefs; derive target identity from the tested engine and harden PowerShell reproduction quoting.
- Return exit code 2 for usage/configuration errors; load CLI TOML configuration and support GITHUB_TOKEN/CODEBERG_TOKEN source credentials.
- Fingerprint batch items for safe resume, atomically replace reports, and derive batch exit codes from item classifications, errors, and incomplete execution.
- Harden source acquisition with HTTPS-only redirects, cross-origin token stripping, clear rate-limit messages, and archive entry-name validation.
- Kill POSIX process groups and enforce Docker no-swap memory limits and output quotas; default the Docker worker to Redot 26.3-stable.
- Expand the CI matrix, integration checks, and Dependabot coverage.
