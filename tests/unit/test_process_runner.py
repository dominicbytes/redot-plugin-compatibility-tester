from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from redot_compat.runner.process import run_process


def test_process_runner_uses_argument_array_and_bounded_logs(tmp_path: Path) -> None:
    result = run_process(
        [sys.executable, "-c", "print('x' * 10000)"],
        working_directory=tmp_path,
        environment={},
        output_directory=tmp_path / "logs",
        timeout_seconds=5,
        max_log_bytes=512,
    )

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.stdout_truncated is True
    assert (tmp_path / "logs/stdout.log").stat().st_size <= 512
    assert (tmp_path / "logs/combined.log").stat().st_size <= 512


def test_process_runner_times_out_and_reaps_process(tmp_path: Path) -> None:
    result = run_process(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        working_directory=tmp_path,
        environment={},
        output_directory=tmp_path / "timeout-logs",
        timeout_seconds=0.2,
    )

    assert result.timed_out is True
    assert result.exit_code is not None


def test_process_runner_redacts_recorded_arguments(tmp_path: Path) -> None:
    result = run_process(
        [sys.executable, "-c", "pass", "--token", "top-secret"],
        working_directory=tmp_path,
        environment={},
        output_directory=tmp_path / "redacted-logs",
        timeout_seconds=5,
    )

    assert "top-secret" not in repr(result.command)
    assert "<redacted>" in result.command


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object integration")
def test_windows_job_reaps_child_and_grandchild_on_timeout(tmp_path: Path) -> None:
    pid_path = tmp_path / "owned-pids.txt"
    grandchild_code = "import time; time.sleep(30)"
    child_code = (
        "import os, subprocess, sys, time; "
        f"child=subprocess.Popen([sys.executable, '-c', {grandchild_code!r}]); "
        f"open({str(pid_path)!r}, 'w', encoding='utf-8').write(f'{{os.getpid()}} {{child.pid}}'); "
        "time.sleep(30)"
    )

    result = run_process(
        [sys.executable, "-c", child_code],
        working_directory=tmp_path,
        environment={},
        output_directory=tmp_path / "job-timeout-logs",
        timeout_seconds=1,
    )

    assert result.ownership == "windows_job"
    assert result.timed_out is True
    pids = [int(value) for value in pid_path.read_text(encoding="utf-8").split()]
    assert _wait_until_gone(pids)


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object integration")
def test_windows_job_kills_descendants_when_controller_exits(tmp_path: Path) -> None:
    pid_path = tmp_path / "controller-owned-pids.txt"
    log_path = tmp_path / "controller-logs"
    grandchild_code = "import time; time.sleep(30)"
    child_code = (
        "import os, subprocess, sys, time; "
        f"child=subprocess.Popen([sys.executable, '-c', {grandchild_code!r}]); "
        f"open({str(pid_path)!r}, 'w', encoding='utf-8').write(f'{{os.getpid()}} {{child.pid}}'); "
        "time.sleep(30)"
    )
    controller_code = (
        "import os, sys; from pathlib import Path; "
        "from redot_compat.runner.process import run_process; "
        f"run_process([sys.executable, '-c', {child_code!r}], "
        f"working_directory=Path({str(tmp_path)!r}), environment={{}}, "
        f"output_directory=Path({str(log_path)!r}), timeout_seconds=30)"
    )
    controller = subprocess.Popen(
        [sys.executable, "-c", controller_code],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 5
    while not pid_path.exists() and time.monotonic() < deadline:
        if controller.poll() is not None:
            stderr = controller.stderr.read().decode(errors="replace") if controller.stderr else ""
            pytest.fail(f"controller exited before spawning fixture: {stderr}")
        time.sleep(0.05)
    assert pid_path.exists()
    pids = [int(value) for value in pid_path.read_text(encoding="utf-8").split()]

    controller.kill()
    controller.wait(timeout=5)

    assert _wait_until_gone(pids)


def _wait_until_gone(pids: list[int], *, timeout_seconds: float = 5) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not any(psutil.pid_exists(pid) for pid in pids):
            return True
        time.sleep(0.05)
    return not any(psutil.pid_exists(pid) for pid in pids)
