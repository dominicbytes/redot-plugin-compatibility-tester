# Compatester research query log

Search date: 2026-08-10

This is a bounded search ledger, not a claim of exhaustive internet coverage. Primary project documentation, tagged source, package registries, and installed engine output were preferred over summaries.

| ID | Query or inspection | Result | Disposition |
|---|---|---|---|
| Q-001 | Redot 26.2 release, tag, version metadata, and local `--version` | Product `26.2`; Godot lineage `4.5.2`; tag commit and local short commit agree. | Adopt |
| Q-002 | Redot 26.2 extension API snapshot and installed API cache | Official tagged JSON obtained. Tagged and cached API bodies are structurally identical in every compared section; build labels differ. | Adopt with provenance labels |
| Q-003 | Fresh `--dump-extension-api` from configured Redot | Both bounded headless and windowed attempts crashed with signal 11 and produced no file. | Unresolved blocker for Milestone 2 |
| Q-004 | Editor plugin activation APIs | Tagged Redot API and Godot 4.5 docs expose `set_plugin_enabled` and `is_plugin_enabled`. | Adopt; runtime-test later |
| Q-005 | Redot `.gdextension` format | Confirms entry symbol, compatibility bounds, library selector ordering, dependencies, and reload caveats. | Adopt |
| Q-006 | Exact Redot C++ bindings for 26.2 | `redot-cpp` tag `redot-26.2-stable` exists at commit `598ec78e86b2c240a023f6de13daba70f7de8610`; repository advises exact matching tags. | Adopt |
| Q-007 | Redot–Rust compatibility layer | Searches for an official or maintained shared Redot–Rust layer returned no credible project. godot-rust itself supports `api-custom-json` with `GDRUST_GODOT_API_JSON`. | Reject the assumed shared layer; Adapt godot-rust experimentally |
| Q-008 | Godot.NET.Sdk version evidence | NuGet publishes `Godot.NET.Sdk` 4.5.0 under MIT; Redot publishes a distinct 26.2 Mono archive. | Adopt as evidence, not proof of local capability |
| Q-009 | GitHub immutable acquisition and asset digests | REST supports fixed-ref archives and release assets; release assets may include SHA-256 digests. A tag name must still be resolved to a full commit. | Adopt |
| Q-010 | Codeberg/Forgejo API stability | Forgejo documents that its API may break across major versions and exposes per-instance OpenAPI. Codeberg release attachments differ from generated source archives. | Adapt with capability/version probing |
| Q-011 | Legacy Godot Asset Library metadata | API exposes one `godot_version`; patch filtering is disregarded; `download_hash` is always empty in the official service. | Adapt; metadata is corroborating evidence only |
| Q-012 | Godot Asset Store acquisition | Store is beta and its implementation/API is not public like the legacy library; public listings use varied licenses. | Metadata-only; require public source/archive and explicit license |
| Q-013 | Python 3.12 TAR safety | Default behavior is not the safe `data` policy in Python 3.12; explicit `filter="data"` is required and partial extraction remains possible on error. | Adopt as defense in depth plus manual limits |
| Q-014 | Python 3.12 ZIP safety | `extract()` sanitizes some names, while `zipfile.Path` does not; caller must validate paths and hostile archive properties. | Adopt manual preflight; reject `zipfile.Path` extraction |
| Q-015 | Docker isolation limits | Network is on and mounts are writable by default; daemon access and bind mounts remain security-sensitive. | Adapt with digest pinning, non-root identity, rootless/userns, quotas, and stronger isolation for hostile native code |
| Q-016 | Windows complete process-tree termination | Job Objects can group descendants and `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` terminates the job when the handle closes. `subprocess` timeout alone does not establish descendant termination. | Adopt Job Objects; use psutil for telemetry/fallback |
| Q-017 | Existing end-to-end Godot/Redot plugin compatibility tester | Queries for “Godot plugin compatibility checker”, “addon compatibility tester”, “extension_api.json diff”, and Redot equivalents found no direct end-to-end match. | Unresolved; do not claim none exists |
| Q-018 | `godot-ci` | Maintained MIT Docker/CI packaging reference, but designed for trusted game export rather than hostile plugin execution. | Inspiration only |
| Q-019 | GDScript Toolkit | Maintained MIT parser/linter/formatter independent of the engine. It can lag engine grammar and cannot prove runtime/API compatibility. | Reject as core; optional advisory only |
| Q-020 | GUT | Maintained MIT Godot unit-test framework with engine-version matrix. Generic use would execute plugin tests and add a dependency. | Reject as generic harness; inspiration for CLI/JUnit output |
| Q-021 | Python orchestrator dependencies | Core and development libraries have permissive licenses; godot-rust is MPL-2.0. Exact versions and transitives are not yet locked. | Conditional adopt; lockfile, SBOM, and license scan required |
| Q-022 | Official Godot 4.5.2 committed API JSON | No exact 4.5.2 JSON was found in the tagged godot-cpp material; the available stable snapshot identifies 4.5.0. | Unresolved; included 4.5.0 only as clearly labeled reference |
| Q-023 | Matching public issue for Redot API-dump crash | Bounded Redot/GitHub issue search found no matching report. | Unresolved; reproduce from verified clean archive before filing |

## Key primary sources

- [Redot 26.2 stable release](https://github.com/Redot-Engine/redot-engine/releases/tag/redot-26.2-stable)
- [Redot 26.2 version metadata](https://raw.githubusercontent.com/Redot-Engine/redot-engine/redot-26.2-stable/version.py)
- [Redot C++ bindings](https://github.com/Redot-Engine/redot-cpp)
- [Godot editor plugin installation](https://docs.godotengine.org/en/4.5/tutorials/plugins/editor/installing_plugins.html)
- [Godot 4.5 EditorInterface](https://docs.godotengine.org/en/4.5/classes/class_editorinterface.html)
- [Godot Asset Library API](https://github.com/godotengine/godot-asset-library/blob/master/API.md)
- [Forgejo API usage](https://forgejo.org/docs/latest/user/api-usage/)
- [Python 3.12 tar extraction filters](https://docs.python.org/3.12/library/tarfile.html#extraction-filters)
- [Python 3.12 zipfile security notes](https://docs.python.org/3.12/library/zipfile.html)
- [Docker Engine security](https://docs.docker.com/engine/security/)
- [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [godot-rust version selection](https://godot-rust.github.io/book/toolchain/godot-version.html)
