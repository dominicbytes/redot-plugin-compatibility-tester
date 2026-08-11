# Compatester adversarial evidence audit

Prepared: 2026-08-10

## Post-implementation disposition — 2026-08-10

The audit rows below remain the original falsification record; a later implementation cannot retroactively turn a false preflight claim into a preflight pass. Subsequent evidence changed the operational disposition of these prerequisites:

| Finding | Follow-up evidence | Current disposition |
|---|---|---|
| AUD-002 | A digest-verified clean Redot 26.2 archive produced the same fresh API snapshot in two isolated runs. | G-02 prerequisite closed; the old installation's crash is retained as historical evidence. |
| AUD-009 | The official archive is retained with its published digest and the extracted console executable hash is recorded. | Provenance prerequisite closed. |
| AUD-016 | An exact Godot 4.5.2 binary produced two identical fresh snapshots and passed the G-05 control matrix. | Exact-control prerequisite closed; the bundled 4.5.0 file remains reference-only. |
| AUD-006/AUD-007 | Kill-on-close Windows Job Object and hardened Docker fixtures passed twice, including controller death, network/write denial, quotas, and teardown. | Enabled-profile containment gate closed with the documented Docker residual risk. |
| AUD-010 | The frozen 62-package environment produced an SPDX 2.3 SBOM, dependency/license inventory with zero `NOASSERTION` declarations, and a fresh `pip-audit` report with zero known vulnerabilities; wheel and sdist both clean-installed as version 0.1.0. | Current alpha supply-chain prerequisite closed; regenerate for every release candidate and Docker image. |

See [`gate-closure-evidence.md`](gate-closure-evidence.md) for immutable identities, capture roots, and the current alpha release-fence evidence.

The preflight skill requires an adversarial audit before consequential recommendations. Delegation was not authorized for this task, so these are two separate, labeled `SELF_REVIEW` passes by the same reviewer. They are not independent review.

Status meanings:

- `PASS` — the challenged claim survived within its stated scope.
- `FAIL` — evidence contradicted or materially narrowed the claim.
- `BLOCKED` — decisive proof was unavailable; the implementation must preserve the uncertainty.

## SELF_REVIEW pass 1 — technical falsification

| ID | Lens | Challenged claim | Evidence URL or path | Missing proof | Impact | Status |
|---|---|---|---|---|---|---|
| AUD-001 | Engine identity | “Redot 26.2 has Godot 4.5.2 compatibility lineage.” | [`version.py`](https://raw.githubusercontent.com/Redot-Engine/redot-engine/redot-26.2-stable/version.py); local `--version`; `redot-26.2-engine-evidence.md` | Identity does not prove all 4.5.2 plugins work. | Preserve dual identity; call the skip result a policy classification, not a runtime compatibility proof. | PASS |
| AUD-002 | Reproducibility | “The configured editor can generate the required API snapshot.” | `redot-26.2-engine-evidence.md` | Root cause and clean-archive reproduction. | Block the Milestone 2 doctor gate; use tagged JSON only for early schema/index work. | FAIL |
| AUD-003 | Harness API | “The proposed plugin activation methods exist in the target API.” | `redot-26.2-extension-api.json`; [EditorInterface 4.5](https://docs.godotengine.org/en/4.5/classes/class_editorinterface.html) | Runtime activation behavior in Redot 26.2. | Keep the design, but require a trusted activation fixture before relying on it. | PASS |
| AUD-004 | Version evidence | “Asset Library/Store minimum and maximum versions are the strongest evidence.” | [Asset Library API](https://github.com/godotengine/godot-asset-library/blob/master/API.md); [Asset Store status](https://docs.godotengine.org/en/stable/community/asset_store/what_is_asset_store.html) | None needed to reject the universal ranking. | Replace the single ranking with package-type-specific precedence; marketplace metadata becomes corroborating evidence. | FAIL |
| AUD-005 | Rust ecosystem | “Ports can be routed through an existing shared Redot–Rust compatibility layer.” | `research-query-log.md`; [godot-rust custom API support](https://godot-rust.github.io/book/toolchain/godot-version.html) | A maintained Redot-specific layer or owner. | Remove the assumed dependency. Trial `api-custom-json` against the tagged Redot API in trusted Milestone 10 work. | FAIL |
| AUD-006 | Process control | “psutil or Job Objects are interchangeable ways to guarantee full Windows tree termination.” | [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects); [Python subprocess](https://docs.python.org/3.12/library/subprocess.html); [psutil](https://github.com/giampaolo/psutil) | A race-free psutil-only proof. | Make a kill-on-close Job Object the Windows guarantee; retain psutil for inspection and fallback cleanup. | FAIL |
| AUD-007 | Sandbox | “The listed Docker flags form a sufficient security boundary for arbitrary native plugins.” | [Docker security](https://docs.docker.com/engine/security/); [Docker run](https://docs.docker.com/engine/containers/run/) | A threat model and escape-resistance validation for the chosen host. | Keep Docker as the default Linux containment layer, but document residual risk and require stronger disposable VM isolation for hostile native submissions. | FAIL |
| AUD-008 | Market scan | “No comparable end-to-end tool exists.” | `research-query-log.md`; [godot-ci](https://github.com/abarichello/godot-ci); [GDScript Toolkit](https://github.com/Scony/godot-gdscript-toolkit); [GUT](https://github.com/bitwes/Gut) | Exhaustive registry and private-project coverage. | Phrase the result as a bounded search finding, not a universal absence claim. | BLOCKED |

## SELF_REVIEW pass 2 — operational, licensing, and delivery challenge

| ID | Lens | Challenged claim | Evidence URL or path | Missing proof | Impact | Status |
|---|---|---|---|---|---|---|
| AUD-009 | Supply chain | “The local editor installation is fully bound to an official release asset.” | [Redot 26.2 release](https://github.com/Redot-Engine/redot-engine/releases/tag/redot-26.2-stable); `redot-26.2-engine-evidence.md` | The original Windows ZIP or an extraction manifest binding its digest to the current files. | Record local executable hashes as local provenance only; rehydrate from a verified archive before closing doctor provenance. | BLOCKED |
| AUD-010 | Licensing | “The proposed dependency stack is safe to adopt under an MIT project.” | Official repositories recorded in `source-of-truth.xlsx`; godot-rust is MPL-2.0. | Locked direct/transitive versions, generated SBOM, and distribution review. | Conditionally adopt permissive Python tooling; document MPL obligations if godot-rust itself is modified; scan the lock before release. | BLOCKED |
| AUD-011 | Immutability | “A release tag is itself an immutable source identity.” | [GitHub repository archive API](https://docs.github.com/en/rest/repos/contents); [Git refs](https://docs.github.com/en/rest/git/refs) | Provider enforcement against tag movement. | Resolve every tag to a full commit, request archives by commit, record redirects and content hashes. | FAIL |
| AUD-012 | Archive safety | “Rejecting traversal, links, and bombs in the plan is enough to make Python extraction safe.” | [tarfile extraction filters](https://docs.python.org/3.12/library/tarfile.html#extraction-filters); [zipfile](https://docs.python.org/3.12/library/zipfile.html) | Implementation and malicious-fixture results. | Mandate explicit TAR `filter="data"`, ZIP member preflight, quotas, unique empty targets, cleanup after partial failure, and no `zipfile.Path` extraction. | FAIL |
| AUD-013 | Baseline policy | “Skipping <=4.5.2 plugins establishes compatibility.” | Plan sections 2 and 6; `AUD-001` | Per-plugin dynamic evidence. | Keep the resource-saving policy, but never merge it with `COMPATIBLE_TESTED`; offer `--force-test-baseline`. | FAIL |
| AUD-014 | Codeberg contract | “A fixed Gitea 1.25 contract is an adequate Codeberg API specification.” | [Forgejo API usage](https://forgejo.org/docs/latest/user/api-usage/); [Codeberg tags/releases](https://docs.codeberg.org/git/using-tags/) | Current production instance OpenAPI retained as a fixture. | Probe version/capabilities, capture instance OpenAPI in contract tests, and keep a fixed-commit Git fallback. | FAIL |
| AUD-015 | Simplicity | “The external orchestrator plus small engine harnesses are unnecessary complexity.” | Plan non-goals, arbitrary-code threat model, API/source-adapter requirements, and alternatives scan | A smaller existing end-to-end tool. | Architecture survives: static inspection first, minimal harnesses for engine-owned checks, no in-editor product shell. | PASS |
| AUD-016 | Reference bundle | “The Godot API JSON in this bundle is an exact 4.5.2 control.” | `godot-4.5-extension-api.json`; `research-query-log.md` | An exact Godot 4.5.2 generated dump. | Label it 4.5.0 reference-only everywhere; the tester must generate a 4.5.2 control from an explicitly configured binary. | FAIL |

## Audit outcome

No finding requires abandoning the proposed product. The audit changes the gate from an unconditional start to a conditional start:

- proceed with Milestones 0 and 1 after applying the evidence, archive, and provider-contract corrections;
- use the tagged Redot snapshot for early API schema/index fixtures;
- do not claim the Milestone 2 doctor gate passes until a clean configured editor generates a fresh snapshot;
- do not execute arbitrary third-party plugins on the host;
- do not treat marketplace metadata, a baseline-policy skip, or a process exit as compatibility proof.
