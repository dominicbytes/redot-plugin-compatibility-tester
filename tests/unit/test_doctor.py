from __future__ import annotations

from pathlib import Path

import pytest

from redot_compat.engines.doctor import doctor_engine
from redot_compat.errors import EngineError


def test_doctor_rejects_missing_binary(tmp_path: Path) -> None:
    with pytest.raises(EngineError, match="does not exist"):
        doctor_engine(tmp_path / "missing", product_hint="redot", timeout_seconds=1)
