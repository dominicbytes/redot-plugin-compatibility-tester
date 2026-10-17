from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from redot_compat.errors import ConfigurationError
from redot_compat.runner.process import ProcessResult
from redot_compat.sandbox import docker_linux
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
    assert "--memory 4g" in joined
    assert "--memory-swap 4g" in joined
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


@pytest.mark.parametrize("character", [",", '"', "\n", "\r"])
@pytest.mark.parametrize("mount", ["source", "output", "heartbeat"])
def test_docker_command_rejects_unsafe_mount_paths(
    tmp_path: Path, character: str, mount: str
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    heartbeat = tmp_path / "heartbeat"
    source.mkdir()
    output.mkdir()
    heartbeat.write_text("0")
    paths = {"source": source, "output": output, "heartbeat": heartbeat}
    paths[mount] = tmp_path / f"bad{character}path"
    with pytest.raises(ConfigurationError, match="commas, quotes, or newlines"):
        build_docker_command(
            DockerProfile(image="example/worker@sha256:" + "a" * 64),
            run_id="run-" + "b" * 32,
            source=paths["source"],
            output=paths["output"],
            heartbeat=paths["heartbeat"],
            request_path="/output/request.json",
        )


def test_output_size_check_counts_nested_regular_files(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "one").write_bytes(b"123")
    (tmp_path / "nested/two").write_bytes(b"4567")
    assert not docker_linux.output_directory_exceeds_limit(tmp_path, max_bytes=7)
    assert docker_linux.output_directory_exceeds_limit(tmp_path, max_bytes=6)
    assert DockerProfile(image="unused").max_output_bytes == 2 * 1024**3


def test_output_size_check_does_not_follow_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "output"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "large").write_bytes(b"x" * 100)
    try:
        (root / "file-link").symlink_to(outside / "large")
        (root / "dir-link").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    assert not docker_linux.output_directory_exceeds_limit(root, max_bytes=1)


def _controller_fixture(tmp_path: Path) -> tuple[list[str], Path, ProcessResult]:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    heartbeat = docker_linux.prepare_heartbeat(tmp_path / "heartbeat")
    command = build_docker_command(
        DockerProfile(image="example/worker@sha256:" + "a" * 64),
        run_id="run-" + "b" * 32,
        source=source,
        output=output,
        heartbeat=heartbeat,
        request_path="/output/request.json",
    )
    now = datetime.now(UTC)
    result = ProcessResult(
        command=command,
        working_directory=str(tmp_path),
        started_at=now,
        finished_at=now,
        duration_ms=0,
        exit_code=0,
        timed_out=False,
        stdout_path="stdout",
        stderr_path="stderr",
        combined_log_path="combined",
        ownership="test",
    )
    return command, heartbeat, result


def test_docker_cleanup_failure_does_not_mask_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    command, heartbeat, expected = _controller_fixture(tmp_path)
    monkeypatch.setattr(docker_linux, "run_process", Mock(return_value=expected))
    monkeypatch.setattr(
        docker_linux,
        "cleanup_owned_container",
        Mock(side_effect=ConfigurationError("cleanup failed")),
    )
    result = docker_linux.run_docker_command(
        command,
        run_id="run-" + "b" * 32,
        heartbeat=heartbeat,
        working_directory=tmp_path,
        output_directory=tmp_path / "logs",
        timeout_seconds=5,
    )
    assert result is expected
    assert "failed to clean up owned Docker container" in caplog.text
    assert not heartbeat.exists()


def test_heartbeat_writer_records_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    writer = docker_linux._HeartbeatWriter(tmp_path / "heartbeat")
    monkeypatch.setattr(writer._stop, "wait", Mock(return_value=False))
    monkeypatch.setattr(Path, "write_text", Mock(side_effect=OSError("disk full")))
    writer._run()
    assert isinstance(writer.error, OSError)
    assert str(writer.error) == "disk full"


def test_docker_controller_reports_heartbeat_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command, heartbeat, expected = _controller_fixture(tmp_path)
    monkeypatch.setattr(docker_linux, "run_process", Mock(return_value=expected))
    cleanup = Mock()
    monkeypatch.setattr(docker_linux, "cleanup_owned_container", cleanup)

    def fail_heartbeat(writer: docker_linux._HeartbeatWriter) -> None:
        writer.error = OSError("disk full")

    monkeypatch.setattr(docker_linux._HeartbeatWriter, "start", fail_heartbeat)
    with pytest.raises(ConfigurationError, match="controller heartbeat failed: disk full"):
        docker_linux.run_docker_command(
            command,
            run_id="run-" + "b" * 32,
            heartbeat=heartbeat,
            working_directory=tmp_path,
            output_directory=tmp_path / "logs",
            timeout_seconds=5,
        )
    cleanup.assert_called_once()


def test_output_watchdog_removes_container_and_marks_quota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "large").write_bytes(b"1234")
    watchdog = docker_linux._OutputWatchdog(tmp_path, "run-" + "b" * 32, 3)
    monkeypatch.setattr(watchdog._stop, "wait", Mock(return_value=False))
    cleanup = Mock()
    monkeypatch.setattr(docker_linux, "cleanup_owned_container", cleanup)
    watchdog._run()
    assert watchdog.quota_exceeded
    cleanup.assert_called_once_with("run-" + "b" * 32)


def test_output_watchdog_polls_and_stops_with_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checked = threading.Event()

    def check(directory: Path, *, max_bytes: int) -> bool:
        checked.set()
        return False

    monkeypatch.setattr(docker_linux, "output_directory_exceeds_limit", check)
    watchdog = docker_linux._OutputWatchdog(tmp_path, "run-" + "b" * 32, 3)
    watchdog.start()
    try:
        assert checked.wait(4)
    finally:
        watchdog.stop()
    assert not watchdog._thread.is_alive()


def test_docker_controller_exposes_quota_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command, heartbeat, expected = _controller_fixture(tmp_path)
    monkeypatch.setattr(docker_linux, "run_process", Mock(return_value=expected))
    monkeypatch.setattr(docker_linux, "cleanup_owned_container", Mock())

    def exceed_quota(watchdog: docker_linux._OutputWatchdog) -> None:
        watchdog.quota_exceeded = True
        assert watchdog._directory == tmp_path / "output"
        assert watchdog._max_bytes == 7

    monkeypatch.setattr(docker_linux._OutputWatchdog, "start", exceed_quota)
    result = docker_linux.run_docker_command(
        command,
        run_id="run-" + "b" * 32,
        heartbeat=heartbeat,
        working_directory=tmp_path,
        output_directory=tmp_path / "logs",
        timeout_seconds=5,
        max_output_bytes=7,
    )
    assert result.output_quota_exceeded


def test_output_watchdog_records_scan_error_and_stops_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watchdog = docker_linux._OutputWatchdog(tmp_path, "run-" + "b" * 32, 3)
    monkeypatch.setattr(watchdog._stop, "wait", Mock(return_value=False))
    monkeypatch.setattr(
        docker_linux, "output_directory_exceeds_limit", Mock(side_effect=OSError("cannot scan"))
    )
    cleanup = Mock()
    monkeypatch.setattr(docker_linux, "cleanup_owned_container", cleanup)
    watchdog._run()
    assert str(watchdog.error) == "cannot scan"
    assert not watchdog.quota_exceeded
    cleanup.assert_called_once_with("run-" + "b" * 32)
