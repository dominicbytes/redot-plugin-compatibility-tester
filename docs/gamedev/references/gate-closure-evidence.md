# Local gate closure evidence

Captured: 2026-08-10 on Windows x86-64 with Docker Desktop's Linux/WSL2 worker. Generated `.artifacts/` and `.tools/` paths are intentionally ignored by Git; this record preserves the identities and commands needed to reproduce them. No engine archive or executable is distributed by this repository.

## G-02 — exact engines and deterministic API snapshots

### Redot 26.2 standard

```text
Official archive: Redot_v26.2-stable_windows_win64.zip
Archive SHA-256: 4644C7591BBE8019B861DEB0CCDB64FD4F59A88514ABF7C788CF176C259855AF
Console executable SHA-256: 5633D02A28A73514084DF6A60FFE01FABDBBB9AC5E28FDFD590ED47277F51989
Version: 26.2.stable.official.4f5b14aba
Compatibility lineage: 4.5.2
Fresh snapshot SHA-256: 177E7796166929B2193C9CCE2FD32F59601A0147D0D1E7FE904B94E8F69F6577
```

The clean official extraction succeeded twice from separate empty engine-state/work directories. Both semantic bodies and byte hashes agreed. This resolves the earlier crash from the pre-existing local installation rather than suppressing it.

### Exact Godot control

```text
Official archive: Godot_v4.5.2-stable_win64.exe.zip
Archive SHA-256: 3766090865330AB2A0ED33594520394B711C620B1378F9223904FAEEF60F2F14
Console executable SHA-256: 446E08F71624052572F96DE9031850BA96382CE6752ADDE38BB955B0A49BED01
Version: 4.5.2.stable.official.6ce3de25a
Fresh snapshot SHA-256: 481ED7DC8EFC79E951081187CD5D651D6B34E2365A463F4F12ADEAB2F63475C8
```

The control also produced two identical isolated snapshots. The exact diff reported 304 Redot additions, 14 control-only symbols, and 18 changed signatures. The 14 control-only symbols are the `SpringBoneSimulator3D.BoneDirection` and `RotationAxis` enum namespaces/values; Redot moves equivalent enums to `SkeletonModifier3D`.

G-02 capture roots: `.artifacts/gauntlet/G-02/run-1` and `run-2` (two tests passed in each clean run).

## G-03 — process and worker containment

### Windows trusted host

The runner starts a package-owned waiting launcher, assigns it to a kill-on-close Windows Job Object, and only then releases the target argument array. Timeout and abrupt-controller fixtures each spawned a child and grandchild. All owned PIDs disappeared within five seconds and two later probes found no survivor. HOME, profile, config, cache, and temporary writes stayed in the owned state tree.

Host mode is still trusted-only: Job Objects own processes but do not restrict filesystem or network access.

### Linux Docker worker

```text
Docker server: 29.2.1
Final local image: redot-compat-worker@sha256:3e7f1dcfa10a2fdafe5ffc44bd78ba623899b9add88fd0f7dc079dd83108c9d2
Image size: 212,292,093 bytes
Redot Linux archive SHA-256: F474D890806C41AF15513CF5A8600243E241882E11B68DBB95660E3465B5B1E4
In-image Redot SHA-256: 11D299E0F01A63574E612C64718CA3037A65540139DEC7B93A87650EE9AAB2F3
Runtime user: 10001:10001
```

The probe observed `CapEff=0000000000000000`, `NoNewPrivs=1`, seccomp mode 2, `pids.max=256`, `memory.max=4294967296`, and `cpu.max="200000 100000"`. Root/input writes and a direct network connection failed; output/HOME writes succeeded; the Docker socket was absent. A parent/child/grandchild container was removed after explicit teardown. A second fixture killed the host controller; the read-only heartbeat stopped, the trusted worker exited, and `--rm` removed the container within ten seconds.

Final-image capture roots: `.artifacts/gauntlet/G-03/run-8` and `run-9` (Windows and Docker tests both passed in each clean run). The public CLI then returned `COMPATIBLE_UNCHANGED` twice through the same image at `.artifacts/gates/docker-worker-final-1` and `docker-worker-final-2`.

Redot's deterministic `WARNING: Scan thread aborted...` on bounded Linux editor shutdown is retained as informational finding `REVIEWED_EDITOR_SCAN_SHUTDOWN` only for Redot import/editor phases. The same text under another engine role or phase remains unreviewed and blocking.

## G-05 — exact-control differential

The real API-gap fixture has source SHA-256 `B13679DA450750B6125D678BB00F94F1AD0CE72AE38C7F5DCB3EB8FDF75D760C` and phase-configuration SHA-256 `3AB017FE87977A4BFD66F5F1D2D151AAD10E2326EB5D70EA43D2D8BA559981C5`. It queries class-owned enum metadata with inheritance disabled. Godot 4.5.2 passes; Redot 26.2 reports the absent `SpringBoneSimulator3D.BoneDirection` namespace and fails.

The public service also ran one normalized plugin fixture through both engines, recorded both identities/roles, and produced the expected high-confidence scoped port classification. A separate baseline fixture passed import, editor activation, and runtime probes under both exact engines and produced high-confidence `COMPATIBLE_UNCHANGED`.

The gate additionally froze all six required matrix rows: PASS/PASS, Redot FAIL/control PASS, FAIL/FAIL, Redot PASS/control FAIL, Redot TIMEOUT/control PASS, and Redot CRASH/control PASS. Capture roots `.artifacts/gauntlet/G-05/run-6` and `run-7` each passed four tests.

## Optional Redot Mono capability

```text
Official archive: Redot_v26.2-stable_windows_mono_win64.zip
Archive SHA-256: 5DA9E073B10DB3022D4FEF069405FE975DD0514878BB2FB67CDBCC6CE61247A4
Mono console SHA-256: 792F653F2BADF24F8D90EC837E977554274E4ABCD978ABFCC0B76E89D70C4B7A
Version: 26.2.stable.mono.official.4f5b14aba
.NET SDK: 8.0.423 (runtime 8.0.29)
SDK archive SHA-512: 063FCC35C136277E6FD767C66579F3B92DB22A078A7F0C7177B6AF1EDB2C9AFAE1613F6CFDC01ACF7421773D9AC77F0EF73A7FD8B37F469E7E3505E5C1361BA0
```

The trusted fixture restored `Redot.NET.Sdk/26.2.0` from the Mono archive's local NuGet feed, built for `net8.0`, and ran with the exact Mono editor. `.artifacts/gates/mono-final/run-1` and `run-2` each passed without engine errors or warnings.

## Scope of closure

These results close the five preflight blockers and enable the implemented alpha paths. They do not close G-01's canonical Linux CI capture, the full G-04 phase/platform matrix, G-06, macOS, publication, or version 1.0.

## Current alpha release fence

The frozen environment passed the complete normal quality sequence twice: 150 files formatted, Ruff lint clean, strict mypy clean across 74 source files, 121 tests passed with 9 intentional capability/platform skips, and exported schemas unchanged. An isolated PEP 517 build produced:

```text
Wheel: redot_plugin_compatibility_tester-0.1.0-py3-none-any.whl
Source distribution: redot_plugin_compatibility_tester-0.1.0.tar.gz
```

The final artifact digests are written to the generated `release/SHA256SUMS` after documentation freeze. They are deliberately not embedded in this source-distribution member, which would make the source archive checksum self-referential.

Separate new Python 3.14 virtual environments installed the wheel and source distribution with dependencies, reported `redot-compat 0.1.0`, passed the installed schema check, and contained all four packaged harness resources. The 62-package lock produced an SPDX 2.3 SBOM and license inventory with zero unresolved declarations. A fresh PyPI advisory query reported zero known vulnerabilities; the unpublished project itself was the single expected unaudited/self-package entry.

These are alpha dry-run results, not G-06 or publication approval. The generated `dist/`, `release/`, and clean-install environments are local ignored evidence and must be regenerated from a committed source identity before an external release.
