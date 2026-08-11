from __future__ import annotations

import json
from pathlib import Path

import pytest

from redot_compat.errors import ConfigurationError
from redot_compat.models import CompatibilityResult
from redot_compat.models.enums import CompatibilityStatus
from redot_compat.testing.service import test_source


def test_baseline_test_stops_at_policy_without_engine(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"

    result = test_source(str(fixture), tmp_path / "baseline")

    assert result.classification is CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY
    assert result.phases == []


def test_dynamic_test_refuses_silent_host_fallback(tmp_path: Path) -> None:
    source = tmp_path / "source"
    addon = source / "addons/example"
    addon.mkdir(parents=True)
    (addon / "plugin.cfg").write_text(
        '[plugin]\nname="Example"\nscript="plugin.gd"\n', encoding="utf-8"
    )
    (addon / "plugin.gd").write_text("@tool\nextends EditorPlugin\n", encoding="utf-8")
    output = tmp_path / "result"

    result = test_source(str(source), output)

    assert result.classification is CompatibilityStatus.MISSING_EXTERNAL_SERVICE
    assert result.sandbox == "none"
    assert result.policy.dynamic_testing_performed is False
    assert json.loads((output / "result.json").read_text(encoding="utf-8"))["classification"] == (
        "MISSING_EXTERNAL_SERVICE"
    )


def test_configured_digest_pinned_docker_backend_is_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "docker-source"
    addon = source / "addons/example"
    addon.mkdir(parents=True)
    (addon / "plugin.cfg").write_text(
        '[plugin]\nname="Example"\nscript="plugin.gd"\n', encoding="utf-8"
    )
    (addon / "plugin.gd").write_text("@tool\nextends EditorPlugin\n", encoding="utf-8")
    selected: list[str] = []

    monkeypatch.setattr(
        "redot_compat.testing.service.docker_daemon_available",
        lambda: (True, "test-daemon"),
    )

    def fake_worker(static_result: CompatibilityResult, *_: object) -> CompatibilityResult:
        selected.append("docker")
        return static_result.model_copy(update={"sandbox": "docker_linux"})

    monkeypatch.setattr("redot_compat.testing.service._run_docker_backend", fake_worker)
    result = test_source(
        str(source),
        tmp_path / "docker-result",
        backend="docker",
        worker_image="example/worker@sha256:" + "a" * 64,
        worker_engine_sha256="b" * 64,
    )

    assert selected == ["docker"]
    assert result.sandbox == "docker_linux"


def test_docker_backend_requires_image_and_engine_hash_together(tmp_path: Path) -> None:
    source = tmp_path / "incomplete-source"
    addon = source / "addons/example"
    addon.mkdir(parents=True)
    (addon / "plugin.cfg").write_text('[plugin]\nname="Example"\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="both --worker-image"):
        test_source(
            str(source),
            tmp_path / "incomplete-result",
            backend="docker",
            worker_image="example/worker@sha256:" + "a" * 64,
        )
