from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import psutil
import pytest

from redot_compat.runner.environment import build_isolated_environment
from redot_compat.runner.process import run_process
from redot_compat.sandbox.docker_linux import (
    DockerProfile,
    build_docker_command,
    docker_daemon_available,
    prepare_heartbeat,
)


def _enabled(request: pytest.FixtureRequest, option: str) -> bool:
    return bool(request.config.getoption(option))


def _wait_processes_gone(pids: list[int], timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not any(psutil.pid_exists(pid) for pid in pids):
            return True
        time.sleep(0.05)
    return not any(psutil.pid_exists(pid) for pid in pids)


@pytest.mark.gauntlet
@pytest.mark.integration
@pytest.mark.skipif(os.name != "nt", reason="canonical host profile is Windows")
def test_g03_windows_job_containment(request: pytest.FixtureRequest, tmp_path: Path) -> None:
    if not _enabled(request, "--integration-host"):
        pytest.skip("G-03 Windows profile requires --integration-host")

    timeout_pid_file = tmp_path / "timeout-pids.txt"
    grandchild_code = "import time; time.sleep(300)"
    child_code = (
        "import os,subprocess,sys,time;"
        f"child=subprocess.Popen([sys.executable,'-c',{grandchild_code!r}]);"
        f"open({str(timeout_pid_file)!r},'w',encoding='utf-8').write("
        "f'{os.getpid()} {child.pid}');time.sleep(300)"
    )
    timed_out = run_process(
        [sys.executable, "-c", child_code],
        working_directory=tmp_path,
        environment=build_isolated_environment(tmp_path / "timeout-state"),
        output_directory=tmp_path / "timeout-logs",
        timeout_seconds=1,
    )
    timeout_pids = [int(value) for value in timeout_pid_file.read_text(encoding="utf-8").split()]
    assert timed_out.ownership == "windows_job"
    assert timed_out.timed_out is True
    assert _wait_processes_gone(timeout_pids, 5)
    time.sleep(0.1)
    assert _wait_processes_gone(timeout_pids, 0)

    controller_pid_file = tmp_path / "controller-pids.txt"
    controller_logs = tmp_path / "controller-logs"
    controller_child_code = (
        "import os,subprocess,sys,time;"
        f"child=subprocess.Popen([sys.executable,'-c',{grandchild_code!r}]);"
        f"open({str(controller_pid_file)!r},'w',encoding='utf-8').write("
        "f'{os.getpid()} {child.pid}');time.sleep(300)"
    )
    controller_code = (
        "import sys;from pathlib import Path;"
        "from redot_compat.runner.environment import build_isolated_environment;"
        "from redot_compat.runner.process import run_process;"
        f"root=Path({str(tmp_path)!r});"
        f"run_process([sys.executable,'-c',{controller_child_code!r}],"
        "working_directory=root,environment=build_isolated_environment("
        "root/'controller-state'),"
        f"output_directory=Path({str(controller_logs)!r}),timeout_seconds=300)"
    )
    controller = subprocess.Popen(
        [sys.executable, "-c", controller_code],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 5
    while not controller_pid_file.exists() and time.monotonic() < deadline:
        if controller.poll() is not None:
            stderr = controller.stderr.read().decode(errors="replace") if controller.stderr else ""
            pytest.fail(f"controller exited before spawning its fixture: {stderr}")
        time.sleep(0.05)
    assert controller_pid_file.exists()
    controller_pids = [
        int(value) for value in controller_pid_file.read_text(encoding="utf-8").split()
    ]
    controller.kill()
    controller.wait(timeout=5)
    assert _wait_processes_gone(controller_pids, 5)
    time.sleep(0.1)
    assert _wait_processes_gone(controller_pids, 0)

    state = tmp_path / "environment-state"
    environment = build_isolated_environment(state)
    state_script = (
        "import os;from pathlib import Path;"
        "[(Path(os.environ[key])/('probe-'+key.lower())).write_text('ok',encoding='utf-8') "
        "for key in ('HOME','TEMP','APPDATA')]"
    )
    state_result = run_process(
        [sys.executable, "-c", state_script],
        working_directory=tmp_path,
        environment=environment,
        output_directory=tmp_path / "state-logs",
        timeout_seconds=5,
    )
    assert state_result.exit_code == 0
    assert all(Path(environment[key]).is_relative_to(state) for key in ("HOME", "TEMP", "APPDATA"))
    assert all(
        (Path(environment[key]) / f"probe-{key.lower()}").is_file()
        for key in ("HOME", "TEMP", "APPDATA")
    )

    capture = {
        "gate": "G-03",
        "profile": "windows_x86_64_trusted_host",
        "ownership": timed_out.ownership,
        "timeout_seconds": 1,
        "timeout_descendants": timeout_pids,
        "controller_exit_descendants": controller_pids,
        "descendants_gone_within_seconds": 5,
        "second_probe_clean": True,
        "isolated_state_root": str(state),
        "filesystem_sandbox": False,
        "trusted_source_required": True,
    }
    (tmp_path / "G-03-host-capture.json").write_text(
        json.dumps(capture, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _docker_option(request: pytest.FixtureRequest) -> str:
    value = request.config.getoption("--integration-docker-image")
    if not value:
        pytest.skip("G-03 Docker profile requires --integration-docker-image")
    return str(value)


def _probe_command(command: list[str], image: str) -> list[str]:
    image_index = command.index(image)
    return [
        *command[:image_index],
        "--entrypoint",
        "python",
        image,
        "-m",
        "redot_compat.sandbox.container_probe",
        "--output",
        "/output/containment-probe.json",
    ]


def _container_name(run_id: str) -> str:
    return f"redot-compat-{run_id.removeprefix('run-')[:12]}"


def _docker_run(command: list[str], *, timeout: float = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )


def _wait_container_absent(name: str, timeout_seconds: float = 10) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        inspected = _docker_run(["docker", "inspect", name], timeout=5)
        if inspected.returncode != 0:
            return True
        time.sleep(0.1)
    return _docker_run(["docker", "inspect", name], timeout=5).returncode != 0


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g03_hardened_docker_containment(request: pytest.FixtureRequest, tmp_path: Path) -> None:
    if not _enabled(request, "--integration-docker"):
        pytest.skip("G-03 Docker profile requires --integration-docker")
    image = _docker_option(request)
    available, detail = docker_daemon_available(timeout_seconds=10)
    assert available, detail
    profile = DockerProfile(image=image)
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    run_id = f"run-{uuid.uuid4().hex}"
    command = build_docker_command(
        profile,
        run_id=run_id,
        source=source,
        output=output,
        request_path="/output/request.json",
    )
    completed = _docker_run(_probe_command(command, image))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads((output / "containment-probe.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert all(payload["checks"].values())
    assert _wait_container_absent(_container_name(run_id))

    teardown_run_id = f"run-{uuid.uuid4().hex}"
    teardown_command = build_docker_command(
        profile,
        run_id=teardown_run_id,
        source=source,
        output=output,
        request_path="/output/request.json",
    )
    teardown_command.insert(2, "--detach")
    image_index = teardown_command.index(image)
    grandchild_code = "import time;time.sleep(300)"
    child_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{grandchild_code!r}]);time.sleep(300)"
    )
    parent_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
        "print('REDOT_COMPAT_CONTAINER_READY',flush=True);time.sleep(300)"
    )
    teardown_command = [
        *teardown_command[:image_index],
        "--entrypoint",
        "python",
        image,
        "-c",
        parent_code,
    ]
    detached = _docker_run(teardown_command)
    assert detached.returncode == 0, detached.stdout + detached.stderr
    name = _container_name(teardown_run_id)
    deadline = time.monotonic() + 5
    logs = ""
    while "REDOT_COMPAT_CONTAINER_READY" not in logs and time.monotonic() < deadline:
        logs_result = _docker_run(["docker", "logs", name], timeout=5)
        logs = logs_result.stdout + logs_result.stderr
        time.sleep(0.1)
    assert "REDOT_COMPAT_CONTAINER_READY" in logs
    top = _docker_run(["docker", "top", name], timeout=5)
    assert top.returncode == 0
    assert len([line for line in top.stdout.splitlines() if line.strip()]) >= 4
    killed = _docker_run(["docker", "kill", name], timeout=10)
    assert killed.returncode == 0, killed.stdout + killed.stderr
    assert _wait_container_absent(name, 10)

    controller_run_id = f"run-{uuid.uuid4().hex}"
    heartbeat = prepare_heartbeat(tmp_path / "controller-heartbeat")
    controller_command = build_docker_command(
        profile,
        run_id=controller_run_id,
        source=source,
        output=output,
        request_path="/output/request.json",
        heartbeat=heartbeat,
    )
    image_index = controller_command.index(image)
    controller_command = [
        *controller_command[:image_index],
        "--entrypoint",
        "python",
        image,
        "-m",
        "redot_compat.sandbox.container_hang_probe",
    ]
    controller_name = _container_name(controller_run_id)
    wrapper_code = (
        "import json,sys;from pathlib import Path;"
        "from redot_compat.sandbox.docker_linux import run_docker_command;"
        "run_docker_command(json.loads(sys.argv[1]),run_id=sys.argv[2],"
        "heartbeat=Path(sys.argv[3]),working_directory=Path(sys.argv[4]),"
        "output_directory=Path(sys.argv[5]),timeout_seconds=300)"
    )
    docker_controller = subprocess.Popen(
        [
            sys.executable,
            "-c",
            wrapper_code,
            json.dumps(controller_command),
            controller_run_id,
            str(heartbeat),
            str(tmp_path),
            str(tmp_path / "controller-docker-logs"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        controller_logs = ""
        while "REDOT_COMPAT_CONTAINER_READY" not in controller_logs and time.monotonic() < deadline:
            logs_result = _docker_run(["docker", "logs", controller_name], timeout=5)
            controller_logs = logs_result.stdout + logs_result.stderr
            if docker_controller.poll() is not None:
                pytest.fail("Docker controller exited before the hang probe became ready")
            time.sleep(0.1)
        assert "REDOT_COMPAT_CONTAINER_READY" in controller_logs
        docker_controller.kill()
        docker_controller.wait(timeout=5)
        assert _wait_container_absent(controller_name, 10)
    finally:
        if docker_controller.poll() is None:
            docker_controller.kill()
            docker_controller.wait(timeout=5)
        if not _wait_container_absent(controller_name, 0):
            _docker_run(["docker", "rm", "--force", controller_name], timeout=10)
        heartbeat.unlink(missing_ok=True)

    inspect = _docker_run(["docker", "image", "inspect", image], timeout=20)
    assert inspect.returncode == 0, inspect.stderr
    image_data: list[dict[str, Any]] = json.loads(inspect.stdout)
    config = image_data[0]["Config"]
    assert config["User"] == "10001:10001"
    assert config["Entrypoint"] == ["python", "-m", "redot_compat.worker"]
    capture = {
        "gate": "G-03",
        "profile": profile.model_dump(mode="json"),
        "daemon": detail,
        "image_id": image_data[0]["Id"],
        "repo_digests": image_data[0].get("RepoDigests", []),
        "probe": payload,
        "teardown_process_rows": len([line for line in top.stdout.splitlines() if line.strip()]),
        "container_removed_within_seconds": 10,
        "controller_disconnect_removed_within_seconds": 10,
    }
    (tmp_path / "G-03-docker-capture.json").write_text(
        json.dumps(capture, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
