# Compatibility classifications

The public enum is defined in `redot_compat.models.CompatibilityStatus`. The first matching decisive rule wins; secondary findings remain in `result.json`.

## No-port results

- `NO_PORT_NEEDED_BASELINE_POLICY`: decisive target evidence is Godot 4.5.2 or earlier and execution was skipped by policy. This is not a runtime test.
- `COMPATIBLE_UNCHANGED`: all required dynamic phases produced explicit success evidence under Redot.
- `COMPATIBLE_REPACKAGE_ONLY`: code works but archive or manifest normalization is required.

## Port-required results

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

For an exact paired run, `TIMEOUT` and `CRASHED` remain the primary status. A passing Godot control can raise confidence and set `port_candidate=true`, but it does not invent a more specific API/native cause without supporting evidence. A control failure or compatibility-lineage mismatch yields `INCONCLUSIVE` rather than Redot-specific blame.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | compatible or no port required after testing |
| 10 | baseline-policy skip |
| 20 | port required |
| 30 | invalid package or upstream package failure |
| 40 | inconclusive or missing environment |
| 50 | tester internal error |
