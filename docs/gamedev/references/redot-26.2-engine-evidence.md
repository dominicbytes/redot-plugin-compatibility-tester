# Redot 26.2 local engine evidence

Captured: 2026-08-10  
Host: Windows x86-64  
Configured path source: `D:/Claude Vault/redot/.codex/redot.env`

## Identity and hashes

`REDOT_BIN` resolves to:

```text
D:/Claude Vault/redot/.tools/redot/26.2-stable-windows/redot.windows.editor.x86_64.console.exe
```

The configured command reports:

```text
26.2.stable.official.4f5b14aba
```

The official Git tag resolves to the full commit `4f5b14abade2239104847d03d8f9056e4467cfcd`.

| Local file | Bytes | Local SHA-256 |
|---|---:|---|
| `redot.windows.editor.x86_64.console.exe` | 104,448 | `5633D02A28A73514084DF6A60FFE01FABDBBB9AC5E28FDFD590ED47277F51989` |
| `redot.windows.editor.x86_64.exe` | 164,860,928 | `10DFBEFC273536F0C65903D6429E531C30133820BF0FA842F2D6E6FB81DB1D42` |
| `Redot_v26.2-stable_export_templates.tpz` | 1,293,241,685 | `FA8C648BD9A9D911DAFFBCC4E1786D0248794571A7E4ED954444197C809079EA` |

The export-template hash matches the digest published in the [official Redot 26.2 GitHub release](https://github.com/Redot-Engine/redot-engine/releases/tag/redot-26.2-stable). The extracted editor executables have local hashes, but the original Windows ZIP was not retained, so this preflight cannot directly match the extracted executable hashes to the published archive digest.

Relevant official release assets:

| Asset | Published SHA-256 digest |
|---|---|
| `Redot_v26.2-stable_windows_win64.zip` | `4644c7591bbe8019b861deb0ccdb64fd4f59a88514abf7c788cf176c259855af` |
| `Redot_v26.2-stable_windows_mono_win64.zip` | `5da9e073b10db3022d4fef069405fe975dd0514878bb2fb67cdbcc6ce61247a4` |
| `Redot_v26.2-stable_export_templates.tpz` | `fa8c648bd9a9d911daffbcc4e1786d0248794571a7e4ed954444197c809079ea` |

## Dual version identity

The tagged [`version.py`](https://raw.githubusercontent.com/Redot-Engine/redot-engine/redot-26.2-stable/version.py) declares:

```text
product: Redot 26.2 stable
Godot compatibility lineage: 4.5.2 stable
```

This supports retaining both fields in every result. It does not, by itself, prove that every plugin targeting Godot 4.5.2 behaves correctly in Redot; the plan's baseline skip remains an explicit project policy.

## Command capability check

The installed build's own `--help` output contains every flag required by the proposed doctor contract:

```text
--editor
--headless
--path
--quit
--quit-after
--script
--check-only
--import
--build-solutions
--dump-extension-api
--validate-extension-api
```

The presence of `--build-solutions` does not prove that this non-Mono editor can build a C# project. A separate Redot Mono executable must be registered and exercised before claiming .NET capability.

## API snapshots

The workspace cache at `D:/Claude Vault/redot/.codex/cache/redot-extension-api.json` has:

```text
bytes: 6,666,639
sha256: 177E7796166929B2193C9CCE2FD32F59601A0147D0D1E7FE904B94E8F69F6577
header: Godot Engine v4.5.2.stable.redot.official
precision: single
```

The tagged Redot C++ bindings snapshot copied into this bundle has:

```text
bytes: 6,666,655
sha256: 453A0CC128BB58333A001F7F43573A5961D973FB7B151AF43139869F22D5915C
header: Godot Engine v4.5.2.stable.redot.custom_build
precision: single
classes: 993
built-in classes: 38
utility functions: 125
global enums: 22
singletons: 39
native structures: 14
```

A canonicalized section-by-section comparison found the two snapshots identical for built-in sizes, built-in offsets, global enums, utility functions, built-in classes, engine classes, singletons, and native structures. The only observed header differences were `version_build` and `version_full_name` (`redot.official` versus `redot.custom_build`).

The tagged snapshot contains:

- `EditorInterface.set_plugin_enabled()`;
- `EditorInterface.is_plugin_enabled()`;
- `GDExtensionManager.load_extension()`;
- `GDExtensionManager.reload_extension()`;
- `GDExtensionManager.unload_extension()`.

These establish API presence for harness design. Runtime behavior still requires trusted-fixture tests.

## Fresh dump attempts

Two bounded attempts were made with the configured Redot binary. No `-d` flag was used.

Attempt 1:

```text
working directory: D:/Claude Vault/redot/plugins/compatester/.preflight-work/redot-api-dump
arguments: --headless --dump-extension-api --quit-after 2
result: engine crash handler reported signal 11 after "Dumping Extension API"; no extension_api.json produced
```

Attempt 2:

```text
working directory: D:/Claude Vault/redot/plugins/compatester/.preflight-work/redot-api-dump-windowed
arguments: --dump-extension-api --quit-after 2
result: native exit -1073741819; engine crash handler reported signal 11; no extension_api.json produced
```

The trace identified Redot 26.2 commit `4f5b14abade2239104847d03d8f9056e4467cfcd` and noted that debug symbols were unavailable. A bounded issue search did not identify a matching published Redot issue. No further retries were made.

## Consequence

At preflight, the official tagged snapshot was sufficient only for deterministic schema, indexing, and unit-test work. The then-configured editor did not satisfy the planned Milestone 2 doctor gate because it could not generate a fresh dump.

## Resolution — 2026-08-10

The failure did not reproduce from a new extraction of the official Windows archive. The retained archive matched the published SHA-256 `4644C7591BBE8019B861DEB0CCDB64FD4F59A88514ABF7C788CF176C259855AF`; its console executable matched SHA-256 `5633D02A28A73514084DF6A60FFE01FABDBBB9AC5E28FDFD590ED47277F51989`. Two bounded runs from separate empty engine-state and work directories produced byte-identical snapshots with SHA-256 `177E7796166929B2193C9CCE2FD32F59601A0147D0D1E7FE904B94E8F69F6577`.

G-02 therefore passes for the verified clean installation. The original crash remains retained evidence about the previous installation; it is not silently ignored or used as current engine provenance. Full commands and capture roots are recorded in [`gate-closure-evidence.md`](gate-closure-evidence.md).
