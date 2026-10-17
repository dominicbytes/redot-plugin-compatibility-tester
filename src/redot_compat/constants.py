from __future__ import annotations

from enum import IntEnum
from importlib import metadata

APP_NAME = "redot-compat"
PACKAGE_NAME = "redot-plugin-compatibility-tester"


def _package_version() -> str:
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:  # pragma: no cover - source tree without install
        return "0.0.0+unknown"


VERSION = _package_version()
RESULT_SCHEMA_VERSION = "1.1.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
BATCH_SCHEMA_VERSION = "1.1.0"
HARNESS_EVENT_SCHEMA_VERSION = 2
BASELINE_VERSION = "4.5.2"
HARNESS_EVENT_PREFIX = "REDOT_COMPAT_EVENT "


class ExitCode(IntEnum):
    """Stable process-level result classes.

    Detailed compatibility state always lives in ``result.json``.
    """

    SUCCESS = 0
    USAGE_ERROR = 2
    BASELINE_POLICY_SKIP = 10
    PORT_REQUIRED = 20
    INVALID_OR_UPSTREAM = 30
    INCONCLUSIVE = 40
    INTERNAL_ERROR = 50
