from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections.abc import Sequence
from pathlib import Path

from pydantic import Field

from redot_compat.errors import ConfigurationError
from redot_compat.models.base import ContractModel
from redot_compat.runner.process import ProcessResult, run_process

_DIGEST_IMAGE = re.compile(r"^[^\s@]+@sha256:[a-f0-9]{64}$")
_RUN_ID = re.compile(r"^run-[a-f0-9]{32}$")


class DockerProfile(ContractModel):
    image: str
    cpus: float = Field(default=2.0, gt=0)
    memory: str = "4g"
    pids_limit: int = Field(default=256, gt=0)
    tmpfs_size: str = "1g"
    user: str = "10001:10001"
    seccomp_profile: str | None = None


def docker_daemon_available(*, timeout_seconds: float = 5.0) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    detail = (completed.stdout or completed.stderr).strip()
    return completed.returncode == 0, detail


def build_docker_command(
    profile: DockerProfile,
    *,
    run_id: str,
    source: Path,
    output: Path,
    request_path: str,
    heartbeat: Path | None = None,
) -> list[str]:
    if not _DIGEST_IMAGE.fullmatch(profile.image):
        raise ConfigurationError("Docker worker image must be digest-pinned")
    if not _RUN_ID.fullmatch(run_id):
        raise ConfigurationError("invalid owned run identifier")
    source_path = source.resolve(strict=True)
    output_path = output.resolve(strict=True)
    if not source_path.is_dir() or not output_path.is_dir():
        raise ConfigurationError("Docker source and output mounts must be directories")
    if any("," in str(path) for path in (source_path, output_path)):
        raise ConfigurationError("Docker bind mount paths cannot contain commas")
    heartbeat_path = heartbeat.resolve(strict=True) if heartbeat is not None else None
    if heartbeat_path is not None and (not heartbeat_path.is_file() or "," in str(heartbeat_path)):
        raise ConfigurationError("Docker heartbeat must be a regular path without commas")
    if not request_path.startswith("/output/") or ".." in Path(request_path).parts:
        raise ConfigurationError("worker request must be under /output")
    command = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--pull",
        "never",
        "--name",
        f"redot-compat-{run_id.removeprefix('run-')[:12]}",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(profile.pids_limit),
        "--cpus",
        str(profile.cpus),
        "--memory",
        profile.memory,
        "--user",
        profile.user,
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,nodev,size={profile.tmpfs_size}",  # noqa: S108
        "--tmpfs",
        f"/home/worker:rw,noexec,nosuid,nodev,size={profile.tmpfs_size}",
        "--env",
        "HOME=/home/worker",
        "--env",
        "XDG_CONFIG_HOME=/home/worker/.config",
        "--env",
        "XDG_CACHE_HOME=/home/worker/.cache",
        "--mount",
        f"type=bind,source={source_path},target=/input,readonly",
        "--mount",
        f"type=bind,source={output_path},target=/output",
    ]
    if heartbeat_path is not None:
        command.extend(
            [
                "--env",
                "REDOT_COMPAT_HEARTBEAT_PATH=/run/redot-compat-heartbeat",
                "--env",
                "REDOT_COMPAT_HEARTBEAT_TIMEOUT_SECONDS=5",
                "--mount",
                (f"type=bind,source={heartbeat_path},target=/run/redot-compat-heartbeat,readonly"),
            ]
        )
    if profile.seccomp_profile:
        command.extend(["--security-opt", f"seccomp={profile.seccomp_profile}"])
    command.extend([profile.image, "--request", request_path])
    return command


def prepare_heartbeat(path: Path) -> Path:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text("0\n", encoding="utf-8", newline="\n")
    return resolved


def run_docker_command(
    command: Sequence[str],
    *,
    run_id: str,
    heartbeat: Path,
    working_directory: Path,
    output_directory: Path,
    timeout_seconds: float,
) -> ProcessResult:
    expected_name = owned_container_name(run_id)
    arguments = list(command)
    if arguments[:2] != ["docker", "run"] or ["--name", expected_name] != _name_pair(arguments):
        raise ConfigurationError("Docker command does not match its owned run identifier")
    writer = _HeartbeatWriter(heartbeat.resolve(strict=True))
    writer.start()
    try:
        return run_process(
            arguments,
            working_directory=working_directory,
            environment=os.environ,
            output_directory=output_directory,
            timeout_seconds=timeout_seconds,
        )
    finally:
        writer.stop()
        cleanup_owned_container(run_id)
        heartbeat.unlink(missing_ok=True)


def owned_container_name(run_id: str) -> str:
    if not _RUN_ID.fullmatch(run_id):
        raise ConfigurationError("invalid owned run identifier")
    return f"redot-compat-{run_id.removeprefix('run-')[:12]}"


def cleanup_owned_container(run_id: str, *, timeout_seconds: float = 10.0) -> None:
    name = owned_container_name(run_id)
    subprocess.run(  # noqa: S603 - exact owned name, fixed Docker operation
        ["docker", "rm", "--force", name],  # noqa: S607
        check=False,
        capture_output=True,
        timeout=min(timeout_seconds, 10.0),
        shell=False,
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        inspected = subprocess.run(  # noqa: S603 - read-only exact owned-name check
            ["docker", "inspect", name],  # noqa: S607
            check=False,
            capture_output=True,
            timeout=5,
            shell=False,
        )
        if inspected.returncode != 0:
            return
        time.sleep(0.1)
    raise ConfigurationError(f"owned Docker container did not disappear: {name}")


def _name_pair(command: list[str]) -> list[str]:
    try:
        index = command.index("--name")
        return command[index : index + 2]
    except ValueError:
        return []


class _HeartbeatWriter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        sequence = 1
        while not self._stop.wait(0.25):
            self._path.write_text(f"{sequence}\n", encoding="utf-8", newline="\n")
            sequence += 1
