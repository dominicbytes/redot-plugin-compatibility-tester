from __future__ import annotations

import logging
import os
import re
import stat
import subprocess
import threading
import time
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from pydantic import Field

from redot_compat.errors import ConfigurationError
from redot_compat.models.base import ContractModel
from redot_compat.runner.process import ProcessResult, run_process

_DIGEST_IMAGE = re.compile(r"^[^\s@]+@sha256:[a-f0-9]{64}$")
_RUN_ID = re.compile(r"^run-[a-f0-9]{32}$")
_DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024**3
_LOGGER = logging.getLogger(__name__)


class DockerProfile(ContractModel):
    image: str
    cpus: float = Field(default=2.0, gt=0)
    memory: str = "4g"
    pids_limit: int = Field(default=256, gt=0)
    tmpfs_size: str = "1g"
    user: str = "10001:10001"
    seccomp_profile: str | None = None
    max_output_bytes: int = Field(default=_DEFAULT_MAX_OUTPUT_BYTES, gt=0)


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
    for path in (source, output):
        _validate_mount_path(path)
    if heartbeat is not None:
        _validate_mount_path(heartbeat)
    source_path = source.resolve(strict=True)
    output_path = output.resolve(strict=True)
    if not source_path.is_dir() or not output_path.is_dir():
        raise ConfigurationError("Docker source and output mounts must be directories")
    for path in (source_path, output_path):
        _validate_mount_path(path)
    heartbeat_path = heartbeat.resolve(strict=True) if heartbeat is not None else None
    if heartbeat_path is not None:
        _validate_mount_path(heartbeat_path)
        if not heartbeat_path.is_file():
            raise ConfigurationError("Docker heartbeat must be a regular file")
    if not request_path.startswith("/output/") or ".." in PurePosixPath(request_path).parts:
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
        "--memory-swap",
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
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
) -> ProcessResult:
    expected_name = owned_container_name(run_id)
    arguments = list(command)
    if arguments[:2] != ["docker", "run"] or ["--name", expected_name] != _name_pair(arguments):
        raise ConfigurationError("Docker command does not match its owned run identifier")
    if max_output_bytes <= 0:
        raise ConfigurationError("Docker output quota must be positive")
    watchdog = _OutputWatchdog(_output_mount(arguments), run_id, max_output_bytes)
    writer = _HeartbeatWriter(heartbeat.resolve(strict=True))
    try:
        writer.start()
        watchdog.start()
        result = run_process(
            arguments,
            working_directory=working_directory,
            environment=os.environ,
            output_directory=output_directory,
            timeout_seconds=timeout_seconds,
        )
    finally:
        writer.stop()
        watchdog.stop()
        try:
            cleanup_owned_container(run_id)
        except Exception:
            _LOGGER.exception("failed to clean up owned Docker container %s", expected_name)
        try:
            heartbeat.unlink(missing_ok=True)
        except OSError:
            _LOGGER.exception("failed to remove controller heartbeat %s", heartbeat)
    if writer.error is not None:
        raise ConfigurationError(f"controller heartbeat failed: {writer.error}") from writer.error
    if watchdog.error is not None:
        raise ConfigurationError(
            f"output quota watchdog failed: {watchdog.error}"
        ) from watchdog.error
    result.output_quota_exceeded = watchdog.quota_exceeded
    return result


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


def _validate_mount_path(path: Path) -> None:
    if any(character in str(path) for character in (",", '"', "\n", "\r")):
        raise ConfigurationError(
            "Docker bind mount paths cannot contain commas, quotes, or newlines"
        )


def _output_mount(command: list[str]) -> Path:
    for index, argument in enumerate(command[:-1]):
        if argument != "--mount":
            continue
        fields = dict(
            field.split("=", 1) for field in command[index + 1].split(",") if "=" in field
        )
        if (
            fields.get("target") == "/output"
            and fields.get("type") == "bind"
            and "source" in fields
        ):
            return Path(fields["source"]).resolve(strict=True)
    raise ConfigurationError("Docker command is missing its output bind mount")


def output_directory_exceeds_limit(directory: Path, *, max_bytes: int) -> bool:
    """Count regular file bytes, without following worker-created links or junctions."""
    total = 0
    pending = [directory]
    while pending:
        current = pending.pop()
        try:
            if not stat.S_ISDIR(current.lstat().st_mode) or current.is_junction():
                continue
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        metadata = entry.stat(follow_symlinks=False)
                        if stat.S_ISDIR(metadata.st_mode):
                            if not Path(entry.path).is_junction():
                                pending.append(Path(entry.path))
                        elif stat.S_ISREG(metadata.st_mode):
                            total += metadata.st_size
                            if total > max_bytes:
                                return True
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            continue
    return False


class _OutputWatchdog:
    def __init__(self, directory: Path, run_id: str, max_bytes: int) -> None:
        self._directory = directory
        self._run_id = run_id
        self._max_bytes = max_bytes
        self.quota_exceeded = False
        self.error: OSError | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.ident is not None:
            self._thread.join(timeout=20)

    def _run(self) -> None:
        while not self._stop.wait(2.0):
            try:
                self.quota_exceeded = output_directory_exceeds_limit(
                    self._directory, max_bytes=self._max_bytes
                )
            except OSError as exc:
                self.error = exc
            if self.quota_exceeded or self.error is not None:
                try:
                    cleanup_owned_container(self._run_id)
                except Exception:
                    _LOGGER.exception("failed to stop Docker container after output quota check")
                return


class _HeartbeatWriter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.error: OSError | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.ident is not None:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        sequence = 1
        while not self._stop.wait(0.25):
            try:
                self._path.write_text(f"{sequence}\n", encoding="utf-8", newline="\n")
            except OSError as exc:
                self.error = exc
                return
            sequence += 1
