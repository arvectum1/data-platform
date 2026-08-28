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

`DP-ENGINE-003` adds URL acquisition and automatic rendered-page fallback:

- cheap HTTP fetch first in `AUTO` mode;
- automatic browser fallback for HTTP failures and obvious client-rendered shells;
- optional lazy Playwright renderer (no browser dependency in the core path);
- explicit `AUTO`, `NEVER` and `ALWAYS` render modes;
- bounded response size, timeout and HTTP(S)-only URL contract;
- redirect/final-URL provenance and acquisition trace;
- decoded HTML/text is normalized into the existing `RawAsset` contract;
- no per-site transport toggles are needed in the normal path.

The engine remains domain-neutral. Discount, doors, procurement, catalog and future domains define `FieldSpec` keys/aliases; operators do not inspect DOM nodes or maintain selectors, and do not choose static-vs-browser acquisition per site in the normal `AUTO` path.

See [`docs/tasks/DP-ENGINE-001.md`](docs/tasks/DP-ENGINE-001.md), [`docs/tasks/DP-ENGINE-002.md`](docs/tasks/DP-ENGINE-002.md) and [`docs/tasks/DP-ENGINE-003.md`](docs/tasks/DP-ENGINE-003.md).

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

Browser rendering is optional. To enable the default Playwright fallback:

```bash
python -m pip install -e '.[browser]'
playwright install chromium
```
