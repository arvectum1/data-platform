# Arvectum Data Platform

Domain-neutral data acquisition and extraction foundation for Arvectum products.

## Current baseline

`DP-ENGINE-001` introduces the first reusable extraction-engine contract:

- providers propose field candidates instead of writing domain values directly;
- every candidate carries confidence and evidence;
- deterministic resolution auto-selects only sufficiently strong, well-separated candidates;
- ambiguous/weak results require human confirmation;
- reviewers may only confirm an existing candidate or reject it — manual value entry is intentionally absent from the engine API;
- provider failures are isolated and reported without discarding successful candidates from other providers.

The engine is intentionally domain-neutral. Discount, doors, procurement, catalog and future data domains should define their own `FieldSpec` sets and candidate providers outside the core.

See [`docs/tasks/DP-ENGINE-001.md`](docs/tasks/DP-ENGINE-001.md).

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```
