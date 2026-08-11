# Redot Plugin Compatibility Tester

## Codex implementation plan

**Document version:** 1.0  
**Prepared:** 2026-08-10  
**Primary Redot target:** Redot 26.2 LTS stable  
**Redot compatibility lineage:** Godot 4.5.2  
**Primary development host:** Windows x86-64  
**Primary automated worker:** Linux x86-64 container  
**Repository name:** `redot-plugin-compat-tester`  
**Python package:** `redot_compat`  
**CLI command:** `redot-compat`  
**Recommended license:** MIT

---

# 1. Directive to Codex

Build a standalone compatibility-analysis system that determines whether a Godot plugin needs Redot-specific porting.

Do **not** implement the product as an ordinary in-editor plugin. Implement it as:

1. an external Python CLI orchestrator;
2. a small bundled Redot editor-plugin harness used only inside disposable test projects;
3. a small bundled Redot runtime harness;
4. one or more isolated execution backends;
5. versioned machine-readable and human-readable reports.

The external process must control Redot, capture its output, enforce timeouts, compare results against an optional Godot control run, and preserve enough evidence to reproduce every conclusion.

The tester is the gate in front of the Redot plugin-porting program. Its job is to prevent effort from being spent on plugins that already work.

---

# 2. Hard project policy

Treat the following as an authoritative project rule:

> Plugins whose effective Godot API/build target is Godot 4.5.2 or earlier do not require a Redot-specific port.

Therefore:

- The default compatibility baseline is `4.5.2`.
- A plugin should become a port candidate only when there is credible evidence that its current release targets an API newer than 4.5.2, or when its target version cannot be determined.
- Plugins at or below the baseline should be classified as `NO_PORT_NEEDED_BASELINE_POLICY` without consuming dynamic-test resources, unless the user passes `--force-test-baseline`.
- A plugin that claims an old minimum version but ships native binaries compiled for a newer API is **not** a baseline plugin. Track the native build API separately from the declared minimum version.
- Never treat a release date alone as proof that a plugin targets a newer engine API.

Redot 26.2 has two identities that the tester must preserve:

- product identity: Redot 26.2;
- compatibility/API lineage: Godot 4.5.2.

Never compare a plugin's Godot requirement directly against `26.2`. Compare it against the baseline `4.5.2` while retaining the Redot product identity in reports.

Authoritative references:

- Redot 26.2 stable release: https://github.com/Redot-Engine/redot-engine/releases/tag/redot-26.2-stable
- Redot version metadata: https://github.com/Redot-Engine/redot-engine/blob/redot-26.2-stable/version.py
- Redot extension API dump implementation: https://github.com/Redot-Engine/redot-engine/blob/redot-26.2-stable/core/extension/extension_api_dump.cpp
- Redot 2026 release announcements: https://blog.redotengine.org/2026/

---

# 3. Product goals

The tester must be able to:

1. Accept a plugin from:
   - a local directory;
   - a local ZIP or TAR archive;
   - a direct HTTPS archive URL;
   - a GitHub repository, tag, commit, or release asset;
   - a Codeberg repository, tag, commit, or release asset;
   - a Godot Asset Library asset ID or URL;
   - a Godot Asset Store URL when its public page exposes enough information; otherwise request a source URL or local archive.
2. Resolve the source to an immutable revision and record provenance.
3. Safely extract and normalize the package.
4. Detect whether it is:
   - a pure GDScript add-on;
   - an editor plugin;
   - a runtime library;
   - a C#/.NET plugin;
   - a C++ GDExtension;
   - a Rust GDExtension;
   - an engine module;
   - a mixed package;
   - a full project/template rather than an add-on.
5. Determine the best-supported estimate of the plugin's effective Godot API target.
6. Apply the 4.5.2 screening rule before executing plugin code.
7. Create a disposable Redot fixture project and install the plugin into it.
8. Run bounded phases for:
   - resource import;
   - script parsing;
   - editor-plugin activation;
   - runtime loading;
   - optional scene/resource probes;
   - optional export smoke tests.
9. Capture:
   - exit codes;
   - signals or crash status;
   - stdout and stderr;
   - Redot structured sentinel events;
   - engine identity and executable hashes;
   - imported-resource failures;
   - missing API errors;
   - missing native libraries or symbols;
   - hangs and timeouts;
   - unsupported-platform conditions.
10. Optionally run the same normalized package under a matching Godot binary as a control.
11. Distinguish:
    - a Redot incompatibility;
    - an upstream plugin defect;
    - a malformed package;
    - a missing build artifact;
    - a platform mismatch;
    - a missing credential/service;
    - an inconclusive result.
12. Produce:
    - `result.json`;
    - `report.md`;
    - optional `report.html`;
    - a compact `codex_port_brief.md` containing the exact evidence needed to begin a port;
    - reproduction scripts for PowerShell and Bash.
13. Run one plugin or a batch manifest.
14. Cache downloads and engine snapshots by SHA-256.
15. Never modify the user's original project or editor configuration.

---

# 4. Non-goals for the first release

Do not include the following in the MVP:

- automatic source-code modification;
- automatic publication of a fork or pull request;
- automatic compilation of arbitrary untrusted build scripts;
- a claim that generic loading proves every feature works;
- visual correctness testing for arbitrary editor interfaces;
- multiplayer, online-service, Steam, or credential-dependent tests without an explicit plugin test manifest;
- a public hosted service that executes arbitrary submissions;
- automatic Godot or Redot binary downloads unless checksums and release provenance are implemented correctly;
- social/adoption scoring such as stars, forks, reviews, or official citations.

A later release may add trusted build adapters and popularity ranking. Compatibility testing must remain independently usable.

---

# 5. Primary user stories

## 5.1 Screen a repository before porting

```powershell
redot-compat inspect https://github.com/example/plugin --ref v3.0.0
```

Expected output:

- detected plugin type;
- detected plugin IDs;
- version evidence;
- effective API target;
- baseline eligibility decision;
- whether dynamic testing is required.

## 5.2 Test a current GitHub release against Redot

```powershell
redot-compat test https://github.com/example/plugin `
  --release latest `
  --redot "$env:REDOT_BIN" `
  --sandbox auto
```

## 5.3 Test a Codeberg release asset

```powershell
redot-compat test https://codeberg.org/owner/repository `
  --release latest `
  --asset "*gdextension*.zip" `
  --redot "$env:REDOT_BIN"
```

## 5.4 Differential test with Godot as the control

```powershell
redot-compat test .\plugin.zip `
  --redot "$env:REDOT_BIN" `
  --godot-control "$env:GODOT_47_BIN" `
  --force-test-baseline
```

## 5.5 Test a batch

```powershell
redot-compat batch .\plugins.toml `
  --redot "$env:REDOT_BIN" `
  --output .\reports
```

## 5.6 Reproduce an earlier result

```powershell
redot-compat reproduce .\runs\20260810T120000Z-plugin-name\result.json
```

---

# 6. Compatibility result taxonomy

Use a stable enum. Do not invent free-form final statuses.

## 6.1 No-port statuses

| Code | Meaning |
|---|---|
| `NO_PORT_NEEDED_BASELINE_POLICY` | Authoritative evidence places the effective API/build target at Godot 4.5.2 or earlier. Dynamic testing was skipped by policy. |
| `COMPATIBLE_UNCHANGED` | Required dynamic phases pass under Redot without source or package changes. |
| `COMPATIBLE_REPACKAGE_ONLY` | Code works, but archive layout, manifest paths, or packaging must be normalized. No API port is required. |

## 6.2 Port-required statuses

| Code | Meaning |
|---|---|
| `PORT_REQUIRED_GDSCRIPT_API` | GDScript parses or runs in the Godot control but fails in Redot because of missing or changed APIs. |
| `PORT_REQUIRED_EDITOR_API` | Editor plugin activates in the Godot control but fails in Redot editor context. |
| `PORT_REQUIRED_RUNTIME_API` | Editor/import phases pass, but runtime functionality fails only in Redot. |
| `PORT_REQUIRED_NATIVE_REBUILD` | Source appears compatible, but bundled native binaries do not match Redot and need rebuilding against Redot bindings/API. |
| `PORT_REQUIRED_NATIVE_SOURCE` | Rebuilding is insufficient; native source changes are required. |
| `PORT_REQUIRED_RUST_BINDINGS` | Failure is attributable to Godot-Rust/Redot-Rust binding or API-generation compatibility. |
| `PORT_REQUIRED_ENGINE_MODULE` | Package is an engine module and cannot be tested or installed as a stock add-on. A custom Redot build is required. |
| `PORT_REQUIRED_EXPORT_PACKAGING` | Editor/runtime pass, but export packaging or target-library selection fails in Redot. |
| `ENGINE_API_GAP` | Plugin depends on an engine feature absent from Redot and no plugin-local adaptation is apparent. |

## 6.3 Invalid, unsupported, or inconclusive statuses

| Code | Meaning |
|---|---|
| `INVALID_PACKAGE` | Archive is malformed, unsafe, or has no usable plugin/project root. |
| `UPSTREAM_PACKAGE_FAILURE` | Package fails in both Redot and the matching Godot control. |
| `MISSING_PLATFORM_BINARY` | Native plugin has no binary for the worker platform. |
| `MISSING_BUILD_ARTIFACT` | Source package contains a GDExtension manifest but no required compiled library. |
| `MISSING_DOTNET_ENGINE` | C# plugin was tested with a non-.NET engine build. |
| `MISSING_EXTERNAL_SERVICE` | Steam, network, database server, hardware, credential, or similar dependency prevents a valid test. |
| `DISPLAY_REQUIRED` | Headless mode is insufficient and no GUI-capable worker was configured. |
| `TIMEOUT` | Plugin or engine exceeded the phase timeout. |
| `CRASHED` | Engine terminated abnormally. |
| `INCONCLUSIVE` | Evidence is insufficient or contradictory. |
| `INTERNAL_TESTER_ERROR` | The tester failed independently of the plugin. |

## 6.4 Confidence

Every result must also include:

- `confidence`: `high`, `medium`, or `low`;
- `confidence_reasons`: array of explicit reasons;
- `control_run_available`: boolean;
- `port_candidate`: boolean;
- `recommended_next_action`: stable code plus explanatory text.

A result should not be `high` confidence for a Redot-specific incompatibility unless the plugin passes a reasonably matching Godot control or there is direct native/API evidence that makes a control unnecessary.

---

# 7. Product architecture

```text
Source specification
        │
        ▼
Source adapter ──► immutable artifact + provenance
        │
        ▼
Safe extractor / normalizer
        │
        ▼
Static inventory + version evidence
        │
        ├── baseline <= 4.5.2 ──► NO_PORT_NEEDED_BASELINE_POLICY
        │
        ▼
Disposable fixture-project builder
        │
        ▼
Sandbox backend
        │
        ├── Redot import phase
        ├── Redot editor activation phase
        ├── Redot runtime phase
        ├── optional GUI phase
        └── optional export phase
        │
        ▼
Optional matching Godot control phases
        │
        ▼
Log parser + API-diff correlator
        │
        ▼
Deterministic classifier
        │
        ▼
JSON / Markdown / HTML / Codex brief
```

## 7.1 External orchestrator

Use Python 3.12 or newer.

Recommended libraries:

- Typer: https://typer.tiangolo.com/
- Rich: https://rich.readthedocs.io/
- Pydantic: https://docs.pydantic.dev/
- HTTPX: https://www.python-httpx.org/
- Packaging version parser: https://packaging.pypa.io/
- Platformdirs: https://platformdirs.readthedocs.io/
- psutil: https://psutil.readthedocs.io/
- pytest: https://docs.pytest.org/
- Ruff: https://docs.astral.sh/ruff/
- mypy: https://mypy.readthedocs.io/
- uv: https://docs.astral.sh/uv/

Use a lockfile. Do not rely on floating dependencies in CI.

## 7.2 Bundled Redot editor harness

Create an editor plugin named `_redot_compat_harness`. It must:

- be copied into every disposable fixture;
- be enabled alongside the target editor plugin;
- wait a configurable number of editor frames;
- check target activation state through `EditorInterface.is_plugin_enabled()`;
- execute manifest-defined generic checks;
- print JSON sentinel events to stdout;
- terminate the editor with a deterministic exit code;
- never remain installed in the plugin source.

Godot's `EditorInterface` provides `is_plugin_enabled()` and `set_plugin_enabled()`:

- https://docs.godotengine.org/en/4.5/classes/class_editorinterface.html

## 7.3 Bundled runtime harness

Create a minimal scene and script that can:

- load resources;
- load scripts;
- check classes and singletons;
- instantiate manifest-approved scenes or classes;
- wait a specified number of frames;
- run simple assertions;
- print JSON sentinel events;
- quit with success or failure.

## 7.4 Sandbox backend interface

Implement a backend abstraction with at least:

- `DockerLinuxBackend`;
- `TrustedHostBackend`.

Design interfaces for later:

- `WindowsVmBackend`;
- `MacOSVmBackend`;
- `RemoteWorkerBackend`.

`TrustedHostBackend` is process containment, not a security boundary. It must refuse untrusted execution unless the user explicitly passes `--allow-unsafe-host-execution`.

---

# 8. Repository layout

```text
redot-plugin-compat-tester/
├── README.md
├── LICENSE
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── TODO.md
├── DECISIONS.md
├── BLOCKERS.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── redot_compat/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── constants.py
│       ├── config.py
│       ├── errors.py
│       ├── models/
│       │   ├── engine.py
│       │   ├── source.py
│       │   ├── inventory.py
│       │   ├── phase.py
│       │   ├── finding.py
│       │   ├── result.py
│       │   └── manifest.py
│       ├── sources/
│       │   ├── base.py
│       │   ├── local.py
│       │   ├── http_archive.py
│       │   ├── github.py
│       │   ├── codeberg.py
│       │   ├── godot_asset_library.py
│       │   └── godot_asset_store.py
│       ├── archive/
│       │   ├── extract.py
│       │   ├── safety.py
│       │   └── hash.py
│       ├── inspect/
│       │   ├── roots.py
│       │   ├── plugin_cfg.py
│       │   ├── project_godot.py
│       │   ├── gdextension.py
│       │   ├── native.py
│       │   ├── dotnet.py
│       │   ├── rust.py
│       │   ├── version_evidence.py
│       │   └── license.py
│       ├── engines/
│       │   ├── identity.py
│       │   ├── registry.py
│       │   ├── snapshot.py
│       │   ├── api_index.py
│       │   └── api_diff.py
│       ├── workspace/
│       │   ├── factory.py
│       │   ├── install.py
│       │   ├── project_config.py
│       │   └── cleanup.py
│       ├── runner/
│       │   ├── process.py
│       │   ├── environment.py
│       │   ├── limits.py
│       │   └── commands.py
│       ├── sandbox/
│       │   ├── base.py
│       │   ├── docker_linux.py
│       │   └── trusted_host.py
│       ├── phases/
│       │   ├── import_phase.py
│       │   ├── parse_phase.py
│       │   ├── editor_phase.py
│       │   ├── runtime_phase.py
│       │   ├── gui_phase.py
│       │   └── export_phase.py
│       ├── logs/
│       │   ├── parser.py
│       │   ├── patterns.py
│       │   ├── sentinel.py
│       │   └── allowlist.py
│       ├── classify/
│       │   ├── rules.py
│       │   ├── differential.py
│       │   └── recommendations.py
│       ├── reports/
│       │   ├── json_report.py
│       │   ├── markdown_report.py
│       │   ├── html_report.py
│       │   ├── codex_brief.py
│       │   └── reproduce.py
│       └── cache/
│           ├── store.py
│           └── prune.py
├── harness/
│   ├── base_project/
│   │   ├── project.godot
│   │   ├── icon.svg
│   │   ├── main.tscn
│   │   └── runtime_probe.gd
│   └── editor_plugin/
│       ├── plugin.cfg
│       └── plugin.gd
├── docker/
│   ├── Dockerfile.worker
│   ├── entrypoint.sh
│   └── README.md
├── schemas/
│   ├── result.schema.json
│   ├── manifest.schema.json
│   └── batch.schema.json
├── examples/
│   ├── redot-compat.toml
│   ├── plugin-test.toml
│   └── plugins.toml
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   └── fixtures/
│       ├── baseline_gdscript_pass/
│       ├── post_baseline_api_gap/
│       ├── malformed_layout/
│       ├── editor_activation_fail/
│       ├── runtime_fail/
│       ├── timeout_plugin/
│       ├── missing_native_binary/
│       ├── bad_entry_symbol/
│       ├── dotnet_plugin/
│       ├── engine_module/
│       └── unsafe_archives/
└── .github/
    └── workflows/
        ├── quality.yml
        ├── integration-redot.yml
        └── release.yml
```

---

# 9. Core data contracts

Use Pydantic models and generate JSON Schemas from them. Schemas are public API and must be versioned.

## 9.1 `SourceProvenance`

Required fields:

```text
source_kind
requested_url_or_path
canonical_url
host
owner
repository
requested_ref
resolved_ref
resolved_commit
release_id
release_tag
release_asset_name
download_url
retrieved_at
archive_sha256
archive_size
http_etag
license_candidates
```

## 9.2 `EngineIdentity`

Required fields:

```text
product_name
product_version
compatibility_version
binary_path
binary_sha256
platform
architecture
precision
is_dotnet
version_output
help_output_sha256
extension_api_sha256
extension_api_path
```

The snapshot command should run:

```text
<engine> --version
<engine> --help
<engine> --headless --dump-extension-api
```

Redot command-line reference:

- https://docs.redotengine.org/tutorials/editor/command_line_tutorial

## 9.3 `VersionEvidence`

Required fields:

```text
source_type
source_path_or_url
raw_value
normalized_version
meaning
confidence
notes
```

`meaning` must be one of:

- `declared_minimum`;
- `declared_maximum`;
- `native_build_api`;
- `project_feature_version`;
- `source_binding_version`;
- `release_claim`;
- `branch_claim`;
- `inferred_only`.

## 9.4 `PluginInventory`

Required fields:

```text
plugin_roots
plugin_ids
package_kind
languages
contains_editor_plugin
contains_runtime_library
contains_gdextension
contains_native_source
contains_native_binaries
contains_rust
contains_dotnet
contains_engine_module
native_platforms
native_architectures
gdextension_manifests
project_files
addon_files
entry_scripts
candidate_demo_scenes
version_evidence
effective_api_target
effective_api_confidence
baseline_decision
```

## 9.5 `PhaseResult`

Required fields:

```text
phase_name
engine_role
command
working_directory
environment_redacted
started_at
finished_at
duration_ms
exit_code
terminated_by_signal
timed_out
stdout_path
stderr_path
combined_log_path
sentinel_events
findings
artifacts
status
```

## 9.6 `Finding`

Required fields:

```text
code
severity
category
message
phase
engine_role
file
line
symbol
raw_log_excerpt
api_diff_match
recommendation
```

## 9.7 `CompatibilityResult`

Required fields:

```text
schema_version
run_id
source
inventory
policy
redot_engine
godot_control_engine
platform
phases
findings
classification
confidence
confidence_reasons
port_candidate
recommended_next_action
created_at
tester_version
reproduction
```

---

# 10. Source acquisition

## 10.1 General requirements

Every source adapter must:

- resolve mutable names such as `main` or `latest` to an immutable commit/tag/release;
- record all redirects;
- use HTTPS by default;
- support optional tokens without logging them;
- limit response size;
- calculate SHA-256 while downloading;
- cache by content hash;
- never execute package contents during acquisition;
- return a normalized `ResolvedArtifact`.

## 10.2 Local adapter

Support:

- directory;
- `.zip`;
- `.tar`;
- `.tar.gz`;
- `.tgz`.

A local directory should be copied into the run workspace, never modified in place.

## 10.3 Direct HTTP adapter

Requirements:

- HTTPS only unless `--allow-insecure-http` is explicit;
- redirect limit;
- configurable host allowlist;
- compressed and uncompressed size limits;
- MIME-type validation plus file-signature validation;
- partial downloads must be deleted.

## 10.4 GitHub adapter

Use the GitHub REST API for:

- latest release;
- release by tag;
- release assets;
- repository ZIP/TAR archive for a fixed ref.

References:

- Repository archive API: https://docs.github.com/en/rest/repos/contents
- Releases API: https://docs.github.com/en/rest/releases
- Release assets API: https://docs.github.com/en/rest/releases/assets

Support `GITHUB_TOKEN` for rate limits and private repositories. Redact it from all logs.

## 10.5 Codeberg adapter

Codeberg is Forgejo-based. Support:

- repository source archives;
- tags;
- releases;
- release attachments;
- optional `CODEBERG_TOKEN`.

Use the public Forgejo/Gitea-compatible API under `/api/v1` where available, with a `git clone --depth 1` fallback for source snapshots.

References:

- Codeberg tags and releases: https://docs.codeberg.org/git/using-tags/
- Codeberg repositories: https://docs.codeberg.org/getting-started/first-repository/
- Gitea/Forgejo-style API usage: https://docs.gitea.com/1.25/development/api-usage

Do not assume that a Codeberg release attachment and the automatically generated source archive have the same packaging. Prefer a named plugin release asset when the user specifies a pattern.

## 10.6 Godot Asset Library adapter

Support the legacy Asset Library because it exposes public metadata and remains online.

References:

- API repository: https://github.com/godotengine/godot-asset-library
- API documentation file: https://github.com/godotengine/godot-asset-library/blob/master/API.md
- Public API base: https://godotengine.org/asset-library/api
- Asset Library website: https://godotengine.org/asset-library/

Record:

- asset ID;
- version;
- minimum and maximum Godot versions when available;
- repository URL;
- download URL;
- license.

## 10.7 Godot Asset Store adapter

The newer Asset Store is in beta and its implementation/API is not public in the same way as the old Asset Library.

Reference:

- https://store.godotengine.org/
- https://docs.godotengine.org/en/stable/community/asset_store/what_is_asset_store.html

MVP behavior:

1. Parse public metadata from the asset page when possible.
2. Follow a public source-code link when one is exposed.
3. Use a public download only when its URL can be resolved without browser automation or credentials.
4. Otherwise stop with a clear message requesting a source repository URL or local archive.
5. Do not make the entire tester dependent on brittle HTML scraping.

---

# 11. Safe archive extraction

Treat every archive as hostile.

Reject or neutralize:

- path traversal such as `../`;
- absolute paths;
- Windows drive paths;
- UNC paths;
- device files;
- named pipes;
- hard links;
- symlinks by default;
- duplicate paths with case collisions;
- paths exceeding configured length;
- archives exceeding file-count limits;
- zip bombs or excessive expansion ratios;
- files exceeding per-file limits.

Default limits should be configurable. Suggested starting values:

```toml
[limits]
max_download_bytes = 1073741824
max_unpacked_bytes = 4294967296
max_file_count = 100000
max_single_file_bytes = 1073741824
max_path_length = 512
max_expansion_ratio = 200
```

The extractor must be covered by explicit malicious-archive tests.

---

# 12. Static inventory and API-target detection

## 12.1 Plugin-root detection

Search to a bounded depth for:

- `addons/*/plugin.cfg`;
- `addons/**/*.gdextension`;
- `project.godot`;
- engine-module markers such as `config.py`, `SCsub`, `register_types.cpp`, or a `modules/<name>` layout;
- Rust `Cargo.toml` files using the `godot` crate;
- C# `.csproj` files using `Godot.NET.Sdk`;
- C++ `SConstruct`, `CMakeLists.txt`, or `godot-cpp` submodules.

Godot's standard editor-plugin form uses `addons/<plugin_name>/plugin.cfg`:

- https://docs.godotengine.org/en/stable/tutorials/plugins/editor/installing_plugins.html
- https://docs.godotengine.org/en/stable/tutorials/plugins/editor/making_plugins.html

If multiple independent plugin roots exist, list them. Require `--plugin-id` or a test manifest when automatic selection is ambiguous.

## 12.2 Effective version evidence

Inspect in descending authority:

1. Asset Library/Store declared minimum and maximum versions.
2. `.gdextension`:
   - `compatibility_minimum`;
   - `compatibility_maximum`;
   - binary names and platform selectors.
3. Included engine API snapshots or generated binding metadata.
4. `project.godot` `config/features` values.
5. C++ binding branch, tag, or submodule commit.
6. Rust `godot` crate API feature such as `api-4-6`.
7. `Godot.NET.Sdk` package version and target framework.
8. CI matrices and release build scripts.
9. Release notes or explicit README statements.
10. Badges and branch names as weak evidence only.

Redot `.gdextension` reference:

- https://docs.redotengine.org/tutorials/scripting/gdextension/gdextension_file

Redot C++ extension reference:

- https://docs.redotengine.org/tutorials/scripting/gdextension/gdextension_cpp_example

## 12.3 Compute separate version fields

Do not collapse everything into one value. Compute:

```text
declared_minimum_version
declared_maximum_version
native_build_api_version
source_binding_api_version
project_feature_version
effective_api_target
effective_api_confidence
```

For a pure GDScript plugin, declared/project versions may dominate.

For a native plugin, `native_build_api_version` and `source_binding_api_version` dominate. A plugin may advertise support for Godot 4.4+ while its current release binary was built against Godot 4.7.

## 12.4 Baseline screening algorithm

Pseudo-code:

```python
def should_dynamic_test(inventory, policy, force):
    if force:
        return True

    if inventory.contains_engine_module:
        return True

    target = inventory.effective_api_target

    if target is None:
        return True

    if target > Version("4.5.2"):
        return True

    if inventory.has_conflicting_post_baseline_evidence:
        return True

    return False
```

When returning `False`, emit:

```text
classification = NO_PORT_NEEDED_BASELINE_POLICY
port_candidate = false
```

Include every evidence item in the report so the decision can be audited.

---

# 13. Engine registry and snapshots

## 13.1 User-provided binaries first

The MVP must require explicit engine paths. Do not silently download and execute engines.

Configuration example:

```toml
[engines.redot]
path = "C:/Tools/Redot/redot-26.2-stable.exe"
expected_product_version = "26.2"
compatibility_baseline = "4.5.2"

[engines.godot_controls."4.6"]
path = "C:/Tools/Godot/Godot_v4.6-stable_win64.exe"

[engines.godot_controls."4.7"]
path = "C:/Tools/Godot/Godot_v4.7-stable_win64.exe"
```

## 13.2 `doctor` command

```powershell
redot-compat doctor --redot "$env:REDOT_BIN"
```

Verify:

- file exists and is executable;
- `--version` succeeds;
- `--help` includes required flags;
- `--headless` works;
- `--import` works on the base fixture;
- `--dump-extension-api` works;
- product and compatibility versions are recorded;
- .NET capability is recorded;
- binary SHA-256 is recorded.

Required Redot flags include:

- `--editor`;
- `--headless`;
- `--path`;
- `--quit` or `--quit-after`;
- `--script`;
- `--check-only`;
- `--import`;
- `--build-solutions` for .NET;
- `--dump-extension-api`;
- `--validate-extension-api` when available.

Reference:

- https://docs.redotengine.org/tutorials/editor/command_line_tutorial

## 13.3 API index and diff

Generate and cache `extension_api.json` for Redot and every configured Godot control.

Build indexes for:

- classes;
- methods;
- properties;
- signals;
- constants;
- enums;
- utility functions;
- built-in types.

For each control version, generate:

```text
only_in_godot_control
only_in_redot
signature_changed
property_changed
constant_changed
```

When a log mentions a missing class, method, or property, correlate it with this diff. This turns a generic parse error into evidence that the plugin uses a post-4.5.2 API.

---

# 14. Disposable workspace construction

Every dynamic run must use a new workspace.

Suggested run layout:

```text
runs/<run-id>/
├── input/
│   ├── provenance.json
│   └── inventory.json
├── engines/
│   ├── redot.json
│   └── godot-control.json
├── normalized-source/
├── fixture-redot/
├── fixture-godot/
├── logs/
├── events/
├── artifacts/
├── result.json
├── report.md
├── codex_port_brief.md
├── reproduce.ps1
└── reproduce.sh
```

## 14.1 Fixture rules

- Copy the base project.
- Copy the compatibility harness.
- Install only the selected add-on root by default.
- Do not overwrite the fixture's `project.godot`, harness, or main scene.
- Merge `addons/` according to the normal Godot installation model.
- Allow additional paths only through an explicit test manifest.
- Use unique project and user-data names for every run.
- Isolate editor settings and user-data directories through environment variables.

## 14.2 Isolated environment variables

Set clean per-run locations.

Linux:

```text
HOME
XDG_CONFIG_HOME
XDG_DATA_HOME
XDG_CACHE_HOME
```

Windows:

```text
USERPROFILE
APPDATA
LOCALAPPDATA
TEMP
TMP
```

macOS:

```text
HOME
TMPDIR
```

Do not allow the test engine to read or overwrite the user's normal editor configuration unless explicitly requested.

---

# 15. Process runner

Implement the runner with `asyncio.create_subprocess_exec()` or an equivalent argument-array API.

Requirements:

- never invoke a shell for engine commands;
- capture stdout and stderr separately and as a timestamped combined stream;
- enforce per-phase timeout;
- enforce maximum log size;
- terminate the full process tree;
- record exit code and terminating signal;
- redact tokens and configured secrets;
- support cancellation;
- preserve exact arguments in reproduction scripts;
- differentiate tester errors from engine/plugin errors.

Process-tree termination:

- Linux/macOS: create a new process group and kill the group on timeout.
- Windows: use psutil or Job Objects to terminate child processes.
- Docker: stop and remove the container.

Recommended default timeouts:

```toml
[timeouts]
engine_doctor_seconds = 30
import_seconds = 180
parse_per_script_seconds = 20
editor_seconds = 120
runtime_seconds = 120
gui_seconds = 180
export_seconds = 600
```

Allow per-plugin overrides in the test manifest.

---

# 16. Dynamic test phases

Each phase must be independently recorded and independently reproducible.

## 16.1 Phase A: import

Command pattern:

```powershell
& $RedotBin `
  --headless `
  --path $FixturePath `
  --import `
  --verbose
```

This phase checks:

- project recognition;
- resource scan/import;
- script parsing triggered by import;
- GDExtension manifest discovery;
- missing native libraries;
- import-plugin failures.

`--import` starts the editor, waits for resource import, and quits according to the Redot command-line documentation.

## 16.2 Phase B: supplementary GDScript parse

For discovered `.gd` scripts, run bounded `--check-only --script` checks where appropriate.

Do not treat every script as a standalone executable. Skip or downgrade checks that are clearly editor-only or require a base project context that cannot be synthesized.

Record:

- parse success;
- parser diagnostics;
- preloaded dependency failures;
- missing classes/methods.

## 16.3 Phase C: .NET build

When C# is present:

1. Verify the selected Redot binary is a .NET build.
2. Run:

```powershell
& $RedotDotNetBin `
  --headless `
  --path $FixturePath `
  --build-solutions `
  --verbose
```

3. If no .NET engine is configured, classify `MISSING_DOTNET_ENGINE`, not plugin incompatibility.

## 16.4 Phase D: editor-plugin activation

Enable the target plugin and `_redot_compat_harness` in the disposable fixture.

Command pattern:

```powershell
& $RedotBin `
  --headless `
  --editor `
  --path $FixturePath `
  --quit-after 600 `
  --verbose
```

The external timeout remains authoritative. The harness should normally quit earlier after its checks.

The harness must emit events such as:

```json
{"event":"harness_started","schema":1}
{"event":"target_plugin_state","plugin_id":"limboai","enabled":true}
{"event":"class_check","name":"BTPlayer","exists":true}
{"event":"resource_check","path":"res://addons/...","loaded":true}
{"event":"harness_finished","success":true}
```

Prefix every event line with:

```text
REDOT_COMPAT_EVENT
```

The log parser must treat only valid JSON after this exact prefix as a structured event.

## 16.5 Phase E: runtime smoke test

Command pattern:

```powershell
& $RedotBin `
  --headless `
  --path $FixturePath `
  --scene res://main.tscn `
  --quit-after 1800 `
  --verbose
```

Generic checks:

- load selected scripts and resources;
- check global classes;
- check manifest-declared autoloads;
- instantiate manifest-approved scenes;
- wait several frames;
- call only manifest-approved probe methods;
- detect unhandled script errors;
- exit deterministically.

Do not claim functional parity from the generic runtime phase alone. Label the scope clearly in reports.

## 16.6 Phase F: GUI fallback

Some editor plugins cannot initialize correctly in headless mode.

On Linux, support Xvfb:

```bash
xvfb-run -a redot --editor --path "$FIXTURE" --quit-after 600 --verbose
```

If no GUI-capable worker exists and the plugin requires display access, classify `DISPLAY_REQUIRED`.

The first release does not need arbitrary UI automation. It only needs to establish that the editor and plugin can initialize under a real display server.

## 16.7 Phase G: export smoke test

Run only when:

- export templates are configured;
- the plugin test manifest requests it;
- the plugin contains runtime functionality or native libraries whose export selection matters.

Use a minimal preset and test package. Verify:

- expected library is included;
- wrong-platform libraries are excluded;
- exported application starts;
- runtime harness emits success.

Reference commands:

- https://docs.redotengine.org/tutorials/editor/command_line_tutorial

---

# 17. Redot harness implementation

## 17.1 Editor harness pseudo-code

```gdscript
@tool
extends EditorPlugin

const PREFIX := "REDOT_COMPAT_EVENT "
var frame_count := 0
var config: Dictionary = {}
var completed := false

func _enter_tree() -> void:
    config = _load_generated_config()
    _emit_event("harness_started", {"schema": 1})
    set_process(true)

func _process(_delta: float) -> void:
    if completed:
        return

    frame_count += 1
    if frame_count < int(config.get("wait_frames", 30)):
        return

    completed = true
    var failures: Array[String] = []
    var plugin_id := String(config.get("target_plugin_id", ""))
    var enabled := EditorInterface.is_plugin_enabled(plugin_id)
    _emit_event("target_plugin_state", {
        "plugin_id": plugin_id,
        "enabled": enabled,
    })

    if not enabled:
        failures.append("target plugin is not enabled")

    _run_class_checks(failures)
    _run_resource_checks(failures)
    _run_project_setting_checks(failures)

    _emit_event("harness_finished", {
        "success": failures.is_empty(),
        "failures": failures,
    })

    get_tree().quit(0 if failures.is_empty() else 1)

func _emit_event(name: String, payload: Dictionary) -> void:
    payload["event"] = name
    print(PREFIX + JSON.stringify(payload))
```

The implementation must guard every probe so a failed check becomes a structured failure rather than crashing the harness itself.

## 17.2 Runtime harness pseudo-code

Use a `SceneTree` or root `Node` script that:

1. loads a generated JSON probe configuration;
2. emits `runtime_started`;
3. runs each probe;
4. emits one event per probe;
5. waits any requested frames;
6. emits `runtime_finished`;
7. exits with 0 or 1.

## 17.3 Generated harness configuration

The Python orchestrator should convert `plugin-test.toml` into a generated JSON file inside the fixture. GDScript should not need a TOML parser.

---

# 18. Plugin-specific test manifest

Use TOML because Python 3.12 can read it with `tomllib`, it is readable by humans, and the orchestrator can convert it to JSON for the Redot harness.

Filename:

```text
plugin-test.toml
```

Example:

```toml
schema_version = 1
name = "Example Plugin"
plugin_ids = ["example_plugin"]
expected_godot_api = "4.7"
test_modes = ["import", "editor", "runtime"]
requires_display = false
requires_network = false
trusted_build = false
wait_editor_frames = 60
runtime_frames = 120

[install]
addon_roots = ["addons/example_plugin"]
include_paths = []

[expect]
classes = ["ExampleNode"]
autoloads = []
resources = ["res://addons/example_plugin/example_resource.tres"]
project_settings = []

[[runtime_probe]]
type = "load_resource"
path = "res://addons/example_plugin/example_resource.tres"

[[runtime_probe]]
type = "instantiate_scene"
path = "res://addons/example_plugin/demo.tscn"
frames = 30

[[runtime_probe]]
type = "class_exists"
name = "ExampleNode"

[timeouts]
editor_seconds = 120
runtime_seconds = 120
```

Supported MVP probe types:

- `class_exists`;
- `load_script`;
- `load_resource`;
- `instantiate_scene`;
- `autoload_exists`;
- `project_setting_exists`;
- `wait_frames`.

Later probe types:

- `instantiate_class`;
- `call_method`;
- `set_property`;
- `assert_signal`;
- `run_scene_interaction`;
- `export_and_launch`.

Do not implement arbitrary code strings in the manifest.

---

# 19. Sandbox and security model

Plugin editor scripts and native libraries are arbitrary code. Treat dynamic testing as code execution, not file validation.

## 19.1 Default behavior

- Static inspection is safe-mode and requires no sandbox.
- Dynamic testing defaults to `--sandbox auto`.
- `auto` chooses Docker when a compatible Linux test is possible.
- Host execution requires a trusted source or explicit `--allow-unsafe-host-execution`.
- Never mount the Docker socket into a worker.
- Network access is disabled by default.
- Credentials are never injected unless an explicit manifest and CLI option permit them.

## 19.2 Docker worker

Recommended restrictions:

```bash
docker run --rm \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 256 \
  --memory 4g \
  --cpus 2 \
  --tmpfs /tmp:rw,nosuid,size=1g \
  -v "$SOURCE:/input:ro" \
  -v "$OUTPUT:/output:rw" \
  redot-compat-worker:<version>
```

The exact worker image must include:

- Python runtime or compiled CLI worker;
- Redot runtime dependencies;
- Xvfb for GUI fallback;
- basic native dependency inspection tools;
- a non-root user.

Docker security references:

- https://docs.docker.com/engine/security/
- https://docs.docker.com/engine/containers/run/

## 19.3 Platform limitation

A Linux container cannot validate a Windows-only DLL or macOS framework.

Expected behavior:

- If a native package includes Linux binaries, test them in Docker.
- If it contains only Windows binaries, return `MISSING_PLATFORM_BINARY` for the Linux worker.
- On Windows, allow `TrustedHostBackend` only with explicit consent.
- Design a later `WindowsVmBackend` using an ephemeral Windows Sandbox, Hyper-V VM, or remote disposable worker.
- Never claim cross-platform compatibility from a single platform result.

## 19.4 Build scripts

Do not run arbitrary `SConstruct`, CMake, Cargo `build.rs`, PowerShell, shell, or other build scripts in the MVP.

A future trusted build mode may:

- require `trusted_build = true` in the manifest;
- require explicit user approval;
- run in a stronger sandbox;
- use allowlisted toolchains;
- disable network by default;
- record every command and dependency.

---

# 20. Log parsing and findings

Scan for structured and unstructured evidence.

## 20.1 Required patterns

At minimum recognize:

```text
ERROR:
SCRIPT ERROR:
Parse Error
FATAL:
CRASH
segmentation fault
access violation
unhandled exception
failed to load
cannot open shared object
undefined symbol
symbol not found
entry symbol
GDExtension
compatibility_minimum
No GDExtension library found
Invalid call
Invalid get index
Identifier not declared
Nonexistent function
Cannot get class
Failed loading resource
Condition "..." is true
WARNING:
```

## 20.2 Finding categories

Normalize findings to:

- `package`;
- `script_parse`;
- `script_runtime`;
- `editor_api`;
- `runtime_api`;
- `native_load`;
- `native_symbol`;
- `native_dependency`;
- `dotnet`;
- `rust_binding`;
- `engine_module`;
- `resource_import`;
- `export`;
- `platform`;
- `timeout`;
- `crash`;
- `security`;
- `tester_internal`.

## 20.3 Warning policy

Warnings are not silently ignored.

Implement a versioned allowlist with:

```text
regex
plugin_sha256 or plugin selector
engine_sha256 or engine version
phase
justification
expiry or review date
```

Unexplained warnings appear in the report and may reduce confidence or fail a configured strict gate.

## 20.4 API-diff correlation

When a missing symbol is found:

1. parse class and member name where possible;
2. search the Redot API index;
3. search the Godot control index;
4. attach one of:
   - `present_in_control_only`;
   - `signature_changed`;
   - `absent_in_both`;
   - `unable_to_correlate`.

This evidence feeds the classifier.

---

# 21. Differential testing with Godot

The Godot control run is central to distinguishing a Redot gap from a broken plugin.

## 21.1 Control selection

The user registers one or more Godot binaries. Select the lowest registered control that satisfies the plugin's effective target, unless a manifest specifies an exact version.

If no matching control is available:

- continue the Redot test;
- lower confidence;
- clearly state that Redot specificity was not proven.

## 21.2 Differential rules

| Redot | Godot control | Interpretation |
|---|---|---|
| PASS | PASS | `COMPATIBLE_UNCHANGED` |
| FAIL | PASS | Strong Redot-specific port evidence |
| FAIL | FAIL | `UPSTREAM_PACKAGE_FAILURE`, bad package, or bad test fixture |
| PASS | FAIL | Control mismatch or upstream regression; classify `INCONCLUSIVE` and investigate |
| TIMEOUT | PASS | Likely Redot hang; high-priority finding |
| CRASH | PASS | Likely Redot/native incompatibility; high-priority finding |

Use the same normalized source, install layout, manifest, platform, renderer, and phase settings for both engines wherever possible.

---

# 22. Deterministic classification rules

Implement ordered rules. First matching decisive rule wins, with secondary findings preserved.

Suggested precedence:

1. Tester internal failure → `INTERNAL_TESTER_ERROR`.
2. Unsafe/malformed archive → `INVALID_PACKAGE`.
3. Baseline policy skip → `NO_PORT_NEEDED_BASELINE_POLICY`.
4. Engine module detected → `PORT_REQUIRED_ENGINE_MODULE`.
5. Required .NET engine missing → `MISSING_DOTNET_ENGINE`.
6. No worker-platform native binary → `MISSING_PLATFORM_BINARY`.
7. Required compiled artifact absent → `MISSING_BUILD_ARTIFACT`.
8. Redot crash with Godot control pass → native/API port status based on findings.
9. Redot timeout with Godot control pass → `TIMEOUT`, `port_candidate=true`.
10. Native library load/symbol failure:
    - source binding target <= baseline and no source API errors → `PORT_REQUIRED_NATIVE_REBUILD`;
    - source compile/API evidence newer than baseline → `PORT_REQUIRED_NATIVE_SOURCE`;
    - Rust binding evidence → `PORT_REQUIRED_RUST_BINDINGS`.
11. GDScript parse error in Redot and pass in control → `PORT_REQUIRED_GDSCRIPT_API`.
12. Editor activation failure in Redot and pass in control → `PORT_REQUIRED_EDITOR_API`.
13. Runtime-only failure in Redot and pass in control → `PORT_REQUIRED_RUNTIME_API`.
14. Export-only failure → `PORT_REQUIRED_EXPORT_PACKAGING`.
15. Failure in both engines → `UPSTREAM_PACKAGE_FAILURE`.
16. Required display/service unavailable → corresponding inconclusive status.
17. All required phases pass → `COMPATIBLE_UNCHANGED`.
18. Otherwise → `INCONCLUSIVE`.

Create unit tests for every rule and every precedence collision.

---

# 23. Recommended-next-action mapping

The classifier must generate an actionable next step.

Examples:

## `PORT_REQUIRED_NATIVE_REBUILD`

```text
Rebuild the current upstream source against the exact Redot 26.2 API and redot-cpp branch. Do not begin source-level API changes until a clean rebuild has been attempted and its compiler errors recorded.
```

## `PORT_REQUIRED_GDSCRIPT_API`

```text
Patch the listed GDScript symbols. Use the attached Redot-versus-Godot API diff to identify replacements or compatibility shims. Preserve the upstream public API and serialized resource format.
```

## `PORT_REQUIRED_EDITOR_API`

```text
Audit the plugin's EditorPlugin calls and editor-resource formats. Reproduce using the generated editor-phase command and start from the first Redot-only error.
```

## `PORT_REQUIRED_RUST_BINDINGS`

```text
Route the port through the shared Redot–Rust compatibility layer. Do not create a plugin-local godot-rust fork unless the shared layer cannot represent the required API.
```

## `UPSTREAM_PACKAGE_FAILURE`

```text
Do not start a Redot port from this package. Verify the selected release asset, required dependencies, and upstream installation instructions because the same fixture also fails under its target Godot version.
```

---

# 24. CLI specification

## 24.1 Commands

```text
redot-compat doctor
redot-compat engine snapshot
redot-compat inspect
redot-compat test
redot-compat batch
redot-compat report
redot-compat reproduce
redot-compat cache list
redot-compat cache prune
redot-compat schema export
redot-compat version
```

## 24.2 `inspect`

```text
redot-compat inspect SOURCE
  [--ref REF]
  [--release latest|TAG]
  [--asset GLOB]
  [--plugin-id ID]
  [--output DIR]
  [--json]
```

No plugin code may execute during `inspect`.

## 24.3 `test`

```text
redot-compat test SOURCE
  --redot PATH
  [--godot-control PATH]
  [--ref REF]
  [--release latest|TAG]
  [--asset GLOB]
  [--plugin-id ID]
  [--manifest PATH]
  [--sandbox auto|docker|host]
  [--allow-unsafe-host-execution]
  [--force-test-baseline]
  [--strict-warnings]
  [--preserve-workspace]
  [--output DIR]
```

## 24.4 `batch`

Batch file example:

```toml
schema_version = 1

[defaults]
redot = "C:/Tools/Redot/redot-26.2-stable.exe"
sandbox = "auto"
output = "./reports"

[[plugin]]
name = "Example GitHub Plugin"
source = "https://github.com/example/plugin"
release = "latest"
plugin_id = "example"

[[plugin]]
name = "Example Codeberg Plugin"
source = "https://codeberg.org/example/plugin"
ref = "v2.0.0"
manifest = "./manifests/example-plugin.toml"
```

## 24.5 Exit codes

Use stable documented exit codes:

| Exit | Meaning |
|---:|---|
| 0 | Compatible/no port needed |
| 10 | Baseline policy skip/no port needed |
| 20 | Port required |
| 30 | Invalid package/upstream package failure |
| 40 | Inconclusive/missing environment |
| 50 | Tester internal error |

The full classification remains in `result.json`.

---

# 25. Reports and artifacts

## 25.1 Markdown report

`report.md` must include:

1. conclusion;
2. port-candidate decision;
3. confidence;
4. exact source revision and archive hash;
5. baseline/version evidence;
6. Redot engine identity and hash;
7. Godot control identity and hash;
8. platform and sandbox;
9. phase table;
10. decisive errors;
11. API-diff matches;
12. limitations;
13. recommended next action;
14. reproduction commands;
15. artifact paths.

## 25.2 Codex port brief

`codex_port_brief.md` should be shorter than the full report but contain everything needed to begin work:

```text
Plugin/upstream URL
Resolved tag and commit
License
Current target Godot API
Redot target and binary hash
Final classification
First failing phase
Exact reproduction command
Minimal error excerpts
Missing/changed API symbols
Native library details
Suggested first patch
Required tests
Known blockers
```

## 25.3 JSON report

`result.json` is authoritative. Markdown and HTML are derived views.

## 25.4 Reproduction scripts

Generate:

- `reproduce.ps1`;
- `reproduce.sh`.

Scripts must use local artifact paths, verify input hashes, and reproduce at least the decisive phase.

---

# 26. Native-package inspection

Without executing binaries, inspect:

- `.gdextension` library map;
- expected entry symbol;
- platform and architecture selectors;
- presence and hashes of DLL/SO/dylib/framework files;
- obvious dependency names using platform tools when available;
- whether debug/release entries point to existing files;
- whether the archive mixes incompatible architectures.

Tools:

- Windows: `dumpbin /DEPENDENTS` or a documented PE parser;
- Linux: `readelf -d`, `objdump -p`, `ldd` only inside an isolated environment;
- macOS: `otool -L`;
- cross-platform static inspection may use a carefully selected library, but it must not load the binary.

Never use `ctypes`, `dlopen`, or equivalent in the Python orchestrator process.

---

# 27. Test suite

## 27.1 Unit tests

Cover:

- URL recognition;
- immutable ref resolution;
- archive hashing;
- safe extraction;
- root detection;
- `plugin.cfg` parsing;
- `.gdextension` parsing;
- project feature parsing;
- Rust/C++/.NET detection;
- version evidence precedence;
- baseline screening;
- command construction;
- environment redaction;
- log parsing;
- sentinel parsing;
- API indexing and diffing;
- every classification rule;
- report rendering;
- schema compatibility.

## 27.2 Synthetic plugin fixtures

Create at least these fixtures:

### `baseline_gdscript_pass`

- editor plugin;
- explicitly targets <=4.5.2;
- should be skipped by default;
- should pass when forced.

### `post_baseline_api_gap`

Generate or select a symbol that is present in the configured Godot control API and absent from Redot's API. The plugin should pass in the control and fail in Redot.

Do not hard-code an unverifiable future symbol. Build this fixture from the generated API diff during integration setup.

### `malformed_layout`

- `plugin.cfg` outside `addons`;
- missing entry script;
- expected `INVALID_PACKAGE` or `COMPATIBLE_REPACKAGE_ONLY` depending on configuration.

### `editor_activation_fail`

- valid parse/import;
- throws during `_enter_tree()`;
- expected editor failure.

### `runtime_fail`

- editor/import pass;
- runtime script throws;
- expected runtime classification.

### `timeout_plugin`

- intentionally blocks or loops;
- runner must terminate the process tree;
- expected `TIMEOUT`.

### `missing_native_binary`

- `.gdextension` references a nonexistent library;
- expected `MISSING_BUILD_ARTIFACT`.

### `bad_entry_symbol`

- native test extension with incorrect entry symbol;
- expected native-load finding.

### `dotnet_plugin`

- expected .NET requirement handling.

### `engine_module`

- module layout;
- expected `PORT_REQUIRED_ENGINE_MODULE` without dynamic execution.

### `unsafe_archives`

Include separate archives for:

- path traversal;
- absolute path;
- symlink;
- case collision;
- expansion bomb simulation;
- file-count limit.

## 27.3 Integration tests

Required Linux integration path:

1. configure Redot 26.2;
2. run `doctor`;
3. snapshot API;
4. inspect all fixtures;
5. run safe dynamic fixtures inside Docker;
6. validate golden `result.json` outputs;
7. validate Markdown reports;
8. verify no host project/config files changed.

Optional platform jobs:

- Windows trusted fixtures;
- macOS trusted fixtures;
- .NET engine job;
- native extension fixture job.

Do not execute arbitrary third-party plugins in ordinary public pull-request CI.

---

# 28. CI and release engineering

## 28.1 Quality workflow

Run:

```bash
uv sync --frozen
ruff format --check .
ruff check .
mypy src
pytest -q --cov=redot_compat --cov-report=term-missing
```

Enforce a meaningful coverage threshold after the initial bootstrap. Do not game coverage with empty tests.

## 28.2 Integration workflow

- Pin the Redot release URL or use a checked-in checksum manifest.
- Verify downloaded engine SHA-256.
- Build the Docker worker.
- Run only trusted repository fixtures.
- Upload run reports and logs as CI artifacts.

## 28.3 Release workflow

Produce:

- Python wheel;
- source distribution;
- optional standalone executables via PyInstaller or another reviewed packager;
- Docker worker image;
- SBOM;
- SHA-256 checksums;
- signed release where project signing is configured.

The Python package and Docker worker must report the same semantic version.

---

# 29. Implementation milestones

Work in this order. Do not skip completion gates.

## Milestone 0 — repository and contracts

Implement:

- repository skeleton;
- `pyproject.toml` and lockfile;
- CLI placeholder;
- Pydantic result models;
- generated JSON Schemas;
- `TODO.md`, `DECISIONS.md`, `BLOCKERS.md`;
- security model documentation.

Gate:

- `redot-compat version` works;
- schemas validate sample documents;
- formatting, linting, typing, and unit-test jobs pass.

## Milestone 1 — source acquisition and static inspection

Implement:

- local source adapter;
- direct HTTP adapter;
- GitHub adapter;
- Codeberg adapter;
- safe extraction;
- plugin-root detection;
- package-kind detection;
- version-evidence collection;
- baseline screening;
- `inspect` command and Markdown/JSON output.

Gate:

- no plugin code executes;
- all unsafe-archive tests pass;
- baseline fixture returns `NO_PORT_NEEDED_BASELINE_POLICY`;
- current GitHub and Codeberg public fixtures resolve to immutable revisions.

## Milestone 2 — engine doctor, snapshots, and API diff

Implement:

- engine registry;
- `doctor`;
- binary hashing;
- `extension_api.json` snapshots;
- API index;
- Redot/Godot API diff;
- engine metadata reports.

Gate:

- Redot 26.2 is correctly reported as product 26.2 with compatibility baseline 4.5.2;
- repeated snapshots are content-addressed and deterministic;
- API diff unit tests pass.

## Milestone 3 — workspace and trusted process runner

Implement:

- disposable fixture factory;
- add-on installer;
- isolated environment directories;
- process runner;
- timeouts and process-tree termination;
- raw phase artifacts.

Use only trusted synthetic fixtures at this milestone.

Gate:

- import phase passes for a compatible fixture;
- timeout fixture is terminated cleanly;
- original source and user editor configuration remain unchanged.

## Milestone 4 — Docker Linux sandbox

Implement:

- worker Dockerfile;
- non-root execution;
- no-network default;
- resource limits;
- read-only input;
- writable output only;
- Xvfb support;
- backend selection.

Gate:

- trusted fixtures run inside Docker;
- plugin cannot write outside assigned scratch/output areas;
- plugin cannot use network in the default profile;
- no Docker socket is mounted.

## Milestone 5 — Redot editor and runtime harnesses

Implement:

- editor harness plugin;
- runtime harness;
- generated JSON probe configuration;
- sentinel event parser;
- import, parse, editor, runtime, and GUI phases;
- plugin-specific TOML manifest.

Gate:

- editor activation success and failure are distinguished;
- runtime-only failure is distinguished;
- malformed sentinel lines cannot spoof success;
- harness always emits a final event on normal completion.

## Milestone 6 — classifier and reports

Implement:

- finding normalization;
- deterministic classification rules;
- confidence calculation;
- recommended-next-action mapping;
- JSON, Markdown, HTML, and Codex brief;
- reproduction scripts;
- stable CLI exit codes.

Gate:

- every taxonomy status has a unit test;
- every synthetic fixture produces the expected golden result;
- reports contain hashes and exact reproduction commands.

## Milestone 7 — Godot control differential

Implement:

- control-engine selection;
- mirrored fixture generation;
- mirrored phase execution;
- differential rules;
- API-diff correlation;
- generated post-baseline fixture from real API differences.

Gate:

- a Redot-only synthetic failure is classified as a port candidate;
- a failure in both engines is not blamed on Redot;
- missing control lowers confidence rather than fabricating certainty.

## Milestone 8 — batch operation and source-adapter completion

Implement:

- batch TOML;
- concurrency limits;
- cache reuse;
- Asset Library adapter;
- cautious Asset Store metadata adapter;
- aggregate summary report;
- resume interrupted batch.

Gate:

- duplicate artifacts are downloaded once;
- batch failures do not corrupt other runs;
- aggregate counts equal individual result files.

## Milestone 9 — export and platform hardening

Implement:

- optional export phase;
- native dependency inspection;
- Windows trusted worker path;
- .NET integration job;
- platform-specific result aggregation;
- signed releases/SBOM.

Gate:

- platform-specific results are never generalized incorrectly;
- export failures are separated from editor/runtime failures;
- release artifacts are reproducible and hashed.

## Milestone 10 — optional trusted build adapters

Only after the core tester is stable, design:

- redot-cpp/SCons adapter;
- CMake adapter;
- Cargo/godot-rust adapter;
- .NET build adapter;
- plugin-specific build recipes.

Every build adapter must require explicit trust and run in isolation.

---

# 30. Acceptance criteria for version 1.0

Version 1.0 is complete only when all of the following are true:

- [ ] A local archive, GitHub release, and Codeberg release can be resolved and hashed.
- [ ] Unsafe archives are rejected.
- [ ] Plugin roots and package types are detected correctly for test fixtures.
- [ ] The 4.5.2 baseline rule is applied before dynamic execution.
- [ ] Redot 26.2 engine identity and compatibility lineage are recorded correctly.
- [ ] Import, editor activation, and runtime phases run in disposable projects.
- [ ] Linux dynamic tests default to Docker isolation.
- [ ] Host execution requires explicit unsafe consent.
- [ ] Timeouts terminate the complete process tree.
- [ ] Structured harness events cannot be confused with arbitrary plugin output.
- [ ] A matching Godot control can be run against the same normalized package.
- [ ] Redot-only, both-engine, and package-layout failures are distinguished.
- [ ] Native rebuild, native source port, GDScript API port, editor API port, engine module, and inconclusive states are distinguished.
- [ ] `result.json` validates against a versioned schema.
- [ ] `report.md` and `codex_port_brief.md` are generated.
- [ ] PowerShell and Bash reproduction scripts are generated.
- [ ] No compatibility claim is based solely on the process closing.
- [ ] No cross-platform claim is based on one platform.
- [ ] CI passes formatting, linting, typing, unit, integration, and golden-report tests.
- [ ] Documentation contains installation, configuration, security, and troubleshooting guidance.

---

# 31. Required documentation

Create:

## `README.md`

Include:

- purpose;
- architecture;
- installation;
- first test;
- baseline policy;
- interpreting results;
- security warning;
- Docker setup;
- GitHub and Codeberg examples;
- batch example.

## `SECURITY.md`

State prominently:

- plugins are arbitrary code;
- host mode is unsafe;
- Docker reduces risk but is not a universal guarantee;
- do not test secrets or private code in untrusted environments;
- how to report a vulnerability.

## `docs/classifications.md`

Document every status, confidence rule, and exit code.

## `docs/manifests.md`

Document every TOML field and probe type.

## `docs/sandboxing.md`

Document Docker, trusted host, platform limits, network policy, and future VM backends.

## `docs/adding-source-adapters.md`

Document the adapter protocol and contract tests.

## `docs/adding-test-probes.md`

Document how to extend the Redot harness safely.

## `docs/troubleshooting.md`

Cover:

- no plugin root detected;
- wrong release asset;
- missing native binary;
- .NET engine mismatch;
- headless failure;
- Docker unavailable;
- control version unavailable;
- false-positive warning;
- timeout and crash artifacts.

---

# 32. Codex operating procedure

Use this cycle for every milestone and non-trivial task:

```markdown
### Task
State one concrete deliverable.

### Plan
List inputs, exact files expected to change, risks, and pass criteria.

### Implement
Make the smallest coherent patch.

### Test
Run the relevant unit, integration, security, and golden-output tests.

### QA review
Inspect the diff, logs, schemas, artifacts, and security behavior.

### Revise
Correct every identified defect or record a reproducible blocker.

### Status
PASS, FAIL, or BLOCKED.
```

Maintain:

## `TODO.md`

```markdown
# TODO

## Current milestone
- [ ] Concrete task
  - Inputs:
  - Outputs:
  - Verification command:
  - Status: NOT STARTED | IN PROGRESS | BLOCKED | PASS
```

## `DECISIONS.md`

```markdown
# Architecture decisions

## ADR-0001: <title>
- Date:
- Status: proposed | accepted | superseded
- Context:
- Decision:
- Alternatives considered:
- Consequences:
- Evidence/links:
```

## `BLOCKERS.md`

```markdown
# Blockers

## BLOCK-0001: <title>
- Date:
- Source/plugin:
- Source revision:
- Redot binary hash:
- Godot control hash:
- Reproduction command:
- Expected result:
- Actual result:
- Log path:
- Attempts made:
- Smallest next experiment:
```

Do not mark a task PASS when:

- required tests were skipped without explanation;
- warnings are unexplained;
- a timeout or crash remains;
- a required platform was not tested;
- a result was inferred without preserving evidence;
- dynamic code ran outside the configured trust model.

---

# 33. Immediate Codex start sequence

1. Create the repository and file tree.
2. Initialize the Python project with uv.
3. Add runtime and development dependencies with bounded version ranges; commit `uv.lock`.
4. Define all enums and Pydantic models first.
5. Generate initial JSON Schemas.
6. Implement stable CLI exit-code handling.
7. Implement local source acquisition and safe extraction.
8. Add malicious-archive tests before adding network adapters.
9. Implement plugin-root and package-kind detection.
10. Implement version-evidence collection and the 4.5.2 baseline gate.
11. Produce a working `redot-compat inspect` command.
12. Implement Redot `doctor` and engine snapshots.
13. Implement the API index/diff.
14. Build the disposable fixture factory.
15. Implement the trusted runner using only synthetic fixtures.
16. Implement and validate the Docker worker.
17. Add the editor/runtime harnesses and sentinel protocol.
18. Add the deterministic classifier and reports.
19. Add Godot differential testing.
20. Add GitHub, Codeberg, Asset Library, and batch workflows.
21. Run the full acceptance checklist before declaring version 1.0.

The first useful deliverable is the static `inspect` command. The first dynamic deliverable is a Docker-isolated import/editor/runtime test of the trusted fixtures. Do not begin by testing arbitrary third-party plugins on the host.

---

# 34. Primary references

## Redot

- Redot engine: https://github.com/Redot-Engine/redot-engine
- Redot 26.2 stable tag: https://github.com/Redot-Engine/redot-engine/tree/redot-26.2-stable
- Redot 26.2 release: https://github.com/Redot-Engine/redot-engine/releases/tag/redot-26.2-stable
- Redot release announcements: https://blog.redotengine.org/2026/
- Redot command line: https://docs.redotengine.org/tutorials/editor/command_line_tutorial
- Redot GDExtension C++ example: https://docs.redotengine.org/tutorials/scripting/gdextension/gdextension_cpp_example
- Redot `.gdextension` format: https://docs.redotengine.org/tutorials/scripting/gdextension/gdextension_file
- Redot C++ bindings: https://github.com/Redot-Engine/redot-cpp

## Godot plugin model

- Installing editor plugins: https://docs.godotengine.org/en/stable/tutorials/plugins/editor/installing_plugins.html
- Making editor plugins: https://docs.godotengine.org/en/stable/tutorials/plugins/editor/making_plugins.html
- Running code in the editor: https://docs.godotengine.org/en/stable/tutorials/plugins/running_code_in_the_editor.html
- `EditorInterface`: https://docs.godotengine.org/en/4.5/classes/class_editorinterface.html

## Godot distribution sources

- Godot Asset Library: https://godotengine.org/asset-library/
- Asset Library API repository: https://github.com/godotengine/godot-asset-library
- Asset Library API documentation: https://github.com/godotengine/godot-asset-library/blob/master/API.md
- Godot Asset Store: https://store.godotengine.org/
- Asset Store documentation: https://docs.godotengine.org/en/stable/community/asset_store/what_is_asset_store.html

## GitHub and Codeberg

- GitHub repository archive API: https://docs.github.com/en/rest/repos/contents
- GitHub releases API: https://docs.github.com/en/rest/releases
- GitHub release assets API: https://docs.github.com/en/rest/releases/assets
- Codeberg tags and releases: https://docs.codeberg.org/git/using-tags/
- Codeberg repository guide: https://docs.codeberg.org/getting-started/first-repository/
- Gitea/Forgejo API usage: https://docs.gitea.com/1.25/development/api-usage

## Tooling and security

- uv: https://docs.astral.sh/uv/
- Typer: https://typer.tiangolo.com/
- Pydantic: https://docs.pydantic.dev/
- HTTPX: https://www.python-httpx.org/
- pytest: https://docs.pytest.org/
- Ruff: https://docs.astral.sh/ruff/
- mypy: https://mypy.readthedocs.io/
- Docker security: https://docs.docker.com/engine/security/
- Docker run controls: https://docs.docker.com/engine/containers/run/

---

# 35. Final instruction to Codex

Build the tester in the milestone order above. Preserve evidence for every conclusion. Apply the Godot 4.5.2 baseline gate before running plugin code. Prefer an immutable source revision, a matching Godot control, and an isolated worker. Never label a plugin as requiring a Redot port merely because it is new, and never label it compatible merely because the editor process closed without an explicit successful harness result.
