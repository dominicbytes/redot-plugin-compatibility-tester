from __future__ import annotations

import pytest
from pydantic import ValidationError

from redot_compat.models.batch import BatchItem, BatchManifest


def test_batch_manifest_bounds_concurrency_and_requires_unique_ids() -> None:
    manifest = BatchManifest(
        concurrency=2,
        items=[BatchItem(id="one", source="./one"), BatchItem(id="two", source="./two")],
    )

    assert manifest.concurrency == 2

    with pytest.raises(ValidationError):
        BatchManifest(
            concurrency=9,
            items=[BatchItem(id="same", source="./one"), BatchItem(id="same", source="./two")],
        )
