from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

_MAX_REQUEST_BYTES = 16 * 1024 * 1024


def main() -> None:
    payload = sys.stdin.buffer.readline(_MAX_REQUEST_BYTES + 1)
    if not payload or len(payload) > _MAX_REQUEST_BYTES:
        raise SystemExit(125)
    try:
        request: Any = json.loads(payload)
        command = request["command"]
        working_directory = request["working_directory"]
        environment = request["environment"]
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(item, str) and "\0" not in item for item in command)
            or not isinstance(working_directory, str)
            or not isinstance(environment, dict)
            or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in environment.items()
            )
        ):
            raise ValueError("invalid Windows Job launcher request")
        process = subprocess.Popen(  # noqa: S603 - validated argument array, no shell
            command,
            cwd=working_directory,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            shell=False,
        )
        return_code = process.wait()
    except (KeyError, OSError, TypeError, ValueError):
        raise SystemExit(125) from None
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
