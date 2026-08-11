# Redot plugin compatibility tester — preflight report

Prepared: 2026-08-10  
Target: Redot 26.2 LTS on Windows x86-64, with a Linux x86-64 container worker  
Plan reviewed: `redot_plugin_compatibility_tester_codex_plan.md` v1.0  
Decision: **Conditional GO**

> **Post-implementation update (2026-08-10):** This report preserves the evidence and decisions as they stood at preflight. The clean-archive Redot failure, missing exact Godot control, unavailable Docker profile, missing Mono editor, and unproven containment gates were subsequently closed. See [`references/gate-closure-evidence.md`](references/gate-closure-evidence.md) for the verified identities and two-run captures. The historical tables below are not current blocker status.

## Outcome

Proceed with the static `inspect` path and the repository/contracts work in Milestones 0–1. The external Python orchestrator plus small disposable Redot harnesses is a sound shape for the problem, and no direct end-to-end alternative was found in the bounded search.

Do not mark Milestone 2 complete or begin arbitrary third-party dynamic testing yet. The configured Redot 26.2 editor reports the expected identity and exposes the required command flags, but both bounded attempts to generate `extension_api.json` crashed with signal 11. An official tagged API snapshot is now bundled, and it structurally matches the workspace cache except for build labels, so schema/index work can begin while the local engine issue is resolved.

Before implementation, amend the plan in six places: use package-type-specific version evidence; make the Asset Library/Store metadata secondary; replace the assumed shared Redot–Rust layer with an experimental godot-rust custom-JSON path; require Windows Job Objects; make archive safeguards explicit in the Python extraction contract; and strengthen the Docker threat model.

## Scope and assumptions

- “computability tester” was interpreted as “compatibility tester” because the supplied plan, folder name, product taxonomy, and requested destination all describe plugin compatibility.
- This pass gathered research, source records, API material, risks, and decisions. It did not implement or execute the tester.
- No `project.godot`, implementation plan under `docs/gamedev`, codebase, or existing workbook was present in `plugins/compatester`; the supplied Codex plan was the only product file before this pass.
- No untrusted plugin, build script, archive payload, or downloaded executable was run.
- Current web/API claims were checked against primary project documentation, tagged source, or official package registries on 2026-08-10.

## Research questions and decisions

| Question | Answer | Decision |
|---|---|---|
| Is Redot 26.2 really based on the Godot 4.5.2 API lineage? | Yes. Tagged `version.py`, the local executable, and both API snapshots agree. | Preserve product `26.2` and compatibility `4.5.2` as separate fields. |
| Are the harness APIs available? | Yes in the tagged API: plugin enable/query and GDExtension load/reload/unload are present. | Keep the harness design; prove runtime behavior with trusted fixtures. |
| Can the configured engine generate its own API snapshot? | No in this environment; two bounded attempts crashed. | Block the Milestone 2 gate; use the tagged snapshot only as development evidence. |
| Is marketplace version metadata authoritative enough to lead target detection? | No. The legacy Asset Library has one weak version field, ignores patch filters, and publishes no useful download hash. The Store is beta/private implementation. | Reorder evidence by package type and directness. |
| Is a shared Redot–Rust compatibility layer available? | None was identified. godot-rust supports custom API JSON directly. | Remove the assumed layer; validate `api-custom-json` in trusted optional work. |
| Is Docker sufficient for hostile native plugins? | It materially reduces risk but is not a universal security boundary. | Keep it as default Linux containment; document residual risk and design VM isolation. |
| Is there a simpler existing tester to adopt? | No end-to-end match was found. Three adjacent tools cover CI, parsing, or unit tests only. | Build the narrow static inspector first; borrow patterns, not dependencies. |

## Materials assembled

- [`source-of-truth.xlsx`](source-of-truth.xlsx) — canonical source, decision, milestone, QA, risk, release, and marketing ledgers.
- [`references/redot-26.2-extension-api.json`](references/redot-26.2-extension-api.json) — official Redot 26.2 tagged API material.
- [`references/godot-4.5-extension-api.json`](references/godot-4.5-extension-api.json) — clearly labeled Godot 4.5.0 reference, not a 4.5.2 control.
- [`references/redot-26.2-engine-evidence.md`](references/redot-26.2-engine-evidence.md) — local identity, hashes, official release digests, flag check, structural API comparison, and crash record.
- [`references/evidence-audit.md`](references/evidence-audit.md) — retained PASS/FAIL/BLOCKED findings from two same-reviewer adversarial passes.
- [`references/research-query-log.md`](references/research-query-log.md) — bounded query ledger, including unresolved searches.

## 1. Engine identity and API feasibility

The [Redot 26.2 release](https://github.com/Redot-Engine/redot-engine/releases/tag/redot-26.2-stable) resolves to commit `4f5b14abade2239104847d03d8f9056e4467cfcd`. The tagged [`version.py`](https://raw.githubusercontent.com/Redot-Engine/redot-engine/redot-26.2-stable/version.py) declares Redot `26.2` and Godot `4.5.2`. The configured editor reports `26.2.stable.official.4f5b14aba`, so the product, lineage, and source commit agree.

The exact tagged [`redot-cpp`](https://github.com/Redot-Engine/redot-cpp) binding snapshot exists at commit `598ec78e86b2c240a023f6de13daba70f7de8610`. It contains 993 engine classes and the methods required by the proposed harness. Its body is structurally identical to the existing workspace API cache in all compared sections; only the build label changes from `redot.custom_build` to `redot.official`.

This gives the project a usable, licensed, immutable API fixture. It does not close the doctor gate: the configured editor crashed while dumping the API in both headless and windowed bounded attempts. Resolve that against a clean, digest-verified official archive before claiming local snapshot reproducibility. Details and hashes are in [`redot-26.2-engine-evidence.md`](references/redot-26.2-engine-evidence.md).

Redot documentation currently labels itself 26.1 on relevant pages, so the installed 26.2 build and tagged data are authoritative for version-specific behavior. Godot 4.5 documentation remains a design reference, not proof of Redot behavior.

## 2. Architecture assessment

The proposed split survives the preflight:

- external Python process owns acquisition, normalization, policy, timeouts, secrets, provenance, and reports;
- a small editor harness owns editor-only activation checks;
- a small runtime harness owns engine runtime checks;
- disposable workspaces prevent changes to source projects and user editor state;
- isolated workers treat plugin scripts and native libraries as code execution.

This is the minimum coherent boundary for the product. An ordinary in-editor plugin could not safely supervise its own crash, hang, or process tree. Keep the static `inspect` command as the first useful deliverable and avoid build adapters until the trusted optional milestone.

## 3. Compatibility evidence must be package-type-specific

The universal ranking in plan section 12.2 should be replaced. Recommended precedence:

| Package kind | Strongest evidence first | Secondary evidence | Weak/corroborating only |
|---|---|---|---|
| Prebuilt GDExtension | Hash and inspect each selected binary; exact API/binding snapshot or lock; `.gdextension` selectors and compatibility bounds | Exact binding tag/submodule, CI build matrix, release build recipe | Store/library version, README, release date |
| C++ source | Exact `redot-cpp`/`godot-cpp` commit or tag; embedded API JSON; build lock | CMake/SCons configuration and CI matrix | Branch name, badge, marketplace field |
| Rust source | Locked `godot` crate version; `api-*` feature or `api-custom-json`; API JSON hash | Cargo lock, CI matrix, README | Crate publish date or repository branch name |
| C#/.NET | `Godot.NET.Sdk` version in project/lock; target framework; configured Mono engine identity | CI matrix and release artifacts | Marketplace version or release date |
| Pure GDScript | Parsed project feature version and concrete symbol evidence against API snapshots | Plugin manifest, CI matrix, explicit release documentation | Marketplace minimum, badge, branch name |

Always retain conflicting evidence instead of selecting one field silently. In particular, an old declared minimum cannot override a newer native binding or prebuilt binary.

The plan's `NO_PORT_NEEDED_BASELINE_POLICY` remains an authoritative project rule, but it must stay distinct from `COMPATIBLE_TESTED`. A baseline skip saves test resources; it does not prove package layout, platform artifacts, editor activation, or runtime behavior. Preserve `--force-test-baseline`.

## 4. Source acquisition contracts

### GitHub

Use the [repository archive endpoints](https://docs.github.com/en/rest/repos/contents) only after resolving mutable refs through the [Git refs API](https://docs.github.com/en/rest/git/refs). Request the archive by full commit, record redirects, and hash the received bytes. For release assets, record asset ID, name, size, timestamps, content type, and the [published digest when present](https://docs.github.com/en/rest/releases/assets), then independently hash the bytes. A release tag name is provenance, not the immutable identity by itself.

### Codeberg/Forgejo

Do not freeze the adapter to a Gitea 1.25 contract. [Forgejo documents API changes across major versions](https://forgejo.org/docs/latest/user/api/usage/) and exposes per-instance OpenAPI. Probe the instance version and capabilities, retain representative OpenAPI/JSON fixtures in contract tests, and keep a shallow fixed-commit Git fallback. Treat a named [release attachment](https://docs.codeberg.org/git/using-tags/) and the auto-generated source archive as different artifacts.

### Godot Asset Library and Store

The legacy [Asset Library API](https://github.com/godotengine/godot-asset-library/blob/master/API.md) exposes a single `godot_version`; its patch component is disregarded by the filter, and the official `download_hash` is always empty. Record its metadata, but independently hash the download and resolve the repository to an immutable revision where possible.

The [Asset Store is beta](https://docs.godotengine.org/en/stable/community/asset_store/what_is_asset_store.html), its implementation is private, and listings use varied licenses. Keep the MVP metadata-only: never infer a reusable license or public download from “free”; require a public source/archive and explicit license, or stop with an actionable request.

## 5. Hostile archive contract

The plan names the right threats but must translate them into executable invariants:

- preflight every member before writing any file;
- normalize separators and Unicode, reject absolute/drive/UNC/device paths, traversal, reserved Windows names, duplicate/case-colliding outputs, special files, hard links, and symlinks by default;
- enforce compressed bytes, expanded bytes, per-file bytes, entry count, path length, nesting depth, and expansion ratio before and during extraction;
- extract into a new empty run-owned directory and remove the partial tree on any failure;
- for Python 3.12 TAR, explicitly use [`filter="data"`](https://docs.python.org/3.12/library/tarfile.html#extraction-filters) as defense in depth in addition to manual validation;
- for ZIP, do not use [`zipfile.Path`](https://docs.python.org/3.12/library/zipfile.html) for extraction, because it does not sanitize names; inspect external attributes for symlinks and validate the resolved destination with `commonpath`;
- test CRCs and create each malicious fixture programmatically without committing a real expansion bomb.

## 6. Execution containment and process control

### Windows trusted host

Use an argument-array process API and assign the engine to a [Windows Job Object](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) immediately after creation. Configure `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` so controller failure still tears down descendants. Use psutil for telemetry, descendant evidence, and fallback cleanup—not as the sole race-free containment guarantee.

Host execution remains trusted-only and requires explicit consent. Isolate `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `TEMP`, and `TMP`; never inherit normal Redot editor state.

### Docker Linux worker

Keep no-network, read-only root, dropped capabilities, no-new-privileges, PID/memory/CPU limits, read-only input, and no Docker socket. Add:

- image references pinned by digest and recorded in results;
- an explicit non-root numeric `--user` and rootless/user-namespace operation where available;
- isolated `HOME`/XDG/cache directories on bounded tmpfs;
- bounded scratch and a copy-out step or a carefully scoped output mount;
- seccomp/AppArmor/SELinux profile identity in provenance;
- a stated residual-risk boundary: Docker is not a universal defense against hostile native code or kernel exploits.

A disposable VM/remote worker remains the stronger future backend for intentionally hostile native submissions and Windows-only DLLs.

## 7. Native and managed language paths

### C++

Adopt exact [`redot-cpp` tags](https://github.com/Redot-Engine/redot-cpp), never `master`, for Redot rebuild work. The 26.2 tag is verified to exist. Static inspection should compare the binary selector actually chosen for OS, architecture, build type, precision, and feature tags. Never load candidate libraries in the Python orchestrator.

### Rust

No maintained shared Redot–Rust layer was identified. The maintained [godot-rust](https://github.com/godot-rust/gdext) project is MPL-2.0 and exposes `api-4-5` plus [`api-custom-json`](https://godot-rust.github.io/book/toolchain/godot-version.html), using `GDRUST_GODOT_API_JSON`. Treat that as the concrete adaptation hypothesis. Validate a tiny trusted extension against the bundled Redot JSON before promising a port path, and record the exact crate/lock/API hashes. Do not fork godot-rust merely to satisfy the plan text.

### .NET

[`Godot.NET.Sdk` 4.5.0](https://www.nuget.org/packages/Godot.NET.Sdk/4.5.0) is MIT-licensed and valid version evidence. Redot publishes a separate 26.2 Mono archive, so the standard local editor and a help flag are not sufficient proof of .NET capability. Register, hash, and doctor a specific Redot Mono executable before running `dotnet build`; otherwise return a missing-capability status.

## 8. Python/tooling recommendation and licenses

Use a lockfile and separate runtime, presentation, and development dependencies.

| Component | License | Recommendation | Reason |
|---|---|---|---|
| Pydantic | MIT | Adopt | Versioned public result models and generated JSON Schema justify it. |
| HTTPX | BSD-3-Clause | Adopt | Async HTTP, redirects, streaming limits, headers, and test transports fit the adapters. |
| packaging | Apache-2.0 or BSD-2-Clause | Adopt | Use the canonical PEP 440 parser; do not invent version comparison. |
| platformdirs | MIT | Adopt | Cross-platform cache/config roots reduce host-state mistakes. |
| psutil | BSD-3-Clause | Adapt | Telemetry and fallback cleanup only; Job Objects/process groups provide the guarantee. |
| Typer | MIT | Adopt | The multi-command CLI is large enough to justify declarative parsing. |
| Rich | MIT | Optional | Presentation only; JSON/Markdown output must not depend on it. |
| pytest | MIT | Adopt for development | Fixtures and parametrization fit the malicious archives and classifier matrix. |
| Ruff | MIT | Adopt for development | Fast lint/format gate. |
| mypy | MIT | Adopt for development | Useful at process, schema, and provider boundaries. |
| uv | Apache-2.0 or MIT | Adopt as tooling | Lock/sync workflow; pin the tool in CI. |

The licenses are compatible with the planned MIT project at the direct-dependency level. This is not a release clearance: generate an SBOM and scan the exact direct/transitive lock before distribution. If godot-rust itself is modified and distributed, honor MPL-2.0 file-level source obligations.

## 9. Comparable tools

| Tool | What it proves | Decision |
|---|---|---|
| [`godot-ci`](https://github.com/abarichello/godot-ci) | MIT Docker images and CI patterns for trusted Godot exports | Inspiration for image layout only; not a hostile-code security model. |
| [GDScript Toolkit](https://github.com/Scony/godot-gdscript-toolkit) | MIT parser/linter/formatter independent of the engine | Reject as a core dependency; optional advisory lint after MVP because it can lag engine grammar and cannot prove runtime compatibility. |
| [GUT](https://github.com/bitwes/Gut) | MIT unit-test framework with Godot CLI/version patterns | Reject as the generic harness; arbitrary plugins do not share GUT tests. Borrow JUnit/CLI reporting ideas only. |

No direct tool was found that combines immutable acquisition, hostile extraction, Redot/Godot engine control, native inventory, differential execution, deterministic classification, and reproducible evidence. This is a bounded search result, not proof of global absence.

## 10. Required plan amendments before coding

1. Replace section 12.2's universal evidence ranking with the package-type-specific table above.
2. State explicitly that `NO_PORT_NEEDED_BASELINE_POLICY` is a policy skip, not a tested compatibility claim.
3. Correct Asset Library expectations to one weak `godot_version` field; never rely on `download_hash`.
4. Make Codeberg/Forgejo version/capability probing and contract fixtures part of the adapter acceptance gate.
5. Add exact Python TAR/ZIP extraction invariants and partial-failure cleanup to section 11.
6. Require a kill-on-close Windows Job Object in section 15; demote psutil to telemetry/fallback.
7. Pin Docker images by digest, name the LSM/seccomp profile, set an explicit user, isolate HOME/XDG, and state the residual-risk boundary.
8. Replace “shared Redot–Rust compatibility layer” with a researched `godot-rust api-custom-json` experiment unless a maintained layer is later identified.
9. Add “clean official archive reproduces API dump” to the Milestone 2 gate and retain archive digest/extraction provenance.
10. Keep Godot 4.5.0 reference data separate from an exact 4.5.2 control; never let the classifier silently substitute it.

## 11. Milestone gate impact

| Milestone | Preflight state | Required gate adjustment |
|---|---|---|
| 0 — contracts | GO | Apply the policy/tested distinction, threat model, dependency lock, and schema provenance fields. |
| 1 — static inspect | GO | Implement provider capability probing, exact commit resolution, hostile extraction invariants, and package-specific evidence. |
| 2 — doctor/API diff | BLOCKED on configured editor | Tagged Redot JSON may seed unit work; pass only after a clean verified editor generates a fresh deterministic snapshot. |
| 3 — trusted process runner | CONDITIONAL GO | Trusted synthetic fixtures only; Job Object/process group/container ownership tests are mandatory. |
| 4 — Docker | CONDITIONAL GO | Add digest pinning, explicit user/rootless posture, isolated HOME/XDG, bounded output, and escape-residual documentation. |
| 5–9 | DEFER | Follow the plan after earlier gates pass. Do not execute arbitrary third-party plugins in ordinary PR CI. |
| 10 — trusted builds | RESEARCH ONLY | Exact redot-cpp tag is available; Rust custom JSON is an experiment; build scripts remain opt-in and isolated. |

## 12. Priority risks

| ID | Priority | Risk | Mitigation / proof required |
|---|---|---|---|
| R-001 | Critical | Configured Redot crashes during API dump. | Reproduce from clean verified ZIP; retain archive digest; replace install or file upstream issue; rerun bounded doctor. |
| R-002 | Critical | Dynamic testing executes arbitrary editor scripts/native code. | Static-first gate; Docker restrictions; trusted-host consent; stronger VM backend; no public PR execution. |
| R-003 | High | Baseline policy is misread as runtime proof. | Separate status, evidence fields, report language, and force-test path. |
| R-004 | High | Marketplace metadata misclassifies native targets. | Package-specific evidence precedence and conflict retention. |
| R-005 | High | Descendants survive timeout/controller failure. | Job Objects, POSIX process groups, container stop/remove, and explicit timeout fixtures. |
| R-006 | High | Provider/API drift breaks acquisition or immutability. | Resolve commits, hash bytes, probe Forgejo, retain response fixtures, test redirects. |
| R-007 | High | Archive traversal/bombs/collisions damage the worker. | Preflight, explicit TAR filter, ZIP validation, quotas, unique empty target, cleanup, malicious fixtures. |
| R-008 | Medium | Rust port path is promised around a nonexistent layer. | Use custom JSON experiment; retain unresolved status until compiled/loaded fixture passes. |
| R-009 | Medium | Local executable provenance cannot be reconstructed. | Retain original release archive or a signed extraction manifest; verify published digest. |
| R-010 | Medium | A Linux-only result is generalized across platforms. | Platform-scoped results and explicit missing-binary states; aggregate only like-for-like evidence. |

## 13. Unresolved items

- Root cause of the Redot 26.2 Windows API-dump crash and whether it reproduces from a clean official archive.
- Exact Godot 4.5.2 control API snapshot; the bundled Godot reference is 4.5.0 only.
- A configured Redot 26.2 Mono executable and successful minimal C# fixture.
- Live Codeberg instance version/OpenAPI behavior at implementation time.
- Whether the beta Asset Store will expose a stable public API and redistribution terms suitable for automation.
- A maintained Redot-specific Rust layer, if one is created later.
- Exact locked dependency versions, transitive licenses, vulnerabilities, and SBOM.

## 14. Adversarial review result

The retained audit is in [`references/evidence-audit.md`](references/evidence-audit.md). It contains two separate `SELF_REVIEW` passes by the same reviewer; no independent-review claim is made. The totals are 10 FAIL, 3 BLOCKED, and 3 PASS. Every failed finding above changed either the recommendation or a milestone gate.

## 15. Start criteria

Implementation may start when the plan amendments are accepted into the working specification. Milestones 0 and 1 can proceed immediately afterward. Before Milestone 2 is closed or any third-party dynamic test runs:

- verify a clean Redot archive against its published digest;
- produce a fresh bounded API dump or record a confirmed upstream blocker;
- prove full process-tree termination with synthetic fixtures;
- prove the archive corpus cannot escape or exhaust configured limits;
- run only trusted fixtures in the initial host/container path;
- preserve the baseline-policy/tested distinction in schema, CLI, and reports.

That yields a practical first slice: a safe, deterministic `inspect` command backed by evidence strong enough to decide whether dynamic testing is warranted.
