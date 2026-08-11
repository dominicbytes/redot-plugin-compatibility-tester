# Release evidence

The repository is currently an alpha (`0.1.0`), not a version 1.0 release candidate. G-02, G-03, G-05, and the optional Mono capability are green locally, but the remaining phase/platform matrix still prevents a 1.0 claim.

Generate quality, schema, wheel/sdist, clean-install, dependency/license, SBOM, checksum, and vulnerability artifacts from a committed source identity using the commands below before publishing.

```console
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run redot-compat schema export --check
uv run pip-audit --cache-dir .artifacts/pip-audit-cache --format json --output release/vulnerability-report.json
uv run python -m build
uv run python scripts/release_audit.py --output release
```

Publishing remains a separate, explicitly authorized action. The GitHub release workflow only uploads dry-run artifacts and has `contents: read` permission.
