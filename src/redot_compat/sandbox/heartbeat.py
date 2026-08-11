from __future__ import annotations

import os
import threading
import time
from pathlib import Path


def start_controller_watchdog() -> None:
    configured = os.environ.get("REDOT_COMPAT_HEARTBEAT_PATH")
    if not configured:
        return
    timeout = float(os.environ.get("REDOT_COMPAT_HEARTBEAT_TIMEOUT_SECONDS", "5"))
    if timeout < 2 or timeout > 30:
        raise ValueError("controller heartbeat timeout must be between 2 and 30 seconds")
    path = Path(configured).resolve(strict=True)
    thread = threading.Thread(target=_watch, args=(path, timeout), daemon=True)
    thread.start()


def _watch(path: Path, timeout: float) -> None:
    last_value: str | None = None
    last_change = time.monotonic()
    while True:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            value = None
        if value and value != last_value:
            last_value = value
            last_change = time.monotonic()
        elif time.monotonic() - last_change > timeout:
            os._exit(124)
        time.sleep(0.25)
