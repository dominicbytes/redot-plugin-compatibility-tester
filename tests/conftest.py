from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--integration-redot", metavar="PATH")
    parser.addoption("--integration-godot-control", metavar="PATH")
    parser.addoption("--integration-redot-archive", metavar="PATH")
    parser.addoption("--integration-redot-archive-sha256", metavar="SHA256")
    parser.addoption("--integration-redot-api", metavar="PATH")
    parser.addoption("--integration-godot-control-api", metavar="PATH")
    parser.addoption("--integration-host", action="store_true")
    parser.addoption("--integration-docker", action="store_true")
    parser.addoption("--integration-docker-image", metavar="REPO@SHA256")
