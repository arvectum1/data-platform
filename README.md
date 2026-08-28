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

`DP-ENGINE-007` adds resumable batch/job execution above the URL pipeline:

- `ExtractionJob` defines ordered URL items plus shared semantic fields;
- `JobExecutor` provides per-item failure isolation and bounded sequential execution;
- default retries apply only to acquisition/timeout/OS failures with deterministic capped backoff;
- review-required and unresolved-required outcomes are distinct from execution failures and are not blindly retried;
- in-memory and atomic JSON checkpoint stores support resume after interruption;
- job-definition hashes block unsafe resume after URLs/fields/acquisition controls change;
- `max_items` supports cooperative worker slices for a future Arvectum OS scheduler;
- checkpoints store execution state only, not URL/header payloads or extracted business values.

`DP-ENGINE-008` adds durable result/review persistence alongside those checkpoints:

- `ResultCodec` serializes governed acquisition/extraction/review state without stringifying candidate values;
- raw page HTML/text/attributes are omitted by default and can be explicitly enabled for governed source snapshots;
- `InMemoryResultStore`, `JsonResultStore` and WAL-backed `SQLiteResultStore` provide result persistence;
- payload SHA-256 detects corruption/tampering and optimistic revisions protect concurrent review updates;
- `JobExecutor` persists the semantic result before writing a terminal checkpoint;
- resume rehydrates terminal `JobItemResult.result` when a result store is configured;
- a crash after result persistence but before terminal checkpoint is recovered without fetching the page again;
- `DurableReviewCoordinator` loads pending candidates after restart, confirms/rejects existing candidate ids through the normal pipeline, and can reconcile the checkpoint state.

The engine remains domain-neutral. Discount, doors, procurement, catalog and future domains define `FieldSpec` keys/aliases; operators do not inspect DOM nodes or maintain selectors, do not choose static-vs-browser acquisition per site, do not wire extraction stages manually, do not edit learned profiles, do not recover batches item-by-item, and do not reparse pages merely to continue a pending review.

See [`docs/tasks/DP-ENGINE-001.md`](docs/tasks/DP-ENGINE-001.md), [`docs/tasks/DP-ENGINE-002.md`](docs/tasks/DP-ENGINE-002.md), [`docs/tasks/DP-ENGINE-003.md`](docs/tasks/DP-ENGINE-003.md), [`docs/tasks/DP-ENGINE-004.md`](docs/tasks/DP-ENGINE-004.md), [`docs/tasks/DP-ENGINE-005.md`](docs/tasks/DP-ENGINE-005.md), [`docs/tasks/DP-ENGINE-006.md`](docs/tasks/DP-ENGINE-006.md), [`docs/tasks/DP-ENGINE-007.md`](docs/tasks/DP-ENGINE-007.md) and [`docs/tasks/DP-ENGINE-008.md`](docs/tasks/DP-ENGINE-008.md).

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

## Batch / resumable execution with durable results

```python
from arvectum_data import (
    ExtractionJob,
    FieldSpec,
    JobExecutor,
    JsonJobCheckpointStore,
    SQLiteResultStore,
)

job = ExtractionJob.from_urls(
    "catalog-refresh-2026-08-28",
    ["https://example.test/a", "https://example.test/b"],
    [FieldSpec("title"), FieldSpec("price", required=True)],
)

results = SQLiteResultStore("state/results.db")
executor = JobExecutor(
    checkpoint_store=JsonJobCheckpointStore("state/jobs"),
    result_store=results,
)
run = executor.run(job, max_items=25)
```

Calling `run(job)` again resumes the checkpoint and skips terminal acquisition work. When a result store is configured, terminal result/evidence is also rehydrated into `JobItemResult.result`.

## Continue pending review after restart

```python
from arvectum_data import DurableReviewCoordinator

review = DurableReviewCoordinator(
    results,
    pipeline=executor.pipeline,
    checkpoint_store=executor.checkpoint_store,
)

record = review.pending(job_id=job.job_id)[0]
record, persisted = review.get(record.job_id, record.item_id)
decision = persisted.extraction.decisions["price"]
candidate_id = decision.candidates[0].candidate_id

updated = review.confirm(
    record.job_id,
    record.item_id,
    {"price": candidate_id},
    expected_revision=record.revision,
)
```

This review path does not reacquire the URL. The result store is a protected data/evidence store: unlike the execution checkpoint, it intentionally contains source identity, candidate values and evidence. Raw page content remains off by default unless `ResultCodec(include_raw_content=True)` is supplied.

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
