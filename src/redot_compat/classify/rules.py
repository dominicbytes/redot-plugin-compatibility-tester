from __future__ import annotations

from pydantic import Field

from redot_compat.classify.differential import DifferentialOutcome, compare_phase_status
from redot_compat.models import (
    CompatibilityStatus,
    Confidence,
    EngineRole,
    PackageKind,
    PhaseName,
    PhaseResult,
    PhaseStatus,
    PluginInventory,
    RecommendedAction,
)
from redot_compat.models.base import ContractModel


class ClassificationContext(ContractModel):
    inventory: PluginInventory
    phases: list[PhaseResult] = Field(default_factory=list)
    exact_control: bool = False
    api_gap_direct: bool = False
    selected_scope_complete: bool = True


class ClassificationDecision(ContractModel):
    status: CompatibilityStatus
    confidence: Confidence
    confidence_reasons: list[str] = Field(min_length=1)
    port_candidate: bool
    action: RecommendedAction


def classify(context: ClassificationContext) -> ClassificationDecision:
    redot = [phase for phase in context.phases if phase.engine_role is EngineRole.REDOT]
    controls = {
        phase.phase_name: phase
        for phase in context.phases
        if phase.engine_role is EngineRole.GODOT_CONTROL
    }
    if any(phase.status is PhaseStatus.TESTER_ERROR for phase in context.phases):
        return _decision(
            CompatibilityStatus.INTERNAL_TESTER_ERROR,
            Confidence.HIGH,
            False,
            "FIX_TESTER",
            "Inspect tester logs before drawing a plugin conclusion.",
            "A process-controller or harness failure outranks plugin evidence.",
        )
    if context.inventory.package_kind is PackageKind.UNKNOWN and not context.inventory.plugin_roots:
        return _decision(
            CompatibilityStatus.INVALID_PACKAGE,
            Confidence.HIGH,
            False,
            "FIX_PACKAGE_LAYOUT",
            "Provide a supported plugin, project, or native package layout.",
            "No supported package root was inventoried.",
        )
    crashed = next((phase for phase in redot if phase.status is PhaseStatus.CRASH), None)
    if crashed is not None:
        exact_specific = _control_passed(crashed, controls, context.exact_control)
        return _decision(
            CompatibilityStatus.CRASHED,
            Confidence.HIGH if exact_specific else Confidence.MEDIUM,
            exact_specific,
            "REVIEW_CRASH",
            "Review the retained crash and engine identity before attempting a port.",
            (
                "Redot crashed while the matched exact-control phase passed."
                if exact_specific
                else (
                    "The Redot process crashed; attribution remains scope-limited without "
                    "a control."
                )
            ),
        )
    timed_out = next((phase for phase in redot if phase.status is PhaseStatus.TIMEOUT), None)
    if timed_out is not None:
        exact_specific = _control_passed(timed_out, controls, context.exact_control)
        return _decision(
            CompatibilityStatus.TIMEOUT,
            Confidence.HIGH if exact_specific else Confidence.MEDIUM,
            exact_specific,
            "REVIEW_TIMEOUT",
            "Review the bounded phase log and decide whether the fixture needs a justified limit.",
            (
                "Redot timed out while the matched exact-control phase passed."
                if exact_specific
                else "A Redot phase exceeded its configured wall-clock limit."
            ),
        )
    if context.exact_control:
        for phase in redot:
            control = controls.get(phase.phase_name)
            if (
                control
                and compare_phase_status(phase.status, control.status)
                is DifferentialOutcome.BOTH_FAILED
            ):
                return _decision(
                    CompatibilityStatus.UPSTREAM_PACKAGE_FAILURE,
                    Confidence.HIGH,
                    False,
                    "FIX_UPSTREAM_PACKAGE",
                    "Reproduce and fix the same failure under the exact Godot control first.",
                    "The matched phase failed under both exact engines.",
                )
        for phase in redot:
            control = controls.get(phase.phase_name)
            if (
                phase.status is PhaseStatus.PASS
                and control is not None
                and control.status is not PhaseStatus.PASS
            ):
                return _decision(
                    CompatibilityStatus.INCONCLUSIVE,
                    Confidence.HIGH,
                    False,
                    "FIX_CONTROL_FIXTURE",
                    "Fix or replace the failing exact-control fixture before comparing engines.",
                    "Redot passed, but the matched exact-control phase failed.",
                )
    missing = next(
        (phase for phase in redot if phase.status is PhaseStatus.MISSING_CAPABILITY), None
    )
    if missing:
        status = _missing_capability_status(context.inventory, missing.phase_name)
        return _decision(
            status,
            Confidence.HIGH,
            False,
            "CONFIGURE_CAPABILITY",
            "Configure the exact missing engine, display, platform artifact, or worker capability.",
            "The requested phase did not run because a required capability is absent.",
        )
    if context.inventory.contains_engine_module:
        return _decision(
            CompatibilityStatus.PORT_REQUIRED_ENGINE_MODULE,
            Confidence.HIGH,
            True,
            "BUILD_CUSTOM_REDOT_ENGINE",
            "Port and compile this engine module in a custom Redot build.",
            "Static inventory identified an engine module.",
        )
    failed = next((phase for phase in redot if phase.status is PhaseStatus.FAIL), None)
    if failed:
        status = _failure_status(context, failed.phase_name)
        exact_specific = context.exact_control and controls.get(failed.phase_name) is not None
        confidence = Confidence.HIGH if exact_specific else Confidence.MEDIUM
        return _decision(
            status,
            confidence,
            status.value.startswith("PORT_REQUIRED_")
            or status is CompatibilityStatus.ENGINE_API_GAP,
            _action_code(status),
            _action_text(status),
            (
                "The exact control passed the matched phase."
                if exact_specific
                else "Redot failed, but no matching exact control result is available."
            ),
        )
    if any(
        finding.code == "UNREVIEWED_WARNING"
        for phase in context.phases
        for finding in phase.findings
    ):
        return _decision(
            CompatibilityStatus.INCONCLUSIVE,
            Confidence.LOW,
            False,
            "REVIEW_WARNING",
            "Review or explicitly allowlist the retained engine warning.",
            "An unexplained engine warning prevents a compatibility claim.",
        )
    executed = [phase for phase in redot if phase.status is not PhaseStatus.NOT_RUN]
    if executed and all(phase.status is PhaseStatus.PASS for phase in executed):
        if not context.selected_scope_complete:
            return _decision(
                CompatibilityStatus.INCONCLUSIVE,
                Confidence.LOW,
                False,
                "ADD_DECLARATIVE_PROBES",
                "Add plugin-specific declarative probes before claiming compatibility.",
                "The engine imported the fixture, but the plugin's behavior was not exercised.",
            )
        exact_pass = context.exact_control and all(
            controls.get(phase.phase_name) is not None
            and controls[phase.phase_name].status is PhaseStatus.PASS
            for phase in executed
        )
        return _decision(
            CompatibilityStatus.COMPATIBLE_UNCHANGED,
            Confidence.HIGH if exact_pass else Confidence.MEDIUM,
            False,
            "NO_CHANGE_FOR_TESTED_SCOPE",
            "No source change is indicated for the tested phases and platform.",
            (
                "Matched Redot and exact-control phases passed."
                if exact_pass
                else (
                    "Selected Redot phases passed; untested platforms and missing control "
                    "remain limitations."
                )
            ),
        )
    return _decision(
        CompatibilityStatus.INCONCLUSIVE,
        Confidence.LOW,
        False,
        "ADD_EVIDENCE",
        "Configure a contained engine run or add a declarative probe manifest.",
        "No decisive dynamic phase evidence is available.",
    )


def _missing_capability_status(
    inventory: PluginInventory, phase_name: PhaseName
) -> CompatibilityStatus:
    if inventory.contains_dotnet or phase_name is PhaseName.DOTNET:
        return CompatibilityStatus.MISSING_DOTNET_ENGINE
    if phase_name is PhaseName.GUI:
        return CompatibilityStatus.DISPLAY_REQUIRED
    if inventory.contains_native_binaries:
        return CompatibilityStatus.MISSING_PLATFORM_BINARY
    return CompatibilityStatus.MISSING_EXTERNAL_SERVICE


def _control_passed(
    phase: PhaseResult,
    controls: dict[PhaseName, PhaseResult],
    exact_control: bool,
) -> bool:
    control = controls.get(phase.phase_name)
    return exact_control and control is not None and control.status is PhaseStatus.PASS


def _failure_status(context: ClassificationContext, phase_name: PhaseName) -> CompatibilityStatus:
    if context.api_gap_direct and context.exact_control:
        return CompatibilityStatus.ENGINE_API_GAP
    if phase_name in {PhaseName.IMPORT, PhaseName.PARSE}:
        return CompatibilityStatus.PORT_REQUIRED_GDSCRIPT_API
    if phase_name is PhaseName.EDITOR:
        return CompatibilityStatus.PORT_REQUIRED_EDITOR_API
    if phase_name in {PhaseName.RUNTIME, PhaseName.GUI}:
        return CompatibilityStatus.PORT_REQUIRED_RUNTIME_API
    if phase_name is PhaseName.EXPORT:
        return CompatibilityStatus.PORT_REQUIRED_EXPORT_PACKAGING
    return CompatibilityStatus.INCONCLUSIVE


def _action_code(status: CompatibilityStatus) -> str:
    return {
        CompatibilityStatus.ENGINE_API_GAP: "REPORT_ENGINE_API_GAP",
        CompatibilityStatus.PORT_REQUIRED_GDSCRIPT_API: "PORT_GDSCRIPT_API",
        CompatibilityStatus.PORT_REQUIRED_EDITOR_API: "PORT_EDITOR_API",
        CompatibilityStatus.PORT_REQUIRED_RUNTIME_API: "PORT_RUNTIME_API",
        CompatibilityStatus.PORT_REQUIRED_EXPORT_PACKAGING: "FIX_EXPORT_PACKAGING",
    }.get(status, "REVIEW_PHASE_FAILURE")


def _action_text(status: CompatibilityStatus) -> str:
    return {
        CompatibilityStatus.ENGINE_API_GAP: (
            "Confirm the API diff and report the Redot-specific gap."
        ),
        CompatibilityStatus.PORT_REQUIRED_GDSCRIPT_API: (
            "Update the first failing GDScript API use."
        ),
        CompatibilityStatus.PORT_REQUIRED_EDITOR_API: "Update the first failing editor API use.",
        CompatibilityStatus.PORT_REQUIRED_RUNTIME_API: "Update the first failing runtime API use.",
        CompatibilityStatus.PORT_REQUIRED_EXPORT_PACKAGING: (
            "Correct the export or packaged artifact path."
        ),
    }.get(status, "Review the first failing phase and retained evidence.")


def _decision(
    status: CompatibilityStatus,
    confidence: Confidence,
    port_candidate: bool,
    action_code: str,
    action_text: str,
    reason: str,
) -> ClassificationDecision:
    return ClassificationDecision(
        status=status,
        confidence=confidence,
        confidence_reasons=[reason],
        port_candidate=port_candidate,
        action=RecommendedAction(code=action_code, text=action_text),
    )
