from __future__ import annotations

import pytest
from pydantic import ValidationError

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
