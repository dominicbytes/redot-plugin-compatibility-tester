from __future__ import annotations

from pathlib import Path

from redot_compat.runner.environment import build_isolated_environment


def test_isolated_environment_drops_secrets_and_keeps_state_inside_run(tmp_path: Path) -> None:
    environment = build_isolated_environment(
        tmp_path,
        inherited={
            "PATH": "safe-path",
            "PROGRAMFILES": "C:/Program Files",
            "PROGRAMFILES(X86)": "C:/Program Files (x86)",
            "PROGRAMDATA": "C:/ProgramData",
            "SYSTEMDRIVE": "C:",
            "GITHUB_TOKEN": "secret-value",
            "AWS_SECRET_ACCESS_KEY": "also-secret",
            "CUSTOM": "not-allowed",
        },
    )

    assert environment["PATH"] == "safe-path"
    assert environment["PROGRAMFILES"] == "C:/Program Files"
    assert environment["PROGRAMFILES(X86)"] == "C:/Program Files (x86)"
    assert environment["PROGRAMDATA"] == "C:/ProgramData"
    assert environment["SYSTEMDRIVE"] == "C:"
    assert "GITHUB_TOKEN" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "CUSTOM" not in environment
    for key in (
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "TMP",
        "TEMP",
        "TMPDIR",
    ):
        assert Path(environment[key]).is_relative_to(tmp_path)
