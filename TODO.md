# TODO

The detailed task graph is [docs/gamedev/implementation-plan.md](docs/gamedev/implementation-plan.md). This alpha records partial milestone slices honestly; a locally implemented feature is not a green version 1.0 release gate.

## Completed local slices

- [x] MS-001 — installable locked Python project, CLI, strict contracts/schemas, docs, pinned quality CI, supply-chain evidence, wheel/sdist, and clean-install smoke.
- [x] MS-002 local implementation — safe local/HTTPS/GitHub/Codeberg acquisition, hostile archive rejection, static inventory/baseline policy, reports, and deterministic G-01 fixture/oracle tests.
- [x] Trusted synthetic Windows smoke — doctor-verified Redot 26.2 import, editor activation, and declarative runtime probes with bounded logs/time and ordered terminal events.
- [x] Static batch slice — bounded concurrency, isolated items, schema-valid resume, failure isolation, and authoritative aggregate summaries.
- [x] MS-003 local gate — official Redot 26.2 archive provenance, clean deterministic API snapshots, exact Godot 4.5.2 control snapshots, and G-02.
- [x] MS-004 containment gate — pre-execution Windows Job Object ownership, timeout/controller-death descendant teardown, and isolated user state.
- [x] MS-005 local gate — digest-pinned Linux worker, fixed resource/security profile, controller watchdog, public CLI execution, and G-03 twice.
- [x] MS-008 differential slice — matched exact-engine phases, real PASS/PASS and Redot-only API-gap fixtures, complete outcome matrix, and G-05 twice.
- [x] Optional Mono capability — exact Redot 26.2 Mono plus offline .NET 8.0.423 fixture build/run twice.

## Required before broader claims

- [ ] Run G-01 twice on the canonical Linux CI profile and retain captures.
- [ ] Complete parse, GUI/display, export, native dependency, and platform aggregation phases.
- [ ] Complete golden report coverage for every classification and precedence collision.
- [ ] Add Asset Library corroboration and Asset Store metadata-only adapters.
- [ ] Run G-04, G-06, every mandatory platform job, and the version 1.0 release audit before changing the alpha status.

## Post-core, separate approval

- [ ] MS-011 — optional trusted redot-cpp, CMake, and godot-rust build adapters.
