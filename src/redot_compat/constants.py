from __future__ import annotations

from enum import IntEnum

APP_NAME = "redot-compat"
PACKAGE_NAME = "redot-plugin-compatibility-tester"
VERSION = "0.1.0"
RESULT_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
BATCH_SCHEMA_VERSION = "1.0.0"
HARNESS_EVENT_SCHEMA_VERSION = 1
BASELINE_VERSION = "4.5.2"
HARNESS_EVENT_PREFIX = "REDOT_COMPAT_EVENT "


class ExitCode(IntEnum):
    """Stable process-level result classes.

    Detailed compatibility state always lives in ``result.json``.
    """

    SUCCESS = 0
    BASELINE_POLICY_SKIP = 10
    PORT_REQUIRED = 20
    INVALID_OR_UPSTREAM = 30
    INCONCLUSIVE = 40
    INTERNAL_ERROR = 50
