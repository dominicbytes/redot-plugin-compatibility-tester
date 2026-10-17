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


def test_process_runner_redacts_secrets_across_read_chunks(tmp_path: Path) -> None:
    secret = "split-secret-value"  # noqa: S105 - synthetic redaction fixture
    code = (
        "import os, sys; "
        "text = 'x' * 4093 + os.environ['TEST_TOKEN'] + '?' * 4096; "
        "sys.stdout.write(text); sys.stderr.write(text)"
    )
    result = run_process(
        [sys.executable, "-c", code],
        working_directory=tmp_path,
        environment={"TEST_TOKEN": secret},
        output_directory=tmp_path / "split-secret-logs",
        timeout_seconds=5,
    )
    for path in (result.stdout_path, result.stderr_path, result.combined_log_path):
        text = Path(path).read_text(encoding="utf-8")
        assert secret not in text
        assert "<redacted>" in text
        assert "\ufffd" not in text
    assert not result.stdout_truncated
    assert not result.stderr_truncated
    assert not result.combined_truncated


def test_process_runner_exposes_stderr_and_combined_truncation(tmp_path: Path) -> None:
    result = run_process(
        [sys.executable, "-c", "import sys; sys.stderr.write('x' * 10000)"],
        working_directory=tmp_path,
        environment={},
        output_directory=tmp_path / "stderr-truncated",
        timeout_seconds=5,
        max_log_bytes=512,
    )
    assert not result.stdout_truncated
    assert result.stderr_truncated
    assert result.combined_truncated


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group teardown")
@pytest.mark.parametrize("timeout", [False, True])
def test_posix_group_kills_reparented_sigterm_resistant_grandchild(
    tmp_path: Path, timeout: bool
) -> None:
    pid_path = tmp_path / "orphan-pid.txt"
    grandchild = (
        "import os, signal, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"open({str(pid_path)!r}, 'w').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    child = (
        "import pathlib, subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}]); "
        f"path = pathlib.Path({str(pid_path)!r}); "
        "exec('while not path.exists(): time.sleep(0.01)')"
    )
    root = (
        "import subprocess, sys, time; "
        f"subprocess.run([sys.executable, '-c', {child!r}], check=True); "
        + ("time.sleep(30)" if timeout else "pass")
    )
    try:
        result = run_process(
            [sys.executable, "-c", root],
            working_directory=tmp_path,
            environment={},
            output_directory=tmp_path / "posix-logs",
            timeout_seconds=2 if timeout else 5,
        )
        assert result.timed_out is timeout
        if not timeout:
            assert result.exit_code == 0
        pid = int(pid_path.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                break
            time.sleep(0.05)
        else:
            pytest.fail("SIGTERM-resistant orphan survived process-group teardown")
    finally:
        if pid_path.exists():
            try:
                psutil.Process(int(pid_path.read_text())).kill()
            except psutil.Error:
                pass


def test_process_runner_retains_short_output_before_process_exit(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    ack = tmp_path / "ack"
    code = (
        "import pathlib, time; print('ready', flush=True); "
        f"ack = pathlib.Path({str(ack)!r}); "
        "exec('while not ack.exists(): time.sleep(0.01)')"
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_process,
            [sys.executable, "-c", code],
            working_directory=tmp_path,
            environment={},
            output_directory=tmp_path / "live",
            timeout_seconds=5,
        )
        retained = tmp_path / "live/stdout.log"
        deadline = time.monotonic() + 2
        observed = False
        while time.monotonic() < deadline and not future.done():
            if retained.exists() and "ready" in retained.read_text():
                observed = True
                break
            time.sleep(0.01)
        ack.touch()
        assert future.result(timeout=6).exit_code == 0
    assert observed, "short pipe output was buffered until engine exit"
