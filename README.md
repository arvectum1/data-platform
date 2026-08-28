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

`DP-ENGINE-004` composes those layers into one governed URL execution path:

- `URLExtractionPipeline.extract_url()` runs acquisition, discovery and extraction in one call;
- the default pipeline wires `AcquisitionEngine` + `AutoDiscoveryProvider` + `ExtractionEngine`;
- `URLExtractionResult` preserves acquisition evidence and extraction evidence together;
- `ready` is true only when no review is required and no required field is unresolved/rejected;
- `confirm()` continues the same result without reacquiring the page or losing transport provenance;
- applications no longer need to manually glue `DP-ENGINE-003` to `DP-ENGINE-002`.

`DP-ENGINE-005` adds bounded confirmation-learning without selector configuration:

- explicit reviewer confirmations teach structural evidence preferences for that site/field;
- candidate values are never persisted in the site profile;
- dynamic source indices are normalized into reusable structural fingerprints;
- selected structures receive bounded confidence boosts and competing/rejected structures receive bounded penalties;
- learning is scoped to the exact normalized host and does not leak across subdomains;
- in-memory learning is enabled by default for `URLExtractionPipeline`;
- `JsonSiteProfileStore` provides atomic persistent learning across process restarts;
- auto-selected fields do not self-train.

`DP-ENGINE-006` adds profile lifecycle and production-oriented persistence:

- schema v2 timestamps every structural signal and versions every store revision;
- learned weight decays by half-life and becomes ineffective after a hard TTL;
- new confirmations are added to the already-decayed weight rather than reviving stale history;
- `prune()` physically removes expired/near-zero signals, while lazy read-time expiry keeps decisions correct even before maintenance runs;
- legacy JSON schema v1 migrates to schema v2 automatically;
- `SQLiteSiteProfileStore` provides WAL-backed transactional storage for multiple processes on one runtime node;
- `URLExtractionPipeline.maintain_profiles()` exposes a scheduler-friendly maintenance hook.

The engine remains domain-neutral. Discount, doors, procurement, catalog and future domains define `FieldSpec` keys/aliases; operators do not inspect DOM nodes or maintain selectors, do not choose static-vs-browser acquisition per site, do not wire extraction stages manually, and do not edit learned profiles in the normal path.

See [`docs/tasks/DP-ENGINE-001.md`](docs/tasks/DP-ENGINE-001.md), [`docs/tasks/DP-ENGINE-002.md`](docs/tasks/DP-ENGINE-002.md), [`docs/tasks/DP-ENGINE-003.md`](docs/tasks/DP-ENGINE-003.md), [`docs/tasks/DP-ENGINE-004.md`](docs/tasks/DP-ENGINE-004.md), [`docs/tasks/DP-ENGINE-005.md`](docs/tasks/DP-ENGINE-005.md) and [`docs/tasks/DP-ENGINE-006.md`](docs/tasks/DP-ENGINE-006.md).

## End-to-end usage

```python
from arvectum_data import FieldSpec, URLExtractionPipeline

pipeline = URLExtractionPipeline()
result = pipeline.extract_url(
    "https://example.test/item",
    [FieldSpec("title"), FieldSpec("price", aliases=("Цена", "Стоимость"))],
)

if result.ready:
    values = result.values()
```

## Persistent site learning

For one local process, JSON remains available:

```python
from arvectum_data import JsonSiteProfileStore, URLExtractionPipeline

pipeline = URLExtractionPipeline(
    profile_store=JsonSiteProfileStore("state/site-profiles.json"),
)
```

For a multi-process runtime on one host, use SQLite:

```python
from arvectum_data import SQLiteSiteProfileStore, URLExtractionPipeline

store = SQLiteSiteProfileStore("state/site-profiles.db")
pipeline = URLExtractionPipeline(profile_store=store)
```

The profile contains only structural evidence statistics; confirmed field values are not stored. The default lifecycle uses a 30-day half-life and a 180-day hard TTL. Expired signals stop affecting scoring lazily; a runtime scheduler may call `pipeline.maintain_profiles()` to reclaim storage.

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
