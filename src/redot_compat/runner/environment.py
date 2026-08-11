from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

_PASSTHROUGH = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "TZ",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMDATA",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "SYSTEMDRIVE",
)


def build_isolated_environment(
    run_root: Path, *, inherited: Mapping[str, str] | None = None
) -> dict[str, str]:
    root = run_root.resolve()
    source = os.environ if inherited is None else inherited
    environment = {key: source[key] for key in _PASSTHROUGH if key in source}
    locations = {
        "HOME": root / "home",
        "USERPROFILE": root / "home",
        "APPDATA": root / "config/roaming",
        "LOCALAPPDATA": root / "config/local",
        "XDG_CONFIG_HOME": root / "config/xdg",
        "XDG_CACHE_HOME": root / "cache",
        "XDG_DATA_HOME": root / "data",
        "TMP": root / "temp",
        "TEMP": root / "temp",
        "TMPDIR": root / "temp",
    }
    for path in sorted(set(locations.values())):
        path.mkdir(parents=True, exist_ok=True)
    environment.update({key: str(value) for key, value in locations.items()})
    environment["REDOT_COMPAT_ISOLATED"] = "1"
    return environment
