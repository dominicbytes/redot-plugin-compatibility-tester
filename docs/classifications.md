# Compatibility classifications

The public enum is defined in `redot_compat.models.CompatibilityStatus`. The first matching decisive rule wins; secondary findings remain in `result.json`.

## No-port results

- `NO_PORT_NEEDED_BASELINE_POLICY`: decisive target evidence is Godot 4.5.2 or earlier and execution was skipped by policy. This is not a runtime test.
- `COMPATIBLE_UNCHANGED`: all required dynamic phases produced explicit success evidence under Redot.
- `COMPATIBLE_REPACKAGE_ONLY`: code works but archive or manifest normalization is required.

## Port-required results

- `PORT_REQUIRED_MAJOR_UPGRADE`: credible Godot 3.x target evidence requires a major-version port to the Godot 4.5.2 lineage used by Redot 26.2 and 26.3. Static inspection returns this before dynamic phases; exit 20 and `port_candidate=true`.
- `PORT_REQUIRED_GDSCRIPT_API`
- `PORT_REQUIRED_EDITOR_API`
- `PORT_REQUIRED_RUNTIME_API`
- `PORT_REQUIRED_NATIVE_REBUILD`
- `PORT_REQUIRED_NATIVE_SOURCE`
- `PORT_REQUIRED_RUST_BINDINGS`
- `PORT_REQUIRED_ENGINE_MODULE`
- `PORT_REQUIRED_EXPORT_PACKAGING`
- `ENGINE_API_GAP`

## Invalid, missing, and inconclusive results

- `INVALID_PACKAGE`
- `UPSTREAM_PACKAGE_FAILURE`
- `MISSING_PLATFORM_BINARY`
- `MISSING_BUILD_ARTIFACT`
- `MISSING_DOTNET_ENGINE`
- `MISSING_EXTERNAL_SERVICE`
- `DISPLAY_REQUIRED`
- `TIMEOUT`
- `CRASHED`
- `INCONCLUSIVE`
- `INTERNAL_TESTER_ERROR`

## Confidence

`high`, `medium`, and `low` are independent of classification. High-confidence Redot-specific blame requires a matching Godot control pass or direct native/API proof. Missing controls, platforms, or capabilities reduce scope and confidence.

For an exact paired run, `TIMEOUT` and `CRASHED` remain the primary status. A passing Godot control can raise confidence and set `port_candidate=true`, but it does not invent a more specific API/native cause without supporting evidence. A non-comparable control yields `INCONCLUSIVE` rather than Redot-specific blame. A compatibility-lineage mismatch is rejected before plugin phases run. A scoped Redot failure without an exact passing control has `port_candidate=false`; static engine-module and major-upgrade evidence can independently establish a port candidate.

## Differential outcomes

- `BOTH_PASSED` (`both_passed`): both matched phases passed.
- `REDOT_ONLY_FAILURE` (`redot_only_failure`): Redot failed, crashed, or timed out while the exact matched control passed. Only this dynamic evidence can establish a port candidate.
- `BOTH_FAILED` (`both_failed`): both statuses are exactly `FAIL`; classify as `UPSTREAM_PACKAGE_FAILURE`.
- `CONTROL_MISMATCH` (`control_mismatch`): Redot passed while the matched control failed; classify as `INCONCLUSIVE` with `FIX_CONTROL_FIXTURE`.
- `NOT_COMPARABLE` (`not_comparable`): the control has `MISSING_CAPABILITY`, `TIMEOUT`, `CRASH`, or `TESTER_ERROR`, or two non-pass statuses are not two actual failures. Classify as `INCONCLUSIVE` with `FIX_CONTROL_FIXTURE`; do not infer an upstream package failure or port candidate.
- `MISSING_CONTROL` (`missing_control`): no matched control ran.
- `INCONCLUSIVE` (`inconclusive`): Redot did not run.

## Harness and engine findings

Protocol v2 authenticates each event with HMAC-SHA256 over the exact UTF-8 JSON body and checks the owned run ID, schema, and event sequence. Import also requires authenticated scan-completion evidence.

- `HARNESS_EVENT_UNAUTHENTICATED`: missing/invalid MAC or a mismatched run ID/schema. Security category, critical severity, phase `FAIL`. The overall result is `INCONCLUSIVE`, high confidence, action `REVIEW_PACKAGE_TAMPERING`, and `port_candidate=false`.
- `HARNESS_CONFIGURATION_ERROR`: missing/bad tester configuration or authenticated terminal `error`; phase `TESTER_ERROR`.
- `HARNESS_PROTOCOL_ERROR`: authenticated output has malformed JSON, invalid sequence, or contradictory terminal events; phase `TESTER_ERROR`. Redot tester failures classify as `INTERNAL_TESTER_ERROR`; an unusable control is `NOT_COMPARABLE`.
- `HARNESS_INCOMPLETE`: a normal exit has no authenticated terminal event. Phase `FAIL`, never success and not a tester error.
- `LOG_TRUNCATED`: the runner could not retain complete stdout, stderr, or combined logs, or the Docker worker exceeded its output quota. Classify as `INCONCLUSIVE`, high confidence, action `RAISE_LOG_LIMIT`, and `port_candidate=false`. A cut event is not treated as package tampering.
- `ENGINE_SHUTDOWN_CRASH_AFTER_PASS` / `ENGINE_SHUTDOWN_CRASH_AFTER_FAIL`: warning identifying a crash strictly after an authenticated terminal pass or fail, with no earlier crash-handler marker in the retained combined log. The phase remains `CRASH` unless canary reproduction or the bounded retry rule below supplies additional evidence.
- `ENGINE_BASELINE_SHUTDOWN_CRASH`: reviewed warning after the same engine/phase crashes after success without the selected plugin, with up to three fresh canary attempts. Editor canaries activate a shipped no-op addon through the same `set_plugin_enabled` and activation-check path. Import canaries only scan; runtime canaries run without plugin probes. Recompute the plugin phase as `PASS` only if no other failure remains; retain the original exit code and logs.
- `ENGINE_INTERMITTENT_SHUTDOWN_CRASH`: reviewed warning after an authenticated terminal pass or fail followed by a crash, unreproduced by the canaries, and a subsequent authenticated same-phase attempt that exits without crashing. Error findings do not prevent retry. Use the non-crashing attempt's status and findings, including `FAIL` for plugin/API errors. At most two additional plugin attempts run, each with fresh project/state/session/logs and the original acquired addon bytes. Stop at the first valid non-crashing result or different failure. Confidence is capped at medium, with a limitation explaining the intermittent shutdown crash; this does not prove the engine caused it.
- `ENGINE_SHUTDOWN_CRASH_RETRY_EXHAUSTED`: warning when all three plugin attempts crash strictly after authenticated terminal pass/fail. Derive the phase result from retained pre-crash evidence: any terminal fail or error finding yields `FAIL`; otherwise `PASS`. Preserve raw crash exits, logs, events, and findings in the attempt records. Confidence is capped at medium with a limitation that shutdown stability remains unverified. Pre-terminal crashes remain `CRASH`; timeouts, protocol errors, tampering, truncation, and incomplete evidence cannot be retried into success. These rules apply equally to Redot and the exact Godot control.
- `ENGINE_BASELINE_DIAGNOSTIC`: info finding replacing an `UNREVIEWED_*` diagnostic reproduced by the bare canary. Matching strips ANSI, normalizes digits, and masks run IDs and paths. Plugin-specific errors remain decisive.
- `SHUTDOWN_RESOURCE_LEAK`: reviewed warning for ObjectDB, RID, resource, and leaked-instance diagnostics at engine shutdown. It does not by itself prevent a compatibility result.
- `API_SYMBOL_MISSING`: checked before generic GDScript parse errors so missing identifiers/members remain visible.
- `EDITOR_ACTIVATION_FAILURE`: real engine addon-load/disable diagnostics, rather than arbitrary prose mentioning a disabled editor plugin.

Canaries run only after an unexplained diagnostic or a shutdown crash after authenticated pass/fail. Their complete evidence is stored separately in `CompatibilityResult.engine_canary_phases`; they never become selected plugin phases. `CompatibilityResult.phase_retry_attempts` retains every raw plugin attempt for each retried phase, including the initial crash and any non-crashing retry; `phases` contains the final reviewed result. Attempt records identify the engine role and phase and retain original commands, exit codes, events, and log paths. Redot and control retries/canaries use their own exact engine and isolated state. Each engine/phase has at most three plugin attempts plus three canaries, all subject to its configured wall-clock timeout. A failed canary is retained as evidence and cannot establish a baseline pass.

## Static dependency findings

- `DOTNET_GODOT_SDK`: a project declares `Godot.NET.Sdk`, which is not Redot's SDK; review migration to `Redot.NET.Sdk/26.x` and use a matching .NET-capable engine. This is dependency evidence, not proof of runtime compatibility.
- `GDEXTENSION_MAXIMUM_BELOW_BASELINE`: the extension's declared `compatibility_maximum` excludes the target baseline. Review/rebuild the extension rather than interpreting the upper bound as a compatible minimum.

## Exit codes

| Code | Meaning |
|---:|---|
| 2 | invalid command usage or configuration |
| 0 | compatible or no port required after testing |
| 10 | baseline-policy skip |
| 20 | port required |
| 30 | invalid package or upstream package failure |
| 40 | inconclusive or missing environment |
| 50 | tester internal error |
