from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

import psutil
from pydantic import Field

from redot_compat.models.base import ContractModel
from redot_compat.runner.redaction import REDACTED, redact_args, redact_environment, redact_text
from redot_compat.runner.windows_job import WindowsJob, launch_in_windows_job


class ProcessResult(ContractModel):
    command: list[str]
    working_directory: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    exit_code: int | None
    timed_out: bool
    stdout_path: str
    stderr_path: str
    combined_log_path: str
    ownership: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    combined_truncated: bool = False


class _BoundedWriter:
    def __init__(self, path: Path, limit: int) -> None:
        self.path = path
        self.limit = limit
        self.written = 0
        self.truncated = False
        self._stream = path.open("xb")
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        with self._lock:
            remaining = self.limit - self.written
            if remaining <= 0:
                self.truncated = True
                return
            chunk = data[:remaining]
            self._stream.write(chunk)
            self._stream.flush()
            self.written += len(chunk)
            if len(chunk) != len(data):
                self.truncated = True

    def close(self) -> None:
        self._stream.close()


def run_process(
    command: Sequence[str],
    *,
    working_directory: Path,
    environment: Mapping[str, str],
    output_directory: Path,
    timeout_seconds: float,
    max_log_bytes: int = 4 * 1024 * 1024,
) -> ProcessResult:
    arguments = [str(item) for item in command]
    if not arguments or any("\0" in item for item in arguments):
        raise ValueError("command must be a non-empty NUL-free argument array")
    if timeout_seconds <= 0 or max_log_bytes <= 0:
        raise ValueError("timeout and log limit must be positive")
    cwd = working_directory.resolve(strict=True)
    logs = output_directory.resolve()
    logs.mkdir(parents=True, exist_ok=False)
    stdout_writer = _BoundedWriter(logs / "stdout.log", max_log_bytes)
    stderr_writer = _BoundedWriter(logs / "stderr.log", max_log_bytes)
    combined_writer = _BoundedWriter(logs / "combined.log", max_log_bytes)
    redacted_environment = redact_environment(environment)
    secrets = tuple(
        environment[key] for key, value in redacted_environment.items() if value == REDACTED
    )
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    windows_job: WindowsJob | None = None
    timed_out = False
    try:
        if os.name == "nt":
            process, windows_job = launch_in_windows_job(
                arguments,
                working_directory=cwd,
                environment=environment,
            )
        else:
            process = subprocess.Popen(  # noqa: S603 - gated argument array, never a shell
                arguments,
                cwd=cwd,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
            )
        assert process.stdout is not None
        assert process.stderr is not None
        threads = [
            threading.Thread(
                target=_drain,
                args=(process.stdout, stdout_writer, combined_writer, "stdout", secrets),
                daemon=True,
            ),
            threading.Thread(
                target=_drain,
                args=(process.stderr, stderr_writer, combined_writer, "stderr", secrets),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            if windows_job is not None:
                windows_job.close()
            _terminate_owned_tree(process)
        for thread in threads:
            thread.join(timeout=5)
        if process.poll() is None:
            _terminate_owned_tree(process)
    finally:
        if windows_job is not None:
            windows_job.close()
        stdout_writer.close()
        stderr_writer.close()
        combined_writer.close()
    finished_at = datetime.now(UTC)
    duration_ms = max(0, round((time.monotonic() - started_clock) * 1000))
    return ProcessResult(
        command=redact_args(arguments),
        working_directory=str(cwd),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        exit_code=process.returncode if process is not None else None,
        timed_out=timed_out,
        stdout_path=str(logs / "stdout.log"),
        stderr_path=str(logs / "stderr.log"),
        combined_log_path=str(logs / "combined.log"),
        ownership="windows_job" if os.name == "nt" else "posix_process_group",
        stdout_truncated=stdout_writer.truncated,
        stderr_truncated=stderr_writer.truncated,
        combined_truncated=combined_writer.truncated,
    )


def _drain(
    stream: BinaryIO,
    writer: _BoundedWriter,
    combined: _BoundedWriter,
    label: str,
    secrets: tuple[str, ...],
) -> None:
    while chunk := stream.read(4096):
        text = chunk.decode("utf-8", errors="replace")
        safe = redact_text(text, secrets=secrets).encode("utf-8")
        writer.write(safe)
        timestamp = datetime.now(UTC).isoformat(timespec="milliseconds")
        combined.write(f"{timestamp} [{label}] ".encode() + safe)


def _terminate_owned_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name != "nt":
        try:
            os.kill(-process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        root = psutil.Process(process.pid)
        owned = root.children(recursive=True)
        for child in owned:
            child.terminate()
        root.terminate()
        _, alive = psutil.wait_procs([*owned, root], timeout=1)
        for item in alive:
            item.kill()
        psutil.wait_procs(alive, timeout=1)
    except psutil.Error:
        process.kill()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
