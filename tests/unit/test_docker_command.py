from __future__ import annotations

from pathlib import Path

import pytest

from redot_compat.errors import ConfigurationError
from redot_compat.sandbox.docker_linux import DockerProfile, build_docker_command


def test_docker_command_applies_mandatory_restrictions(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    command = build_docker_command(
        DockerProfile(image="example/worker@sha256:" + "a" * 64),
        run_id="run-" + "b" * 32,
        source=source,
        output=output,
        request_path="/output/request.json",
    )

    joined = " ".join(command)
    assert "--network none" in joined
    assert "--read-only" in command
    assert "--cap-drop ALL" in joined
    assert "no-new-privileges" in command
    assert "--pids-limit 256" in joined
    assert "--user 10001:10001" in joined
    assert "readonly" in joined
    assert "/var/run/docker.sock" not in joined
    assert command[-2:] == ["--request", "/output/request.json"]


def test_docker_command_requires_digest_pinned_image(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()

    with pytest.raises(ConfigurationError, match="digest-pinned"):
        build_docker_command(
            DockerProfile(image="example/worker:latest"),
            run_id="run-" + "b" * 32,
            source=source,
            output=output,
            request_path="/output/request.json",
        )


def test_docker_command_mounts_controller_heartbeat_read_only(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    heartbeat = tmp_path / "heartbeat"
    source.mkdir()
    output.mkdir()
    heartbeat.write_text("0\n", encoding="utf-8")

    command = build_docker_command(
        DockerProfile(image="example/worker@sha256:" + "a" * 64),
        run_id="run-" + "b" * 32,
        source=source,
        output=output,
        request_path="/output/request.json",
        heartbeat=heartbeat,
    )

    joined = " ".join(command)
    assert "REDOT_COMPAT_HEARTBEAT_PATH=/run/redot-compat-heartbeat" in joined
    assert "target=/run/redot-compat-heartbeat,readonly" in joined
