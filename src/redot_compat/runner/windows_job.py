from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

if os.name == "nt":
    _kernel32: Any = vars(ctypes)["WinDLL"]("kernel32", use_last_error=True)
else:  # pragma: no cover - exercised by the POSIX runner
    _kernel32 = None

_CREATE_NEW_PROCESS_GROUP = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class WindowsJob:
    """Own a Windows process family with kill-on-close semantics."""

    def __init__(self, handle: int) -> None:
        self._handle = handle
        self._closed = False

    @classmethod
    def create(cls) -> WindowsJob:
        _require_windows()
        handle = _kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise _windows_error()
        job = cls(int(handle))
        limits = _ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _kernel32.SetInformationJobObject(
            handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            error = _windows_error()
            job.close()
            raise error
        return job

    def assign(self, process_id: int) -> None:
        _require_windows()
        process_handle = _kernel32.OpenProcess(
            _PROCESS_TERMINATE | _PROCESS_SET_QUOTA,
            False,
            process_id,
        )
        if not process_handle:
            raise _windows_error()
        try:
            if not _kernel32.AssignProcessToJobObject(self._handle, process_handle):
                raise _windows_error()
        finally:
            _kernel32.CloseHandle(process_handle)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._handle and _kernel32 is not None:
            _kernel32.CloseHandle(self._handle)
        self._handle = 0


def launch_in_windows_job(
    command: Sequence[str],
    *,
    working_directory: Path,
    environment: Mapping[str, str],
) -> tuple[subprocess.Popen[bytes], WindowsJob]:
    """Assign a trusted waiting launcher before it starts the requested command."""

    _require_windows()
    helper_environment = dict(os.environ)
    helper_environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        [sys.executable, "-m", "redot_compat.runner._windows_job_child"],
        cwd=working_directory,
        env=helper_environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        creationflags=_CREATE_NEW_PROCESS_GROUP,
    )
    job: WindowsJob | None = None
    try:
        job = WindowsJob.create()
        job.assign(process.pid)
        assert process.stdin is not None
        request = json.dumps(
            {
                "command": list(command),
                "working_directory": str(working_directory),
                "environment": dict(environment),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        process.stdin.write(request + b"\n")
        process.stdin.close()
        return process, job
    except BaseException:
        if job is not None:
            job.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        raise


def _require_windows() -> None:
    if os.name != "nt" or _kernel32 is None:
        raise OSError("Windows Job Objects are available only on Windows")


def _windows_error() -> OSError:
    _require_windows()
    error_factory = vars(ctypes)["WinError"]
    get_last_error = vars(ctypes)["get_last_error"]
    return cast(OSError, error_factory(get_last_error()))


if os.name == "nt":
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    _kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    _kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    _kernel32.SetInformationJobObject.restype = ctypes.c_int
    _kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    _kernel32.OpenProcess.restype = ctypes.c_void_p
    _kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _kernel32.AssignProcessToJobObject.restype = ctypes.c_int
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.CloseHandle.restype = ctypes.c_int
