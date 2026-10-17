from __future__ import annotations

import pytest
from pydantic import ValidationError

from redot_compat.config import PhaseTimeouts
from redot_compat.models import PluginTestManifest
from redot_compat.models.enums import PhaseName
from redot_compat.sandbox.worker_protocol import WorkerRequest


def test_worker_request_only_accepts_declared_relative_paths() -> None:
    request = WorkerRequest(
        run_id="run-" + "a" * 32,
        source_subpath="addons/example",
        phases=[PhaseName.IMPORT, PhaseName.EDITOR],
        engine_sha256="b" * 64,
    )

    assert request.source_subpath == "addons/example"

    with pytest.raises(ValidationError):
        WorkerRequest(
            run_id="run-" + "a" * 32,
            source_subpath="../../escape",
            phases=[PhaseName.IMPORT],
            engine_sha256="b" * 64,
        )


def test_worker_request_accepts_the_input_mount_root() -> None:
    request = WorkerRequest(
        run_id="run-" + "a" * 32,
        source_subpath=".",
        phases=[PhaseName.IMPORT],
        engine_sha256="b" * 64,
    )

    assert request.source_subpath == "."


def test_worker_request_rejects_output_escape() -> None:
    with pytest.raises(ValidationError):
        WorkerRequest(
            run_id="run-" + "a" * 32,
            source_subpath=".",
            output_subpath="../escape",
            phases=[PhaseName.IMPORT],
            engine_sha256="b" * 64,
        )


def test_legacy_worker_request_defaults_to_worker_timeouts() -> None:
    request = WorkerRequest.model_validate(
        {
            "run_id": "run-" + "a" * 32,
            "source_subpath": ".",
            "phases": ["import"],
            "engine_sha256": "b" * 64,
        }
    )
    assert request.protocol_version == 1
    assert request.phase_timeouts is None


def test_worker_timeout_settings_round_trip_without_forcing_manifest_default() -> None:
    request = WorkerRequest(
        run_id="run-" + "a" * 32,
        source_subpath=".",
        phases=[PhaseName.IMPORT],
        engine_sha256="b" * 64,
        manifest=PluginTestManifest(plugin_id="example"),
        phase_timeouts=PhaseTimeouts(import_phase=9, editor=11),
    )
    restored = WorkerRequest.model_validate_json(request.model_dump_json(exclude_unset=True))
    assert restored.phase_timeouts is not None
    assert restored.phase_timeouts.import_phase == 9
    assert restored.phase_timeouts.editor == 11
    assert restored.manifest is not None
    assert "timeout_seconds" not in restored.manifest.model_fields_set
