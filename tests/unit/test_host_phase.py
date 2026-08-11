from __future__ import annotations

import os
import sys
from pathlib import Path

from redot_compat.models import EngineRole, PhaseName, PhaseStatus
from redot_compat.testing.host import run_host_phase


def test_harness_pass_cannot_override_engine_error(tmp_path: Path) -> None:
    script = "\n".join(
        [
            "import sys",
            'print(\'REDOT_COMPAT_EVENT {"schema":1,"run_id":"test-run",\' '
            '\'"sequence":0,"event":"start","payload":{}}\')',
            'print(\'REDOT_COMPAT_EVENT {"schema":1,"run_id":"test-run",\' '
            '\'"sequence":1,"event":"pass","payload":{}}\')',
            "print('ERROR: unexpected engine failure', file=sys.stderr)",
        ]
    )

    result = run_host_phase(
        [sys.executable, "-c", script],
        phase_name=PhaseName.RUNTIME,
        run_id="test-run",
        working_directory=tmp_path,
        environment=os.environ,
        log_directory=tmp_path / "logs",
        timeout_seconds=10,
        expect_harness_events=True,
    )

    assert result.status is PhaseStatus.FAIL
    assert [finding.code for finding in result.findings] == ["UNREVIEWED_ERROR"]


def test_host_phase_preserves_selected_engine_role(tmp_path: Path) -> None:
    result = run_host_phase(
        [sys.executable, "-c", "print('ERROR: control failure')"],
        phase_name=PhaseName.IMPORT,
        run_id="control-run",
        working_directory=tmp_path,
        environment=os.environ,
        log_directory=tmp_path / "control-logs",
        timeout_seconds=10,
        expect_harness_events=False,
        engine_role=EngineRole.GODOT_CONTROL,
    )

    assert result.engine_role is EngineRole.GODOT_CONTROL
    assert result.findings[0].engine_role is EngineRole.GODOT_CONTROL
