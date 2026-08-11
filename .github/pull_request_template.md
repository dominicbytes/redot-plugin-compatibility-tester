## Summary

Describe the compatibility behavior or repository preparation changed here.

## Verification

- [ ] `uv sync --frozen`
- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy src`
- [ ] `uv run pytest -q`
- [ ] `uv run redot-compat schema export --check`

## Security and evidence

- [ ] No untrusted plugin was executed outside an eligible backend.
- [ ] Public schema/oracle changes include an explicit decision and fixture hash update.
- [ ] Logs, reports, fixtures, and reproduction commands contain no credentials.
