# Redot Plugin Compatibility Tester — implementation plan

Prepared: 2026-08-10  
Status: Alpha implementation complete for the current local scope; G-02, G-03, G-05, and the optional Mono capability are closed  
Decision gate: Local GO for the implemented trusted-host and Docker paths; canonical G-01 CI, the full G-04 matrix, and G-06 remain open  
Canonical project root: D:/Claude Vault/redot/plugins/compatester  
Canonical source of truth: source-of-truth.xlsx  
Research basis: preflight-report.md and references/

## Implementation closure update — 2026-08-10

The plan below remains the canonical design and gate definition. Implementation has since closed the preflight engine, exact-control, process-containment, Docker, and Mono blockers. The immutable identities, fixture hashes, commands, and two-run captures are recorded in [`references/gate-closure-evidence.md`](references/gate-closure-evidence.md). Statements below that describe a fixture or prerequisite as future work are retained as the original acceptance contract; the milestone table, binding obligations, and risk register reflect the current state.

## Planning assumptions and confirmation basis

- The user's request to turn the supplied v1.0 draft and completed preflight into the full plan is treated as confirmation of the product destination and release boundary. A separate game-design interview would add no useful product information for this developer tool.
- The supplied redot_plugin_compatibility_tester_codex_plan.md remains design-source material. This file is the canonical executable plan.
- Implementation will live directly in plugins/compatester. Do not create a redundant nested redot-plugin-compat-tester repository.
- Redot is the engine under test. The orchestrator is Python 3.12 or newer; the only in-engine implementation language is typed GDScript. C++, Rust, and .NET are package kinds to inspect or optional trusted build targets, not implementation languages for the tester.
- The owner is recorded as Project because team composition, budget, and individual ownership were not supplied.
- Calendar dates are deliberately deferred. Milestone gates, not speculative dates, control progress.
- Version 1.0 ends after Milestone 9. Milestone 10 trusted build adapters is optional post-core work and cannot delay the 1.0 release.
- The original configured Redot 26.2 editor's API-dump crash is retained as preflight history. G-02 was later closed with a digest-verified clean official archive and two isolated deterministic dumps.

## 1. Destination

The finished product is an offline-first command-line tool named redot-compat. A plugin porter gives it a local package or an immutable remote source; the tool safely inventories the package, applies the project’s Godot 4.5.2 baseline policy, and—only when trust and containment gates permit—runs reproducible Redot phases with an optional exact Godot control. It returns a stable classification, confidence, decisive evidence, and commands that reproduce the conclusion.

Version 1.0 is finished when one operator can:

1. inspect local archives/directories and fixed GitHub or Codeberg artifacts without executing plugin code;
2. reject hostile archives and retain immutable provenance;
3. doctor a verified Redot 26.2 installation and generate deterministic API evidence;
4. run trusted fixtures through disposable projects and a hardened Linux container worker;
5. distinguish import, activation, runtime, native, platform, timeout, crash, upstream, and Redot-specific outcomes;
6. compare the same normalized package against an explicitly configured matching Godot control;
7. produce schema-valid result.json, report.md, codex_port_brief.md, and reproduction scripts;
8. run a resumable batch and package a reproducible wheel, source distribution, worker image, schemas, checksums, and SBOM.

Automatic porting, arbitrary build execution, a hosted submission service, and claims of full functional parity are not part of this destination.

## 2. Audience and constraints

### Audience and operating experience

- Primary users: Redot plugin porters, add-on maintainers, release engineers, and reviewers deciding whether port work is warranted.
- Primary interaction: keyboard-driven CLI and generated files. No GUI is required for the tester itself.
- Typical single run: a static result in seconds to tens of seconds; a dynamic run is bounded by named phase timeouts and may take minutes.
- Batch runs may be long-lived, but every item is independently resumable and reproducible.

### Platform and engine constraints

| Constraint | Confirmed target |
|---|---|
| Development host | Windows x86-64 |
| Default dynamic worker | Linux x86-64 container |
| Redot product identity | 26.2 stable |
| Compatibility lineage | Godot 4.5.2 |
| Orchestrator runtime | Python 3.12 or newer |
| Engine harness language | Typed GDScript |
| Control engine | User-supplied, exact binary identity and hash |
| Local engine source | REDOT_BIN; verify with the installed executable before version-specific work |
| Network | Disabled during dynamic execution unless a manifest and explicit operator approval allow it |
| Host execution | Trusted source plus explicit --allow-unsafe-host-execution |
| Warnings | Unexplained warnings are unfinished work |

### Accessibility and presentation constraints

- Every command must work with color disabled and without an interactive terminal.
- Status cannot rely on color alone; text labels and stable exit codes are authoritative.
- JSON and Markdown output must contain the same conclusion and evidence identifiers.
- Errors must name the failed phase, the next action, and the retained evidence path.
- Terminal output must remain bounded; full logs go to files.

### Performance and resource budgets

- Static inspection of the canonical 10,000-entry synthetic corpus must finish within 30 seconds and 1 GiB peak resident memory on the canonical two-vCPU/four-GiB Linux CI worker.
- Default dynamic limits are: doctor 30 seconds, import 180 seconds, per-script parse 20 seconds, editor 120 seconds, runtime 120 seconds, GUI 180 seconds, and export 600 seconds.
- Container defaults are two CPUs, four GiB memory, 256 processes, and a one-GiB temporary filesystem unless a fixture documents a different bounded need.
- A timeout is a result, not permission to extend limits silently.

### Production constraints

- No calendar, staffing, budget, package registry, release host, or signing identity is confirmed.
- Use the direct dependency set evaluated in preflight, but freeze exact versions in uv.lock before code is accepted.
- Do not publish externally in this planning session or during implementation without explicit authorization.

## 3. Design pillars

1. **Evidence before claims.** Every conclusion traces to immutable source bytes, engine identity, phase evidence, and deterministic rules.
2. **Static first, execution last.** Acquisition and inspection run without plugin code. Dynamic work is inaccessible until trust and containment gates pass.
3. **Scope every result.** A baseline-policy skip is not tested compatibility; a Linux result is not a Windows result; a process exit is not a successful harness result.
4. **Contain failure outside the engine.** The external process owns timeouts, process trees, logs, credentials, workspaces, and cancellation because the engine cannot reliably supervise its own crash or hang.
5. **Small public contracts, replaceable internals.** Version schemas and status enums; add modules only when a milestone gives them a distinct responsibility.

### Confirmed decisions index

The detailed rationale and source links live in the Decisions sheet of source-of-truth.xlsx.

| ID | Confirmed decision |
|---|---|
| DEC-001 | Proceed conditionally with Milestones 0–1; retain later gates. |
| DEC-002 | Store Redot 26.2 product identity separately from Godot 4.5.2 compatibility lineage. |
| DEC-003 | Keep baseline-policy skip separate from tested compatibility. |
| DEC-004 | Use package-type-specific version-evidence precedence. |
| DEC-005 | Resolve mutable refs to full commits and hash received bytes. |
| DEC-006 | Require explicit TAR data filtering, ZIP member preflight, quotas, empty targets, and cleanup. |
| DEC-007 | Use kill-on-close Windows Job Objects as the descendant-termination guarantee. |
| DEC-008 | Keep Docker as the default Linux containment layer with explicit residual risk. |
| DEC-009 | Trial godot-rust api-custom-json; do not assume a shared Redot–Rust layer. |
| DEC-010 | Adopt the evaluated Python stack with runtime/presentation/development boundaries and a lockfile. |
| DEC-011 | Use tagged Redot JSON for early unit work but block the fresh doctor/API gate. |
| DEC-012 | Treat Asset Library/Store fields as corroborating metadata only. |
| DEC-013 | Keep the Redot harness minimal, typed, co-located, data-driven, and free of autoload/game scaffolding. |
| DEC-014 | Implement directly in plugins/compatester with docs/gamedev/implementation-plan.md as the canonical plan. |
| DEC-015 | Make static local inspect plus hostile-archive/golden evidence the first end-to-end vertical slice. |
| DEC-016 | Permit dynamic execution only after trust and containment gates; public PR CI uses trusted repository fixtures only. |
| DEC-017 | Treat versioned result.json as authoritative; all human reports and summaries are derived. |
| DEC-018 | Define version 1.0 as Milestones 0–9 with wheel/sdist/worker/SBOM; HTML and standalone executables are deferred. |
| DEC-019 | Keep trusted build adapters optional post-core work requiring separate approval and isolation. |
| DEC-020 | Require exact configured engine identities; the bundled Godot 4.5.0 JSON is reference-only, never a 4.5.2 control. |

## 4. Product rules

### Core operator loop

1. Accept a source specification and operator options.
2. Resolve mutable provider names to a full commit or release artifact identity.
3. Hash received bytes and record redirects and metadata.
4. Preflight every archive member, then extract into a new empty run-owned directory.
5. Detect plugin roots, package kind, native selectors, and version evidence.
6. Apply package-specific evidence precedence and preserve conflicts.
7. If authoritative effective target is 4.5.2 or earlier and force-test is absent, return NO_PORT_NEEDED_BASELINE_POLICY without executing the package.
8. Otherwise require an eligible sandbox and configured engine, construct disposable fixtures, and run only selected phases.
9. Optionally mirror the normalized package and phase configuration under an exact Godot control.
10. Normalize findings, apply the ordered classifier, render reports, and retain reproduction material.

### Terminal states and semantics

- A successful run always ends in one documented CompatibilityResult status and one stable process exit code.
- NO_PORT_NEEDED_BASELINE_POLICY is a policy terminal state. It never implies COMPATIBLE_TESTED.
- COMPATIBLE_UNCHANGED requires every required phase to produce explicit success evidence.
- A Redot-specific high-confidence port conclusion normally requires a matching Godot control pass or direct native/API proof.
- A failure in both engines is upstream/package/fixture evidence, not a Redot blame assignment.
- Missing worker capability, display, service, binary, .NET engine, or exact control produces a scoped missing/inconclusive status.
- Tester failure outranks plugin classification; unsafe or malformed input is rejected before dynamic work.

### Edge cases

- Multiple independent plugin roots require --plugin-id or a manifest; never choose silently.
- A declared old minimum cannot override a newer native binding, binary selector, locked crate, or SDK.
- Release date, branch name, badge, star count, and marketplace version are corroborating evidence only.
- A tag name is never the immutable identity; resolve it to a full commit and hash the received artifact.
- A package with only Windows binaries cannot pass a Linux worker. Record MISSING_PLATFORM_BINARY for that worker.
- A plugin that prints text resembling harness events cannot create success; only schema-valid, ordered harness events combined with engine/phase evidence are accepted. This prevents accidental spoofing, not malicious same-process forgery.
- Simultaneous timeout and crash evidence retains both facts; the classifier applies documented precedence and explains it.
- Partial extraction, partial download, partial report generation, and cancelled work are cleaned or marked incomplete; they are never cached as valid.

### Content and persistence

- Persistent state is limited to immutable content-addressed cache entries, engine snapshots, run directories, and explicit configuration.
- Each run owns its HOME/XDG or USERPROFILE/AppData/temp roots.
- Credentials are accepted only through supported environment/config channels, redacted before persistence, and never copied into reproduction scripts.
- result.json is authoritative. Markdown, Codex brief, summaries, and optional future HTML are derived views.

## 5. Presentation

The product has no game camera, art, animation, VFX, or audio pipeline. Its presentation layer is intentionally narrow:

- Typer defines commands and machine-stable options.
- Rich may improve interactive tables and progress, but is optional; plain text remains complete.
- --json or file output never contains ANSI styling.
- report.md begins with conclusion, confidence, scope, and next action before detailed evidence.
- codex_port_brief.md contains only the evidence needed to begin a port.
- result.json uses a versioned public schema and stable enum values.
- Report links use relative artifact paths so a run directory remains portable.
- No Blender, Blockbench, GPT Image, screenshots, or marketing assets are required.

## 6. Technical design

### Current state

The project contains planning/research artifacts only. There is no project.godot, Python package, harness, test suite, or release configuration. Implementation must not pretend prior code or architecture exists.

### Runtime architecture

    Source specification
      -> source adapter and immutable provenance
      -> hostile archive preflight/extractor
      -> static inventory and version-evidence resolver
      -> baseline policy decision
      -> disposable fixture factory
      -> sandbox backend and process owner
      -> Redot phases and optional exact Godot control phases
      -> log/event parser and API correlator
      -> ordered classifier
      -> result.json and derived reports

The Python orchestrator owns every control-plane decision. The Redot harnesses only perform engine-context checks requested by a generated probe configuration.

### Incremental repository shape

Create files only in the milestone that needs them. The expected mature structure is:

    plugins/compatester/
      pyproject.toml
      uv.lock
      README.md
      SECURITY.md
      CHANGELOG.md
      TODO.md
      DECISIONS.md
      BLOCKERS.md
      src/redot_compat/
        cli.py
        config.py
        constants.py
        errors.py
        models/
        sources/
        archive/
        inspect/
        engines/
        workspace/
        runner/
        sandbox/
        phases/
        logs/
        classify/
        reports/
        cache/
      harness/
        base_project/
          project.godot
          main.tscn
          runtime_probe.gd
        editor_plugin/
          plugin.cfg
          plugin.gd
      schemas/
      examples/
      docker/
      tests/
        unit/
        contract/
        integration/
        golden/
        fixtures/
        gauntlet/
      docs/
        gamedev/
        classifications.md
        manifests.md
        sandboxing.md
        adding-source-adapters.md
        adding-test-probes.md
        troubleshooting.md

Do not create every empty package at bootstrap. Add a package when its first task lands.

### Public data contracts

- SourceProvenance records requested and canonical locations, provider, immutable revision, release/asset identity, redirects, timestamps, size, digest, and license candidates.
- EngineIdentity stores product version and compatibility lineage separately, plus path, hashes, platform, architecture, precision, .NET capability, version/help evidence, and API snapshot identity.
- VersionEvidence stores the source, raw and normalized values, meaning, package applicability, confidence, and notes.
- PluginInventory stores roots, IDs, package kinds/languages, entry points, native selectors, project files, version evidence, effective target, conflicts, and baseline decision.
- PhaseResult stores exact argument arrays, redacted environment, start/end/duration, exit/signal/timeout, logs, ordered events, findings, artifacts, and state.
- CompatibilityResult stores schema version, source/inventory/policy/engines/platform/phases/findings, final classification, confidence, port-candidate flag, next action, tester version, and reproduction data.
- Schemas are generated from Pydantic models, versioned separately from the CLI, and validated against golden examples.

### Source and version evidence

Package-specific precedence from preflight is binding:

| Package kind | Decisive evidence | Secondary evidence | Weak evidence |
|---|---|---|---|
| Prebuilt GDExtension | Selected binary hash; exact API/binding snapshot or lock; manifest selectors/bounds | Exact binding tag/submodule; CI build matrix | Marketplace version, README, date |
| C++ source | Exact redot-cpp/godot-cpp commit; embedded API JSON; lock | Build configuration and CI matrix | Branch, badge, marketplace |
| Rust source | Locked godot crate; api feature or api-custom-json; API hash | Cargo lock and CI | Publish date, branch |
| C#/.NET | Godot.NET.Sdk version/lock; target framework; exact Mono identity | CI and release artifacts | Marketplace/date |
| Pure GDScript | Parsed project feature version plus concrete symbols against API snapshots | Plugin manifest, CI, explicit release docs | Marketplace, badge, branch |

Conflicts are retained; they reduce confidence or force dynamic testing. Marketplace data never overrides direct package evidence.

### Harness scene and script organization

- Use a tiny co-located harness, not a general game-project scaffold.
- base_project/main.tscn has one root Node and runtime_probe.gd. No player input, viewport target, audio, assets, or autoloads are required.
- editor_plugin/plugin.gd is an @tool EditorPlugin with explicit typed variables, parameters, return types, and typed collections supported by the installed Redot API.
- Keep probes in named methods; use match with a default branch for probe dispatch.
- Await only bounded frame/timer signals and check instance validity after an await when the node may be freed.
- Do not add class_name unless another harness script genuinely needs global registration.
- Generated JSON supplies data; the harness does not parse TOML.
- Use Redot scene/resource tooling for new or complex scene/resource edits when available; use native edits for GDScript.

### Harness event protocol

Every harness line starts with REDOT_COMPAT_EVENT followed by JSON containing schema, run_id, sequence, event, and payload. The parser enforces:

- known schema and event names;
- matching run ID;
- strictly increasing sequence;
- exactly one start and one normal terminal event;
- required event order;
- no success if required probes or terminal event are missing;
- corroboration with the phase exit, logs, and activation/runtime checks.

This is an integrity protocol against malformed, duplicated, or accidental output—not a cryptographic boundary against malicious code running in the same engine process.

### Execution containment

- TrustedHostBackend requires explicit consent and a trusted source designation.
- Windows starts the engine suspended when necessary, assigns it to a kill-on-close Job Object, then resumes it. psutil is telemetry/fallback only.
- POSIX phases run in a new process group and terminate the whole group.
- Docker uses a digest-pinned image, explicit non-root numeric user, no network, read-only root, dropped capabilities, no-new-privileges, PID/CPU/memory limits, bounded tmpfs, isolated HOME/XDG, read-only input, controlled output copy-out, and recorded seccomp/LSM profile.
- Never mount the Docker socket or inject ordinary user credentials.
- Docker reduces risk; it is not a universal hostile-native-code boundary. Intentionally hostile native submissions require a later disposable VM/remote worker.

### API snapshots and engine authority

- Run the resolved REDOT_BIN --version before using version-specific features.
- The installed Redot build, generated API output, and successful bounded runs are authoritative.
- docs/gamedev/references/redot-26.2-extension-api.json may seed schema/index tests, but cannot pass the local doctor reproducibility gate.
- docs/gamedev/references/godot-4.5-extension-api.json is Godot 4.5.0 reference material only, never an exact 4.5.2 control.
- No engine is silently downloaded or executed. Automatic acquisition can be reconsidered only after checksum/provenance support exists.

## 7. Preflight research brief

The completed preflight was commissioned to answer:

- whether Redot 26.2 and Godot 4.5.2 identities align;
- whether required editor/harness APIs exist;
- whether the configured engine can produce a fresh API snapshot;
- which package metadata is authoritative by plugin type;
- how GitHub, Codeberg/Forgejo, Asset Library, and Asset Store acquisition must be normalized;
- what Python archive invariants are required;
- which primitive guarantees full process-tree termination on Windows;
- what Docker can and cannot guarantee;
- whether a maintained Redot–Rust layer or existing end-to-end tester can be adopted;
- which dependencies and licenses are acceptable.

Required references included tagged Redot/Godot API material, installed-engine output, official provider and language documentation, security documentation, package registries, and adjacent tooling. Stopping criteria were: one implementation-affecting answer or a clearly retained unresolved state for every question; bounded alternative search; no untrusted code execution; and an adversarial evidence audit.

Research is complete for planning. Detailed evidence remains in [preflight-report.md](preflight-report.md), [the reference index](references/README.md), and [the retained audit](references/evidence-audit.md).

## 8. Preflight findings

### Adopt

- External Python orchestrator with small disposable editor/runtime harnesses.
- Dual Redot 26.2 and Godot 4.5.2 identity.
- Tagged Redot 26.2 API JSON for early deterministic unit work.
- Exact redot-cpp tags for optional trusted C++ work.
- Typer, Pydantic, HTTPX, packaging, platformdirs, pytest, Ruff, mypy, and uv with a lockfile.
- Static local/GitHub/Codeberg inspection as the first useful product.

### Adapt

- Replace one universal version ranking with package-specific precedence.
- Resolve tags/latest to full commits; record redirects and hash downloaded bytes.
- Probe Forgejo instance/version/capabilities and retain contract fixtures.
- Treat Asset Library and beta Asset Store metadata as corroborating only.
- Use manual TAR/ZIP preflight, explicit TAR data filtering, quotas, empty targets, and failure cleanup.
- Use Job Objects for Windows ownership; psutil remains telemetry/fallback.
- Harden Docker and record residual risk rather than calling it a complete sandbox.
- Treat godot-rust api-custom-json as an experiment, not an existing shared Redot layer.

### Reject or defer

- Baseline-policy skip as proof of tested compatibility.
- GDScript Toolkit or GUT as the generic compatibility harness.
- Arbitrary third-party code in ordinary pull-request CI.
- Arbitrary build scripts in version 1.0.
- HTML reports and standalone executables as version 1.0 gates.
- A public hosted execution service.

### Binding blockers and obligations

- G-02 is closed: a digest-verified clean Redot archive produced two identical fresh API snapshots.
- G-05 is closed locally with a separately verified Godot 4.5.2 control; the bundled 4.5.0 reference remains reference-only.
- The optional .NET capability is proven with a separately verified Redot 26.2 Mono editor and minimal trusted fixture.
- G-03 is closed for the Windows Job Object and hardened Linux Docker profiles. Host execution remains trusted-only, and Docker's residual isolation risk remains documented.
- Exact dependency versions, transitive licenses, vulnerabilities, and SBOM remain version 1.0 release gates until the final G-06 candidate audit.
- Arbitrary hostile native submissions still require stronger disposable-machine isolation; the implemented worker does not claim a universal sandbox boundary.

## 9. Milestones and Gauntlet gates

### Milestone sequence

| ID | Runnable, observable outcome | Dependencies | Completion gate | State |
|---|---|---|---|---|
| MS-001 | redot-compat version and schema export run from a locked package; sample results validate. | Accepted plan and preflight | Format, lint, type, unit, schema, dependency-license checks pass with no unexplained warnings. | Implemented locally |
| MS-002 | redot-compat inspect produces deterministic JSON/Markdown for local, HTTP, GitHub, and Codeberg trusted fixtures without executing plugin code. | MS-001 | Hostile archive corpus passes; immutable provider evidence passes; G-01 passes. | Implemented; canonical Linux G-01 CI capture pending |
| MS-003 | redot-compat doctor and engine snapshot/diff produce content-addressed Redot evidence from a clean verified editor. | MS-001; clean official Redot archive | Fresh bounded dumps are deterministic; dual identity and provenance are correct; G-02 passes. | Complete — G-02 passed twice |
| MS-004 | A disposable trusted fixture runs through the host runner; timeout/controller failure leaves no descendants or user-state changes. | MS-002, MS-003 | Windows Job Object/POSIX ownership, log bounds, redaction, cancellation, and G-03 host scenarios pass. | Complete for Windows profile — G-03 passed twice |
| MS-005 | The same trusted fixture runs in a digest-pinned, non-root Linux worker with no network or unapproved writes. | MS-004 | Worker provenance and restrictions are recorded; G-03 container scenarios pass. | Complete for local Docker profile — G-03 passed twice |
| MS-006 | Typed Redot editor/runtime harnesses distinguish activation success, activation failure, runtime failure, timeout, and missing capability. | MS-003, MS-005 | Event state machine and trusted phase fixtures pass; G-04 passes; bounded Redot logs contain no unexplained warnings. | Alpha subset implemented; full G-04 matrix pending |
| MS-007 | Every fixture receives a deterministic classification, confidence, next action, reports, exit code, and reproduction scripts. | MS-006 | Every taxonomy/precedence collision has golden coverage and schemas validate. | Alpha classification/report surface implemented |
| MS-008 | The same package is mirrored under Redot and an exact Godot control, producing scoped differential evidence. | MS-003, MS-007; exact control binaries | Redot-only, both-engine, control-mismatch, and missing-control cases pass G-05. | Complete locally — G-05 passed twice |
| MS-009 | Batch manifests, cache reuse, resume, Asset Library metadata, and cautious Asset Store handling work without cross-run corruption. | MS-002, MS-007 | Aggregate counts reconcile to individual result files and provider contract fixtures pass. | Deferred |
| MS-010 | Export/native/platform paths and release packaging produce a reproducible 1.0 candidate. | MS-005 through MS-009 | Platform scope, SBOM, checksums, docs, CI, and G-06 pass; full 1.0 checklist is green. | Deferred |
| MS-011 | Optional trusted build adapters prove explicitly approved redot-cpp, CMake, godot-rust custom-JSON, or .NET recipes in isolation. | Stable 1.0 core | Each adapter has a separate threat review, exact dependency locks, and trusted fixtures. | Optional; exact Redot Mono recipe proven locally |

No later milestone may be marked complete while a dependency is blocked. Work that can be isolated behind a fake or trusted fixture may be prototyped, but it cannot close the dependent milestone.

### Common Gauntlet protocol

Gauntlets supplement normal acceptance tests only where claims are security-sensitive, comparison-dependent, or difficult to recover from.

- Immutable oracle definitions live in tests/gauntlet/oracles/ and are reviewed before the implementation they judge.
- Golden expected results live in tests/golden/. Generated captures go to the gitignored .artifacts/gauntlet/<gate>/<run-id>/ directory.
- Every capture records source/fixture hash, tester version, command argument array, redacted environment, OS/container profile, engine hashes, start/end/duration, exit/signal/timeout, logs, result JSON, and comparison summary.
- Oracle status is one of OBSERVED, INFERRED, BLOCKED, or WAIVED. A WAIVED item requires owner, rationale, expiry, and release consequence.
- Critics are read-only. Applicable named lenses are Security, Reproducibility, Classification, Operator Clarity, and Redot Runtime, followed by one unlensed review. Each returns PASS, FAIL, or BLOCKED with artifact citations.
- Retests use the same fixture hashes and profile. An implementation attempt cannot change its own expected result; changing an oracle requires a separate decision and a new oracle version.
- Raw pixel equality is never used. This CLI/harness has no visual identity; observable state, events, files, limits, timing, and memory are the comparison measures.

### G-01 — static inspect vertical slice

- **Risk and round cap:** high archive/classification risk; at most three implementation-review rounds.
- **Frozen references:** preflight-report.md sections 3–5 (OBSERVED); Python 3.12 tarfile and zipfile primary documentation URLs recorded in Sources (OBSERVED); future fixture paths tests/fixtures/baseline_gdscript_pass and tests/fixtures/unsafe_archives (BLOCKED until CT-M1-02 creates them and records SHA-256 in the oracle).
- **Canonical scenario:** on the two-vCPU/four-GiB Linux CI profile, run redot-compat inspect first on the baseline directory, then on each generated unsafe ZIP/TAR, with network disabled and an empty cache.
- **Inputs and behavior:** the baseline fixture yields one selected plugin root, pure-GDScript inventory, effective target at or below 4.5.2, NO_PORT_NEEDED_BASELINE_POLICY, port_candidate false, and zero executed phases. Every hostile archive is rejected before the first filesystem write outside its empty extraction root; a partial tree is removed.
- **Measures:** exact schema/status/evidence IDs; archive digest; zero phase records; no modified source file; no extraction escape; deterministic normalized result in two runs; baseline corpus within 30 seconds and one GiB peak RSS. Timestamps, run IDs, and absolute temporary paths are allowed differences and are normalized before golden comparison.
- **Capture command:** uv run pytest -q tests/gauntlet/test_static_inspect_oracle.py, which invokes the real CLI and writes .artifacts/gauntlet/G-01/.
- **Critics:** Security, Reproducibility, Classification, Operator Clarity, then unlensed.
- **PASS:** all scenarios and critics pass in two consecutive clean runs. **FAIL:** wrong status, any execution, escape/write, non-cleanup, nondeterministic semantic output, resource-budget breach, or unresolved warning. **BLOCKED:** fixture hash or canonical profile is unavailable.
- **Consequence:** MS-002 cannot close and no dynamic milestone may start. This is the first selected vertical slice and must implement the minimum deterministic capture/normalization harness plus one end-to-end golden comparison.

### G-02 — engine identity, provenance, and API determinism

- **Risk and round cap:** critical provenance/runtime risk; at most three rounds.
- **Frozen references:** official Redot Windows ZIP digest 4644c7591bbe8019b861deb0ccdb64fd4f59a88514abf7c788cf176c259855af (OBSERVED); references/redot-26.2-extension-api.json SHA-256 453A0CC128BB58333A001F7F43573A5961D973FB7B151AF43139869F22D5915C (OBSERVED); references/redot-26.2-engine-evidence.md and references/gate-closure-evidence.md (OBSERVED); clean executable SHA-256 5633D02A28A73514084DF6A60FFE01FABDBBB9AC5E28FDFD590ED47277F51989 and fresh dump SHA-256 177E7796166929B2193C9CCE2FD32F59601A0147D0D1E7FE904B94E8F69F6577 (OBSERVED twice).
- **Canonical scenario:** verify the retained official archive digest, extract with a recorded manifest, run doctor in isolated Windows user/temp roots, and perform two bounded fresh API dumps from separate empty directories. No -d flag is permitted; every engine invocation has --quit-after of at least 2 when applicable plus an external wall-clock timeout.
- **Measures:** product 26.2; compatibility lineage 4.5.2; full tag commit; executable and archive hashes; required flags; clean import; two fresh canonical API bodies byte-equivalent after only documented build-label normalization; expected API structural sections and harness methods present. The custom/official build label is an allowed difference; class/method/signature/body differences are not.
- **Capture command:** uv run pytest -q tests/gauntlet/test_engine_snapshot_oracle.py --integration-redot <verified-console-path>.
- **Critics:** Reproducibility, Redot Runtime, Security, Classification, then unlensed.
- **PASS:** provenance is complete and both fresh runs agree. **FAIL:** wrong identity, unrecorded substitution, semantic API drift, leaked host state, or unexplained warning. **BLOCKED:** crash, timeout, missing official archive, or missing required capability.
- **Consequence:** MS-003 and every engine-execution milestone remain blocked. A confirmed upstream issue may explain the block but does not convert it to PASS.

### G-03 — process and worker containment

- **Risk and round cap:** critical arbitrary-code containment risk; at most three rounds.
- **Frozen references:** Windows Job Object contract and Docker restrictions in preflight-report.md section 6 (OBSERVED); implemented timeout/controller-failure/write/network fixtures and final worker identity in references/gate-closure-evidence.md (OBSERVED twice).
- **Canonical scenarios:** child spawns a grandchild and hangs; controller exits unexpectedly; fixture attempts an out-of-root write; container fixture attempts network access; cancellation races with normal exit.
- **Profiles:** Windows x86-64 trusted host with isolated USERPROFILE/AppData/TEMP; Linux x86-64 digest-pinned worker, numeric non-root user, two CPUs, four GiB, 256 PIDs, one-GiB tmpfs, no network, no Docker socket, read-only input/root.
- **Measures:** all owned processes disappear within five seconds on host and ten seconds for container stop/remove; two later probes find no run-ID process; no file appears outside allowed roots; network attempt fails; output and logs remain bounded; cleanup is idempotent. Normal exit-vs-cancel winner may differ only when the race is explicitly recorded.
- **Capture command:** uv run pytest -q tests/gauntlet/test_containment_oracle.py --integration-host; Docker cases use the same test with --integration-docker and write one combined capture.
- **Critics:** Security, Reproducibility, Operator Clarity, then unlensed.
- **PASS:** every profile/scenario meets limits twice. **FAIL:** surviving descendant/container, write/network escape, secret leakage, unbounded output, or ambiguous ownership. **BLOCKED:** required host/container capability is unavailable.
- **Consequence:** host or container dynamic execution stays disabled for the failed profile; no third-party dynamic run is permitted.

### G-04 — harness activation/runtime evidence

- **Risk and round cap:** high engine-context correctness risk; at most three rounds.
- **Frozen references:** tagged Redot API snapshot and hash from G-02 (OBSERVED); EditorInterface method presence (OBSERVED); future trusted success, activation-fail, runtime-fail, and malformed-event fixture hashes (BLOCKED).
- **Canonical profile:** verified Redot 26.2, headless, Forward+ or engine default recorded, 1280×720 only when a display-backed fallback is required, isolated project/user roots, wait 30 editor frames and 30 runtime frames unless fixture specifies otherwise.
- **Scenarios:** clean activation; exception in editor _enter_tree; runtime-only error; missing resource; out-of-order/duplicate/malformed event lines; normal completion without terminal event.
- **Measures:** exact ordered event state machine, plugin-enabled state, required load/probe outcomes, phase exit, first decisive error, duration, no post-terminal success mutation, no unexplained warnings. Display pixels are not compared. A same-process malicious forgery remains an explicit allowed threat limitation, not a passed security claim.
- **Capture command:** uv run pytest -q tests/gauntlet/test_harness_oracle.py --integration-redot <verified-console-path>.
- **Critics:** Redot Runtime, Classification, Reproducibility, Security, then unlensed.
- **PASS:** each fixture maps to its frozen phase outcome twice. **FAIL:** activation/runtime conflation, malformed events creating success, missing terminal evidence accepted, hang, crash, or warning. **BLOCKED:** verified Redot profile unavailable.
- **Consequence:** MS-006 cannot close and classifier golden results cannot be treated as engine-proven.

### G-05 — Redot versus Godot differential classification

- **Risk and round cap:** critical comparison/classification risk; at most three rounds.
- **Frozen references:** exact Redot engine identity from G-02 (OBSERVED); exact Godot 4.5.2 control archive/executable/API hashes and generated post-baseline API-gap fixture/configuration hashes in references/gate-closure-evidence.md (OBSERVED twice).
- **Canonical profile:** same normalized source hash, selected plugin root, platform/architecture, fixture layout, renderer, manifest, environment policy, phase list, frame counts, and timeouts under both engines.
- **Scenarios and exact outcomes:** PASS/PASS -> COMPATIBLE_UNCHANGED; Redot FAIL/control PASS -> matching port-required status; FAIL/FAIL -> UPSTREAM_PACKAGE_FAILURE or invalid fixture; Redot PASS/control FAIL -> INCONCLUSIVE; Redot TIMEOUT/control PASS -> TIMEOUT with port_candidate true; Redot CRASH/control PASS -> crash plus the evidence-selected port category.
- **Measures:** paired phase configuration hashes equal; control selected by documented rule; no 4.5.0 reference substitution; exact classification/confidence reasons; API symbol correlation; missing control lowers confidence and cannot produce high-confidence Redot blame.
- **Capture command:** uv run pytest -q tests/gauntlet/test_differential_oracle.py --redot <path> --godot-control <path>.
- **Critics:** Classification, Redot Runtime, Reproducibility, Operator Clarity, then unlensed.
- **PASS:** every matrix row and precedence collision matches its golden result. **FAIL:** mismatched fixtures, wrong blame, silent control substitution, or nondeterminism. **BLOCKED:** exact control or generated real API-gap fixture unavailable.
- **Consequence:** MS-008 cannot close; reports may describe Redot-only failures only as low/medium-confidence unproven specificity.

### G-06 — version 1.0 release, platform, accessibility, and performance

- **Risk and round cap:** high release/supply-chain risk; at most two rounds after feature freeze.
- **Frozen references:** version 1.0 checklist in this plan (INFERRED until all prior gates pass); uv.lock, SBOM, image digest, source commit, platform matrices, and signing identity (BLOCKED until release candidate).
- **Canonical profiles:** Windows x86-64 trusted-fixture job; Linux x86-64 Docker job; optional .NET job only with exact Redot Mono identity; no macOS claim without a macOS job.
- **Measures:** quality commands pass; schemas and golden reports unchanged except approved schema migration; static 10,000-entry budget passes; all phase timeouts enforced; plain/no-color CLI remains readable; JSON/Markdown conclusions agree; wheel/sdist/image hashes are recorded; image runs non-root; SBOM and license/vulnerability review have no unaccepted critical finding; clean install reproduces the version.
- **Capture command:** uv run pytest -q tests/gauntlet/test_release_oracle.py followed by the documented CI release dry run; generated outputs go to .artifacts/gauntlet/G-06/.
- **Critics:** Security, Reproducibility, Classification, Operator Clarity, Redot Runtime, then unlensed.
- **PASS:** all mandatory profiles and critics pass with no blocked release item. **FAIL:** generalized untested platform claim, inaccessible status, artifact mismatch, critical supply-chain finding, regression, crash, timeout, or warning. **BLOCKED:** required platform, SBOM, lock, image, or release destination decision unavailable.
- **Consequence:** no 1.0 tag or publication.

## 10. Task breakdown

Every task uses a failing test or fixture first when behavior can be specified, then the minimum implementation, then a diff/log/artifact review. A task cannot be PASS if its named verification was skipped.

### MS-001 — repository and public contracts

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M0-01 | Initialize the Python project directly at plugins/compatester. DEC-010, DEC-014 | Plan complete | pyproject.toml, uv.lock, src/redot_compat/__init__.py, tests/, .gitignore, .gitattributes | Python >=3.12; package imports; no redundant nested repo; generated outputs ignored. | uv sync --frozen; uv run python -c "import redot_compat" |
| CT-M0-02 | Expose version and no-op CLI command routing. DEC-014 | CT-M0-01 | __main__.py, cli.py, constants.py | redot-compat version returns semantic version and exit 0 in plain and JSON modes. | uv run redot-compat version; uv run redot-compat version --json |
| CT-M0-03 | Define stable enums and Pydantic contracts, including policy-vs-tested distinction. DEC-002, DEC-003 | CT-M0-01 | models/source.py, engine.py, inventory.py, phase.py, finding.py, result.py | All required preflight fields exist; invalid enum/schema inputs fail; no free-form final status. | uv run pytest -q tests/unit/test_models.py |
| CT-M0-04 | Generate and version public JSON Schemas plus golden samples. DEC-003, DEC-017 | CT-M0-03 | schemas/*.schema.json, tests/golden/schema/, schema command | Generation is deterministic; valid samples pass; incompatible sample changes require schema decision. | uv run redot-compat schema export --check; uv run pytest -q tests/unit/test_schema.py |
| CT-M0-05 | Define configuration, platform directories, and secret-redaction contract. DEC-010, DEC-016 | CT-M0-03 | config.py, runner/redaction.py, examples/redot-compat.toml | No token/credential appears in repr, logs, errors, result, or reproduction data. | uv run pytest -q tests/unit/test_config.py tests/unit/test_redaction.py |
| CT-M0-06 | Freeze architecture, security, classifications, task, decision, and blocker records. DEC-013 through DEC-020 | CT-M0-02 through CT-M0-05 | README.md, SECURITY.md, TODO.md, DECISIONS.md, BLOCKERS.md, docs/classifications.md | Documents agree with schemas/CLI; Docker residual risk and host consent are prominent. | uv run pytest -q tests/unit/test_docs_contract.py |
| CT-M0-07 | Install quality gates and trusted-only CI. DEC-010, DEC-016 | CT-M0-01 | Ruff/mypy/pytest config, .github/workflows/quality.yml | Format, lint, strict boundary typing, and tests run without executing engines or third-party plugins. | uv run ruff format --check .; uv run ruff check .; uv run mypy src; uv run pytest -q |
| CT-M0-08 | Freeze dependencies and initial license/supply-chain evidence. DEC-010 | CT-M0-01 | uv.lock, dependency manifest/report in .artifacts or docs/release | Direct/transitive packages are enumerated; license exceptions and vulnerabilities are recorded; no floating CI install. | uv sync --frozen; documented license/vulnerability commands; manual lock diff |
| CT-M0-09 | Close the runnable repository/contracts gate. DEC-001 | CT-M0-02 through CT-M0-08 | CI artifact with CLI/schema output | All M0 commands pass twice from a clean environment; no unexplained warning. | Full quality command set plus clean reinstall |

### MS-002 — safe acquisition and static inspect

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M1-01 | Define ResolvedArtifact/adapter protocol and safe local directory/archive acquisition. DEC-005 | CT-M0-03 | sources/base.py, sources/local.py, cache/hash.py | Local source is copied, never modified; provenance and streamed SHA-256 are complete. | uv run pytest -q tests/unit/test_local_source.py |
| CT-M1-02 | Generate hostile ZIP/TAR fixtures and implement preflight extraction invariants. DEC-006 | CT-M1-01 | archive/safety.py, archive/extract.py, tests/fixtures/unsafe_archives/ | Reject traversal, absolute/drive/UNC/device/reserved paths, links, special files, collisions, excessive depth/count/size/ratio; TAR uses data filter; partial targets are removed. | uv run pytest -q tests/unit/test_archive_safety.py |
| CT-M1-03 | Detect bounded plugin roots and package kinds. DEC-004 | CT-M1-01 | inspect/roots.py, plugin_cfg.py, project_godot.py, gdextension.py, dotnet.py, rust.py | Multiple roots remain explicit; engine module/full project/mixed package are distinct; no file executes. | uv run pytest -q tests/unit/test_inventory.py |
| CT-M1-04 | Statistically inspect native selectors/artifacts without loading them. DEC-004 | CT-M1-03 | inspect/native.py | Selected OS/arch/build/precision/features and missing artifacts are recorded; Python never uses dlopen/ctypes on candidate libraries. | uv run pytest -q tests/unit/test_native_inventory.py |
| CT-M1-05 | Implement package-specific version evidence and conflict retention. DEC-004, DEC-012 | CT-M1-03, CT-M0-03 | inspect/version_evidence.py, inspect/license.py | Evidence precedence matches section 6; weak marketplace/date evidence cannot override direct package evidence. | uv run pytest -q tests/unit/test_version_evidence.py |
| CT-M1-06 | Apply the 4.5.2 baseline policy without claiming tested compatibility. DEC-002, DEC-003 | CT-M1-05 | inspect/baseline.py, result model fields | <=4.5.2 decisive target skips execution; conflicts/unknown/newer targets request testing; force flag is retained. | uv run pytest -q tests/unit/test_baseline_policy.py |
| CT-M1-07 | Deliver first end-to-end local inspect JSON/Markdown slice. DEC-015, DEC-017 | CT-M1-02 through CT-M1-06 | CLI inspect command, reports/inspect_json.py, reports/inspect_markdown.py | Baseline fixture yields exact policy status, evidence, no phases, exit 10; source remains unchanged. | uv run redot-compat inspect tests/fixtures/baseline_gdscript_pass --json; golden comparison |
| CT-M1-08 | Add bounded direct HTTPS archive acquisition. DEC-005 | CT-M1-01 | sources/http_archive.py | HTTPS default, redirect/host/size/signature/MIME limits, streamed hash, partial cleanup, secret redaction. | uv run pytest -q tests/unit/test_http_archive.py |
| CT-M1-09 | Resolve GitHub refs/releases/assets immutably. DEC-005 | CT-M1-08 | sources/github.py, tests/contract/github/ | Tags/latest resolve to full commits; redirects/digests/asset metadata retained; bytes independently hashed. | uv run pytest -q tests/contract/test_github.py |
| CT-M1-10 | Probe Forgejo/Codeberg capability and retain fixed-commit fallback. DEC-005 | CT-M1-08 | sources/codeberg.py, tests/contract/codeberg/ | Instance version/OpenAPI capability recorded; attachment/source archive distinct; full-commit Git fallback tested. | uv run pytest -q tests/contract/test_codeberg.py |
| CT-M1-11 | Implement G-01 capture, normalization, and immutable oracles. DEC-015, DEC-016 | CT-M1-02 through CT-M1-10 | tests/gauntlet/test_static_inspect_oracle.py, tests/gauntlet/oracles/G-01.*, tests/golden/inspect/ | Fixture hashes frozen; only allowed volatile fields normalized; two clean end-to-end results agree. | G-01 command and critic records |
| CT-M1-12 | Document source forms, baseline semantics, archive limits, and static-only safety. DEC-003, DEC-005, DEC-006 | CT-M1-11 | README.md, docs/troubleshooting.md, examples/ | Examples run; docs never call policy skip tested compatibility. | Docs contract test plus manual command copy/paste |

### MS-003 — engine doctor, snapshots, and API diff

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M2-01 | Register explicit Redot/control binaries and compute identity/hashes. DEC-002, DEC-020 | CT-M0-03 | engines/registry.py, engines/identity.py | Product/compatibility fields separate; path, platform, arch, precision, .NET capability, version/help hashes retained. | uv run pytest -q tests/unit/test_engine_identity.py |
| CT-M2-02 | Implement bounded doctor checks in isolated engine state. DEC-011 | CT-M2-01 | engines/doctor.py, CLI doctor | Version/help/headless/base import/required flags checked; no -d; external timeout and --quit-after >=2 where applicable. | uv run redot-compat doctor --redot <path> --output <dir> |
| CT-M2-03 | Rehydrate Redot from the official archive and record supply-chain provenance. DEC-011 | CT-M2-02 | checksum manifest, extraction manifest, BLOCKERS.md evidence | Published ZIP digest verified; extracted file hashes bound to archive; source URL and extraction tool/version recorded. | Get-FileHash or platform SHA-256 plus doctor provenance test |
| CT-M2-04 | Generate two fresh content-addressed extension API snapshots. DEC-011 | CT-M2-03 | engines/snapshot.py, cache API objects | Separate empty runs succeed and semantic bodies agree; failures retain logs and remain BLOCKED. | Bounded snapshot integration test; never retry indefinitely |
| CT-M2-05 | Build deterministic indexes for classes/members/signals/constants/enums/utilities/types. DEC-011 | CT-M0-04, tagged API fixture | engines/api_index.py | Tagged Redot fixture indexes deterministically and exposes required harness APIs. | uv run pytest -q tests/unit/test_api_index.py |
| CT-M2-06 | Diff Redot and exact configured Godot APIs. DEC-020 | CT-M2-01, CT-M2-05 | engines/api_diff.py | Added/removed/signature/property/constant changes are stable and schema-valid; 4.5.0 reference is labeled reference-only. | uv run pytest -q tests/unit/test_api_diff.py |
| CT-M2-07 | Register exact Godot 4.5.2 control evidence without substitution. DEC-020 | CT-M2-02 | engine config/docs, control snapshot | Exact binary/hash/API identity retained; absence is explicit and lowers capability. | doctor/snapshot against configured control |
| CT-M2-08 | Run G-02 and close or retain the API-dump blocker. DEC-011 | CT-M2-03 through CT-M2-07 | G-02 oracle/captures, BLOCKERS.md | All G-02 criteria pass; crash/timeout remains BLOCKED with smallest next experiment. | G-02 command and critics |

### MS-004 — disposable workspace and trusted process runner

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M3-01 | Create unique run directories and immutable input/inventory snapshots. DEC-016, DEC-017 | MS-002, MS-003 | workspace/factory.py, workspace/cleanup.py | Every run owns paths; source/cache objects remain read-only; cleanup is idempotent. | uv run pytest -q tests/unit/test_workspace_factory.py |
| CT-M3-02 | Install only the selected add-on into a minimal fixture. DEC-016 | CT-M3-01 | workspace/install.py, workspace/project_config.py | Harness/project files cannot be overwritten; ambiguous paths fail; explicit manifest can add only declared paths. | uv run pytest -q tests/unit/test_fixture_install.py |
| CT-M3-03 | Isolate Windows and POSIX user/config/cache/temp directories. DEC-007, DEC-016 | CT-M3-01 | runner/environment.py | Required variables point inside run root; inherited secrets removed/redacted; ordinary editor dirs unchanged. | uv run pytest -q tests/unit/test_environment.py |
| CT-M3-04 | Implement argument-array asynchronous process execution and bounded logs. DEC-007 | CT-M0-05 | runner/process.py, runner/limits.py, runner/commands.py | No shell; separate and combined timestamped logs; max size; timeout; cancellation; exact redacted args retained. | uv run pytest -q tests/unit/test_process_runner.py |
| CT-M3-05 | Guarantee Windows descendant ownership with kill-on-close Job Objects. DEC-007 | CT-M3-04 | runner/windows_job.py | Child/grandchild assigned before untrusted work; handle closure kills group; psutil only confirms/fallbacks. | Windows containment fixture tests |
| CT-M3-06 | Guarantee POSIX process-group ownership and deterministic teardown. DEC-007 | CT-M3-04 | runner/posix_group.py | Timeout/cancel/controller cleanup targets full group; no unrelated PID is touched. | Linux containment fixture tests |
| CT-M3-07 | Produce complete raw PhaseResult artifacts for a trusted synthetic import. DEC-017 | CT-M3-02 through CT-M3-06 | phases/import_phase.py, run logs/events/artifacts | Result distinguishes tester/engine/plugin failure; source and user state unchanged. | trusted fixture bounded import integration test |
| CT-M3-08 | Execute G-03 host scenarios. DEC-007, DEC-016 | CT-M3-05 through CT-M3-07 | tests/fixtures/containment/, G-03 host captures | Job/process-group scenarios pass twice; no leaks/warnings. | G-03 --integration-host |

### MS-005 — Docker Linux containment

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M4-01 | Build a digest-pinned worker as a numeric non-root user. DEC-008 | MS-004 | docker/Dockerfile.worker, checksum/source manifest | Base and Redot inputs pinned/verified; no latest tag; no root runtime. | docker build plus image history/config inspection |
| CT-M4-02 | Define a minimal worker request/response and entrypoint. DEC-008, DEC-017 | CT-M4-01 | docker/entrypoint.sh, sandbox/worker_protocol.py | One run request maps to one owned run result; malformed request cannot broaden mounts/commands. | uv run pytest -q tests/unit/test_worker_protocol.py |
| CT-M4-03 | Implement backend selection and explicit unsafe host consent. DEC-008, DEC-016 | CT-M3-04 | sandbox/base.py, docker_linux.py, trusted_host.py | auto chooses eligible Docker; host refuses absent trust plus consent; reason appears in result. | uv run pytest -q tests/unit/test_backend_selection.py |
| CT-M4-04 | Apply no-network/read-only/capability/resource/tmpfs/identity restrictions. DEC-008 | CT-M4-01, CT-M4-03 | Docker command builder and provenance fields | No socket; read-only root/input; bounded output/scratch; isolated HOME/XDG; seccomp/LSM/userns posture recorded. | command golden test plus container inspection |
| CT-M4-05 | Copy outputs out safely and remove owned containers on every terminal path. DEC-008 | CT-M4-02 through CT-M4-04 | sandbox/docker_linux.py, cleanup tests | Output paths cannot escape; partial output marked; timeout/cancel/controller failure removes container. | integration cleanup/race tests |
| CT-M4-06 | Add Xvfb capability without UI automation. DEC-008 | CT-M4-01 | worker packages, GUI command path | Display-backed start is available for trusted fixtures; no arbitrary click/image automation is implied. | bounded Xvfb engine start fixture |
| CT-M4-07 | Run G-03 Docker write/network/resource/teardown scenarios. DEC-008, DEC-016 | CT-M4-04 through CT-M4-06 | G-03 Docker captures | Every container restriction passes twice; digest/profile retained. | G-03 --integration-docker |
| CT-M4-08 | Document containment boundaries and VM roadmap. DEC-008 | CT-M4-07 | SECURITY.md, docs/sandboxing.md | Residual kernel/daemon/mount risk and unsupported Windows/macOS claims are explicit. | Docs contract and security critic |

### MS-006 — Redot editor and runtime harnesses

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M5-01 | Create the minimal Redot base project and main scene. DEC-013, DEC-016 | MS-003, MS-005 | harness/base_project/project.godot, main.tscn | One root Node, no autoloads/input/assets, unique project/user data, Redot 26.2 compatible. | Redot static resource check; bounded empty scene run |
| CT-M5-02 | Implement the typed runtime probe dispatcher. DEC-013, DEC-017 | CT-M5-01 | harness/base_project/runtime_probe.gd | Typed functions/collections; known probe match plus default; bounded waits; one start/probe/terminal sequence. | Redot code validation; trusted runtime fixture |
| CT-M5-03 | Implement the typed @tool editor harness. DEC-013, DEC-017 | CT-M5-01 | harness/editor_plugin/plugin.cfg, plugin.gd | Enables/checks selected target, performs only generated probes, guards failures, emits ordered terminal evidence, quits deterministically. | Redot code validation; trusted activation fixture |
| CT-M5-04 | Define and validate plugin-test.toml, then generate harness JSON. DEC-017 | CT-M0-03, CT-M5-02 | models/manifest.py, schemas/manifest.schema.json, examples/plugin-test.toml | No arbitrary code strings; only supported probe types/paths/timeouts; JSON is deterministic and scoped. | uv run pytest -q tests/unit/test_manifest.py |
| CT-M5-05 | Parse harness events as a strict state machine. DEC-017 | CT-M0-03 | logs/sentinel.py | Schema/run/sequence/order/terminal checks enforced; malformed/duplicate/out-of-order lines cannot create success. | uv run pytest -q tests/unit/test_sentinel.py |
| CT-M5-06 | Implement import and context-aware supplementary GDScript parse phases. DEC-016 | CT-M3-07 | phases/import_phase.py, phases/parse_phase.py | Each phase bounded and reproducible; editor-only/non-standalone scripts are skipped or downgraded with reason. | trusted pass/parse-fail integration fixtures |
| CT-M5-07 | Implement editor, runtime, and display-backed phase orchestration. DEC-016, DEC-017 | CT-M5-02 through CT-M5-06, CT-M4-06 | phases/editor_phase.py, runtime_phase.py, gui_phase.py | Activation and runtime failures remain distinct; DISPLAY_REQUIRED used when appropriate; no generic parity claim. | trusted activation/runtime/display fixtures |
| CT-M5-08 | Handle .NET capability without assuming the standard editor can build. DEC-002, DEC-020 | CT-M2-01, CT-M5-06 | phases/dotnet_phase.py | No configured proven Mono -> MISSING_DOTNET_ENGINE; exact Mono path/hash retained before --build-solutions. | unit capability matrix; optional trusted Mono integration |
| CT-M5-09 | Generate success/failure/timeout/malformed-event fixtures and freeze hashes. DEC-016 | CT-M5-02 through CT-M5-08 | tests/fixtures/editor_activation_fail/, runtime_fail/, timeout_plugin/, malformed_events/ | Each fixture has one purpose and documented expected phase result; no external dependency. | fixture manifest validation |
| CT-M5-10 | Run G-04 and close the harness gate. DEC-016, DEC-017 | CT-M5-09 | G-04 oracles/captures | All scenarios pass twice; affected resources validate; bounded runs have no crash/timeout/unexplained warning except fixtures designed for them. | G-04 command and critics |

### MS-007 — classifier and reports

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M6-01 | Normalize structured/unstructured logs into versioned Findings. DEC-017 | MS-006 | logs/parser.py, logs/patterns.py | Required error/warning/native/API patterns map to stable categories; raw excerpts are bounded. | uv run pytest -q tests/unit/test_log_parser.py |
| CT-M6-02 | Implement reviewed warning allowlists with expiry. DEC-016 | CT-M6-01 | logs/allowlist.py, allowlist schema | Rule includes regex, plugin/engine selector, phase, justification, review/expiry; unmatched warning is retained. | uv run pytest -q tests/unit/test_warning_allowlist.py |
| CT-M6-03 | Implement ordered decisive classification and precedence collisions. DEC-003, DEC-017 | CT-M6-01, CT-M0-03 | classify/rules.py | Every status and collision has one deterministic first decisive rule; secondary findings remain. | uv run pytest -q tests/unit/test_classification.py |
| CT-M6-04 | Calculate confidence and port-candidate scope. DEC-003, DEC-020 | CT-M6-03 | classify/confidence.py | High Redot-specific confidence requires matching control or direct proof; missing control/platform lowers scope. | uv run pytest -q tests/unit/test_confidence.py |
| CT-M6-05 | Map stable next-action codes to evidence-aware guidance. DEC-009, DEC-017 | CT-M6-03 | classify/recommendations.py | Native rebuild/source/Rust/editor/runtime/upstream actions cite first failing evidence and do not promise unproven paths. | uv run pytest -q tests/unit/test_recommendations.py |
| CT-M6-06 | Generate authoritative JSON and derived Markdown/Codex brief. DEC-017 | CT-M6-03 through CT-M6-05 | reports/json_report.py, markdown_report.py, codex_brief.py | Conclusions/confidence/evidence/limits/reproduction agree; schema validates; brief includes all required port-start facts. | golden report tests |
| CT-M6-07 | Generate hash-checking PowerShell/Bash reproduction scripts. DEC-005, DEC-017 | CT-M6-06 | reports/reproduce.py | Scripts use local artifact paths, verify hashes, redact secrets, and reproduce at least the decisive phase with safe quoting. | tests/unit/test_reproduce.py plus shell syntax checks |
| CT-M6-08 | Expose stable exit codes and report command. DEC-003, DEC-017 | CT-M6-06 | cli.py, docs/classifications.md | Exit 0/10/20/30/40/50 meanings stable; full status remains in JSON. | parametrized CLI tests |
| CT-M6-09 | Freeze golden results for every synthetic fixture/status. DEC-017 | CT-M6-01 through CT-M6-08 | tests/golden/results/, tests/golden/reports/ | Every taxonomy status and precedence collision is represented or explicitly impossible with rationale. | uv run pytest -q tests/golden |

### MS-008 — exact Godot control differential

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M7-01 | Select the lowest exact registered control satisfying effective target or an exact manifest version. DEC-020 | MS-003, MS-007 | engines/control_selection.py | Selection deterministic and recorded; no bundled 4.5.0 reference substitution. | uv run pytest -q tests/unit/test_control_selection.py |
| CT-M7-02 | Mirror normalized source, install layout, manifest, and phase settings. DEC-017, DEC-020 | CT-M7-01, CT-M3-02 | workspace/mirror.py | Source/install/config hashes equal across roles; only engine-owned paths differ. | uv run pytest -q tests/unit/test_mirrored_fixture.py |
| CT-M7-03 | Run matched control phases and retain paired evidence. DEC-020 | CT-M7-02, CT-M5-07 | phases/control.py | Same platform/renderer/frame/timeouts; absence/mismatch is explicit; one role cannot overwrite another's artifacts. | trusted paired integration fixture |
| CT-M7-04 | Correlate missing symbols with Redot/control API indexes. DEC-011, DEC-020 | CT-M2-06, CT-M6-01 | logs/api_correlation.py | present_in_control_only/signature_changed/absent_in_both/unable_to_correlate are deterministic and evidence-linked. | uv run pytest -q tests/unit/test_api_correlation.py |
| CT-M7-05 | Apply the complete differential matrix. DEC-003, DEC-020 | CT-M7-03, CT-M7-04 | classify/differential.py | All G-05 rows and timeout/crash precedence match frozen expectations; missing control never fabricates specificity. | uv run pytest -q tests/unit/test_differential.py |
| CT-M7-06 | Generate a real post-baseline API-gap fixture from the configured API diff. DEC-011, DEC-020 | CT-M2-06, CT-M7-04 | tests/fixtures/post_baseline_api_gap/, fixture manifest/hash | Symbol is present in selected control and absent/changed in Redot; fixture source and expected failure are frozen. | fixture generator check plus paired bounded run |
| CT-M7-07 | Run G-05 and close the differential gate. DEC-020 | CT-M7-05, CT-M7-06 | G-05 oracles/captures | Every paired scenario passes twice with identical normalized evidence. | G-05 command and critics |

### MS-009 — batch and provider completion

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M8-01 | Define batch TOML/schema and bounded concurrency. DEC-017 | MS-002, MS-007 | models/batch.py, schemas/batch.schema.json, examples/plugins.toml | Defaults/overrides deterministic; concurrency/resource ceiling enforced; one item cannot mutate another. | uv run pytest -q tests/unit/test_batch_model.py |
| CT-M8-02 | Implement content-addressed downloads/snapshots and safe cache reuse. DEC-005 | CT-M1-01, CT-M2-04 | cache/store.py, cache/prune.py | Cache key is content identity; partial/failed entries never valid; prune cannot delete active run data. | uv run pytest -q tests/unit/test_cache.py |
| CT-M8-03 | Resume interrupted batches from authoritative item results. DEC-017 | CT-M8-01, CT-M8-02 | batch runner/state | Completed valid items reused; corrupt/incomplete items rerun; cancellation leaves readable state. | interruption/resume integration test |
| CT-M8-04 | Add legacy Asset Library metadata as corroborating evidence. DEC-012 | CT-M1-08 | sources/godot_asset_library.py | Single godot_version and empty official hash handled correctly; download independently hashed; repository resolved when possible. | provider contract fixture tests |
| CT-M8-05 | Add beta Asset Store metadata-only behavior. DEC-012 | CT-M1-08 | sources/godot_asset_store.py | No brittle credential/browser automation; varied licenses retained; absent public source/archive produces actionable stop. | saved-page/metadata contract tests |
| CT-M8-06 | Reconcile aggregate summaries from individual result.json files. DEC-017 | CT-M8-03 | reports/batch_summary.py | Counts/status/confidence/platform totals equal source results; no summary-only classification. | uv run pytest -q tests/unit/test_batch_summary.py |
| CT-M8-07 | Bound provider retries/rate limits and freeze response/OpenAPI fixtures. DEC-005, DEC-012 | CT-M8-04, CT-M8-05 | tests/contract/providers/, provider policy | Retry budget finite; version/capability recorded; secrets redacted; fixture update is reviewed. | full provider contract suite |
| CT-M8-08 | Run a duplicate-source, partial-failure, resumed batch end to end. DEC-005, DEC-017 | CT-M8-02 through CT-M8-07 | .artifacts/batch integration output | Duplicate downloaded once; one failure does not corrupt peers; resume completes; aggregate reconciles. | bounded batch integration test |

### MS-010 — export, platform hardening, and version 1.0 release

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M9-01 | Add manifest-gated export smoke phase. DEC-016 | MS-006 | phases/export_phase.py, minimal reviewed presets/templates | Runs only with configured templates and requested manifest; expected libraries selected; exported app bounded and explicitly successful. | trusted export fixture integration test |
| CT-M9-02 | Add static native dependency inspection per platform without loading candidates. DEC-004, DEC-016 | MS-002 | inspect/native_pe.py, native_elf.py, native_macho.py or reviewed library | Entry/dependency/arch evidence retained; tools run in appropriate isolated profile; ldd never used on host candidate. | native fixture unit/integration tests |
| CT-M9-03 | Harden the Windows trusted worker path. DEC-007, DEC-016 | MS-004 | Windows integration workflow/config | Explicit consent, Job Object ownership, isolated state, trusted fixtures only, artifact hashes and warnings reviewed. | Windows trusted integration job |
| CT-M9-04 | Add optional .NET integration with an exact Redot 26.2 Mono binary. DEC-020 | CT-M5-08 | Mono engine record, dotnet fixture/workflow | Standard editor never substituted; build/run evidence scoped to exact binary/platform; absence stays missing-capability. | optional .NET job |
| CT-M9-05 | Aggregate platform-specific evidence without generalization. DEC-003, DEC-020 | CT-M9-02 through CT-M9-04 | models/report aggregation | Like-for-like evidence only; unsupported/unrun platforms explicit; no cross-platform compatible status from one worker. | platform matrix tests |
| CT-M9-06 | Package wheel, sdist, schemas, and digest-pinned Docker worker under one semantic version. DEC-018 | MS-009 | build/release config, CHANGELOG.md | Clean installation reports same version; artifact hashes recorded; no source-tree build residue beyond defined output. | release dry run and clean-install smoke test |
| CT-M9-07 | Generate SBOM/checksums and complete license/vulnerability review. DEC-010, DEC-018 | CT-M9-06 | SBOM, checksums, third-party notices | Exact lock/image contents covered; MPL obligations identified if godot-rust distributed/modified; no unaccepted critical issue. | documented scanners plus manual review record |
| CT-M9-08 | Finish operator, security, manifest, adapter, probe, and troubleshooting docs. DEC-018 | CT-M9-01 through CT-M9-07 | README.md, SECURITY.md, docs/*.md | Fresh operator can run inspect/test/reproduce; every status/probe/field/limit documented; examples verified. | docs tests and clean-machine walkthrough |
| CT-M9-09 | Restrict CI/release workflows to trusted fixtures and verified engine assets. DEC-016, DEC-018 | CT-M9-06 | quality, integration, release workflows | Public PR job never runs submitted plugins; engine/image digests verified; artifacts uploaded; signing conditional on configured identity. | workflow policy tests and release dry run |
| CT-M9-10 | Run G-06 and the full version 1.0 acceptance audit. DEC-018 | CT-M9-01 through CT-M9-09, all prior Gauntlets | G-06 captures, release checklist, release decision record | No failed/blocked mandatory item, warning, crash, timeout, formula/schema mismatch, or unsupported claim. | G-06 command, critics, clean release rehearsal |

### MS-011 — optional trusted build adapters

| Task ID | Outcome and decision trace | Dependencies | Expected files or systems | Acceptance checks | Verification |
|---|---|---|---|---|---|
| CT-M10-01 | Define explicit trust/approval/toolchain/network/output contract shared by build adapters. DEC-016, DEC-019 | Version 1.0 stable | build/base.py, build manifest schema, SECURITY.md | No build starts without manifest trust plus operator approval; exact commands/dependencies retained; isolation mandatory. | security unit/contract tests |
| CT-M10-02 | Build a redot-cpp/SCons adapter pinned to redot-26.2-stable. DEC-019 | CT-M10-01 | build/redot_cpp.py, trusted fixture | Exact tag/commit/API hash; no arbitrary flags; compiler output retained; isolated build/load passes. | trusted C++ fixture |
| CT-M10-03 | Add a narrowly scoped CMake recipe adapter. DEC-019 | CT-M10-01 | build/cmake.py, trusted fixture | Reviewed preset/toolchain only; no arbitrary script injection; network off by default. | trusted CMake fixture |
| CT-M10-04 | Trial godot-rust api-custom-json using the tagged Redot JSON. DEC-009, DEC-019 | CT-M10-01 | build/godot_rust.py, trusted Rust fixture | Exact crate/lock/API hashes; GDRUST_GODOT_API_JSON recorded; compile and Redot load both pass before recommendation is enabled. | trusted Rust compile/load integration |
| CT-M10-05 | Add an exact-SDK/exact-Mono .NET recipe if still needed. DEC-019, DEC-020 | CT-M10-01, CT-M9-04 | build/dotnet.py, trusted fixture | Exact Godot.NET.Sdk/lock/Mono identities; isolated restore policy; build/runtime evidence scoped. | trusted .NET integration |
| CT-M10-06 | Keep adapter findings experimental until separate release approval. DEC-019 | CT-M10-02 through CT-M10-05 | docs/release and classifications | Core tester works without adapters; unsupported adapters cannot change stable classification automatically. | feature-disabled regression suite |

## 11. QA strategy

### Test layers

| Layer | Purpose | Required evidence |
|---|---|---|
| Unit | Models, parsing, precedence, paths, command construction, redaction, classification | One behavior per test; deterministic, no network/engine |
| Generated security corpus | Hostile ZIP/TAR, paths, quotas, collision, partial failure | Programmatically generated fixtures; no real bomb committed |
| Provider contract | GitHub/Forgejo/Asset Library/Store protocol drift | Redacted recorded responses/OpenAPI; live smoke only in controlled scheduled job |
| Schema/golden | Stable public JSON, reports, CLI exits, reproduction | Versioned golden files; approved migration for deliberate change |
| Redot static validation | Typed GDScript and resources load in installed Redot | redot_code_intel validate when available, then installed build parse/resource checks |
| Bounded Redot integration | Import/editor/runtime/display/export behavior | --quit-after >=2 when applicable, external timeout, exact engine hash, logs/warnings reviewed |
| Containment | Process tree, cancellation, writes, network, quotas | G-03 captures on each enabled backend |
| Differential | Like-for-like Redot/control behavior | Equal configuration/source hashes and G-05 paired artifacts |
| Platform | Linux/Windows and optional .NET; macOS only when available | Platform-scoped results; missing platform explicit |
| Release | Clean install, SBOM, checksums, accessibility, performance, docs | G-06 and release dry run |

### Test discipline

- Use pytest as the authoritative orchestrator test framework. Do not add GUT/gdUnit4 merely to test the tiny harness; bounded engine fixtures exercise its public behavior with less dependency risk.
- Follow RED–GREEN–REFACTOR for every rule, parser, classifier branch, and security invariant.
- Do not test Redot internals. Test the tester’s observed event/result contract.
- Async tests use explicit engine/runner timeouts, never arbitrary sleeps.
- Resolve failures in this order: parse errors, resource/load errors, runtime errors, warnings.
- Review the diff plus retained logs/artifacts after functional changes.
- Any timeout, crash, resource load failure, runtime error, or unexplained warning leaves the task unfinished unless it is the fixture’s exact expected result and the tester classifies it correctly.
- Ordinary pull-request CI uses repository-owned trusted fixtures only. Live provider and engine jobs are scheduled/manual and pinned.

### Standard verification commands

    uv sync --frozen
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy src
    uv run pytest -q

Engine commands are generated as argument arrays. Never run Redot with -d in unattended automation. Every Redot run records the resolved binary identity first and has a wall-clock timeout.

## 12. Risks and open questions

| ID | State | Impact and question | Mitigation / proof required | Owner | Deadline |
|---|---|---|---|---|---|
| RSK-001 | Resolved | Critical: why does Redot 26.2 crash during API dump? | The failure did not reproduce from the verified clean archive; two isolated dumps matched. The old installation is not accepted as gate evidence. | Project | Closed by G-02 |
| RSK-002 | Controlled, residual | Critical: can plugin/native code escape the selected worker? | G-03 proves the documented Docker controls, not universal escape resistance. Keep static-first policy and require disposable-machine isolation for hostile native submissions. | Project | Local profile closed; residual risk retained |
| RSK-003 | Open | High: will users mistake policy skip for tested compatibility? | Separate schema/status/report terms and preserve force-test path. | Project | Before MS-001 schema freeze |
| RSK-004 | Open | High: can weak marketplace data override direct evidence? | Package-specific precedence, conflict retention, tests. | Project | Before MS-002 |
| RSK-005 | Resolved for enabled profiles | High: can descendants survive timeout/controller failure? | Kill-on-close Job Object and Docker heartbeat/ownership fixtures passed twice, including abrupt controller death. | Project | Closed by G-03 |
| RSK-006 | Open | High: can provider drift break immutability/acquisition? | Full commits/hashes, capability probing, fixtures, bounded fallback. | Project | Before MS-002 |
| RSK-007 | Open | High: can an archive escape or exhaust the worker? | Explicit TAR/ZIP invariants, quotas, cleanup, G-01. | Project | Before MS-002 |
| RSK-008 | Open | Medium: will godot-rust custom JSON compile/load against Redot 26.2? | Trusted exact-lock/api-custom-json experiment; no promise before pass. | Project | Before MS-011 Rust adapter |
| RSK-009 | Resolved | Medium: can current executables be bound to the official archive? | The official ZIP was retained, matched the published digest, and yielded the recorded executable hash. | Project | Closed by G-02 |
| RSK-010 | Open | Medium: could Linux results be generalized to Windows/macOS? | Platform-scoped aggregation and explicit missing states. | Project | Before MS-010 |
| RSK-011 | Open | Medium: team capacity, budget, and calendar are unspecified. | Use dependency gates; owner supplies schedule only after MS-002 sizing evidence. | Project | Before any date commitment |
| RSK-012 | Resolved | High: no exact Godot 4.5.2 control is currently retained. | Exact 4.5.2 archive, executable, and fresh snapshot are hashed; G-05 passed twice without substituting the 4.5.0 reference. | Project | Closed by G-05 |
| RSK-013 | Resolved locally | Medium: no proven Redot 26.2 Mono executable is configured. | Exact Mono archive/binary and portable .NET 8 SDK are hashed; the minimal trusted C# fixture passed twice. | Project | Optional capability proven |
| RSK-014 | Controlled | High: exact dependency transitives/licenses/vulnerabilities can drift after the current audit. | The 62-package lock, SPDX SBOM, license review, fresh vulnerability report, and artifact checksums are clean for this alpha; regenerate for G-06 and each release image. | Project | Current alpha closed; final before release |
| RSK-015 | Open | Medium: publication host and signing identity are unspecified. | Produce local release dry run only; obtain explicit destination/signing decision before publish. | Project | Before external release |

### Not yet specified

- Calendar milestones and staffing.
- External publication destination and release signing.
- Availability of macOS or disposable Windows VM workers.
- Whether Asset Store will expose a stable public API suitable for more than metadata.
- Whether HTML or standalone executable packaging is worth a later release.

These do not block MS-001 or MS-002. The active technical frontier is RSK-001.

## 13. Release plan

### Versioning and artifacts

- Use semantic versioning for the Python package/CLI and Docker worker; they report the same version.
- Version result/manifest/batch schemas explicitly. A schema-breaking change requires a documented migration and major schema version.
- Version 1.0 release candidates contain: wheel, source distribution, digest-pinned worker image, JSON Schemas, README/security/docs, changelog, SBOM, checksums, and source commit.
- report.html and standalone executables are optional later deliverables, not 1.0 gates.

### Distribution gates

1. MS-001 through MS-010 complete; MS-011 is irrelevant to 1.0.
2. G-01 through G-06 PASS; no mandatory BLOCKED/WAIVED item.
3. Full quality, golden, integration, trusted platform, accessibility, and performance checks pass.
4. Redot and Godot artifacts are digest-verified and recorded.
5. No unaccepted critical vulnerability/license issue; third-party notices are present.
6. No untrusted plugin executes in public PR CI.
7. Clean environment installs and reproduces version/schema/sample inspect.
8. Release notes state exact platform/control scope and known limitations.
9. Publication destination and signing decision are explicitly approved. Without them, stop after the local dry-run artifacts.

### Licensing

- Project license is MIT as requested by the repository owner; retain `LICENSE` and package metadata together.
- Retain upstream attribution for bundled Redot/Godot API snapshots.
- Direct dependencies are permissive at preflight, but exact lock contents control release clearance.
- If godot-rust is modified or redistributed, satisfy MPL-2.0 file-level obligations.
- Do not redistribute third-party plugins/marketplace assets without explicit compatible rights.

### Rollback and support

- Releases are immutable. Fixes publish a new version; never replace artifacts under an existing version.
- Retain checksums, SBOM, schemas, release notes, and known-blocker records.
- A critical sandbox/provenance/classification defect suspends dynamic recommendations until a corrected release passes the affected Gauntlet.

## 14. Out of scope

- Automatic source modification, port generation, fork creation, pull request, or publication.
- Automatic compilation of arbitrary untrusted SCons, CMake, Cargo, PowerShell, shell, or other build scripts.
- Hosted public execution of user submissions.
- Generic visual correctness, UI automation, pixel comparison, multiplayer, online service, Steam, hardware, or credential testing without an explicit trusted manifest and future plan.
- Claiming that baseline policy, load success, process exit, one probe, or one platform proves complete compatibility.
- Silent engine download or execution.
- Dynamic testing of arbitrary third-party plugins on the host.
- macOS compatibility claims without a macOS worker.
- Popularity/adoption scoring.
- A broad game-project scaffold, autoload layer, input map, visual/audio asset pipeline, or general-purpose Godot test framework inside the harness.
- Version 1.0 HTML reports, standalone executables, and trusted build adapters.

Planning is complete when this file and source-of-truth.xlsx agree. Implementation must begin at CT-M0-01 and may not skip a failed or blocked dependency gate.
