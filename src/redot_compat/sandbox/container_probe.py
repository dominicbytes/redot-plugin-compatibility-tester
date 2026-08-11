from __future__ import annotations

import argparse
import json
import os
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast


def main() -> None:
    parser = argparse.ArgumentParser(description="Fixed Docker containment probe")
    parser.add_argument("--output", type=Path, default=Path("/output/containment-probe.json"))
    args = parser.parse_args()
    result = _probe()
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    raise SystemExit(0 if result["passed"] else 1)


def _probe() -> dict[str, Any]:
    uid, gid = _numeric_identity()
    root_write_blocked = _write_blocked(Path("/redot-compat-root-write"))
    input_write_blocked = _write_blocked(Path("/input/redot-compat-input-write"))
    home_write_succeeded = _write_succeeded(Path.home() / ".cache/redot-compat/probe")
    output_write_succeeded = _write_succeeded(Path("/output/redot-compat-output-write"))
    network_blocked, network_error = _network_blocked()
    status = _key_values(Path("/proc/self/status"))
    limits = {
        "pids_max": _read(Path("/sys/fs/cgroup/pids.max")),
        "pids_current": _read(Path("/sys/fs/cgroup/pids.current")),
        "memory_max": _read(Path("/sys/fs/cgroup/memory.max")),
        "cpu_max": _read(Path("/sys/fs/cgroup/cpu.max")),
    }
    checks = {
        "uid_gid": uid == 10001 and gid == 10001,
        "root_write_blocked": root_write_blocked,
        "input_write_blocked": input_write_blocked,
        "home_write_succeeded": home_write_succeeded,
        "output_write_succeeded": output_write_succeeded,
        "network_blocked": network_blocked,
        "docker_socket_absent": not Path("/var/run/docker.sock").exists(),
        "no_new_privileges": status.get("NoNewPrivs") == "1",
        "no_effective_capabilities": status.get("CapEff") == "0000000000000000",
        "seccomp_filter": status.get("Seccomp") == "2",
        "pids_limit": limits["pids_max"] == "256",
        "memory_limit": limits["memory_max"] == str(4 * 1024 * 1024 * 1024),
        "cpu_limit": limits["cpu_max"] == "200000 100000",
    }
    return {
        "schema_version": 1,
        "uid": uid,
        "gid": gid,
        "home": str(Path.home()),
        "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
        "xdg_cache_home": os.environ.get("XDG_CACHE_HOME"),
        "network_error": network_error,
        "status": {key: status.get(key) for key in ("CapEff", "NoNewPrivs", "Seccomp")},
        "cgroup": limits,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _numeric_identity() -> tuple[int, int]:
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return -1, -1
    return cast(Callable[[], int], getuid)(), cast(Callable[[], int], getgid)()


def _write_blocked(path: Path) -> bool:
    try:
        path.write_text("unexpected\n", encoding="utf-8")
    except OSError:
        return True
    path.unlink(missing_ok=True)
    return False


def _write_succeeded(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")
        return path.read_text(encoding="utf-8") == "ok\n"
    except OSError:
        return False


def _network_blocked() -> tuple[bool, str]:
    try:
        connection = socket.create_connection(("1.1.1.1", 53), timeout=1.0)
    except OSError as exc:
        return True, f"{type(exc).__name__}: {exc}"
    connection.close()
    return False, "connection unexpectedly succeeded"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = _read(path)
    if text is None:
        return values
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key] = value.strip()
    return values


if __name__ == "__main__":
    main()
