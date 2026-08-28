# Arvectum Data Platform

Domain-neutral data acquisition and extraction foundation for Arvectum products.

## Current baseline

`DP-ENGINE-001` established the governed extraction contract:

- providers propose field candidates instead of writing domain values directly;
- every candidate carries confidence and evidence;
- deterministic resolution auto-selects only sufficiently strong, well-separated candidates;
- ambiguous/weak results require human confirmation;
- reviewers may only confirm an existing candidate or reject it — manual value entry is intentionally absent from the engine API;
- provider failures are isolated and reported without discarding successful candidates from other providers.

`DP-ENGINE-002` adds automatic semantic candidate discovery without per-site selectors:

- JSON-LD recursive discovery;
- HTML meta and `itemprop` discovery;
- semantic DOM label/value discovery (`dt/dd`, `th/td`, semantic attributes);
- plain-text `label: value` fallback;
- `FieldSpec.aliases` for domain vocabulary rather than CSS/XPath configuration;
- corroborating signals for the same value are merged into one evidence-rich candidate;
- conflicting values remain separate candidates and therefore flow into the existing confirmation gate.

The engine remains domain-neutral. Discount, doors, procurement, catalog and future domains define `FieldSpec` keys/aliases; operators do not inspect DOM nodes or maintain selectors.

See [`docs/tasks/DP-ENGINE-001.md`](docs/tasks/DP-ENGINE-001.md) and [`docs/tasks/DP-ENGINE-002.md`](docs/tasks/DP-ENGINE-002.md).

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```
