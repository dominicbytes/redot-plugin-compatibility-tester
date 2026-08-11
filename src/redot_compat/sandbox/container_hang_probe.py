from __future__ import annotations

import subprocess
import sys
import time

from redot_compat.sandbox.heartbeat import start_controller_watchdog


def main() -> None:
    start_controller_watchdog()
    grandchild_code = "import time;time.sleep(300)"
    child_code = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{grandchild_code!r}]);time.sleep(300)"
    )
    subprocess.Popen([sys.executable, "-c", child_code])  # noqa: S603
    sys.stdout.write("REDOT_COMPAT_CONTAINER_READY\n")
    sys.stdout.flush()
    time.sleep(300)


if __name__ == "__main__":
    main()
