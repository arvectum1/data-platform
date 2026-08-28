# DP-ENGINE-008 — Durable result/review persistence

**Status:** implemented

## Goal

Persist governed extraction results separately from `DP-ENGINE-007` execution checkpoints so successful/review-required/incomplete item evidence survives process restarts and review can continue without reacquiring or reparsing the page.

The separation is deliberate:

- **checkpoint store** = execution control state only;
- **result store** = durable extraction/review data and evidence.

This closes the main persistence gap left by `DP-ENGINE-007`: a `review_required` checkpoint can now point to a durable candidate set that a reviewer may open later, confirm/reject, persist, and reconcile back into the job state.

## Durable result record

`StoredResultRecord` is keyed by:

- `job_id`;
- `item_id`;
- job `definition_hash`.

It also stores:

- result status (`ready`, `review_required`, `incomplete`);
- payload SHA-256;
- optimistic `revision`;
- `created_at` / `updated_at`;
- schema version (`RESULT_SCHEMA_VERSION = 1`).

A record payload hash is recomputed during deserialization. Tampered/corrupted payloads fail with `ResultIntegrityError` rather than being silently trusted.

## Persisted payload

The default durable payload preserves what is required to continue governed review:

- `RawAsset.asset_id` and `source_url`;
- asset metadata/provenance;
- acquisition attempts and warnings;
- all field definitions;
- field statuses/reasons;
- all candidates and candidate ids;
- candidate values/confidence/provider;
- evidence kind/source reference/excerpt/metadata;
- provider errors;
- learning events/warnings.

The acquisition and extraction sides are reconstructed onto the same `RawAsset` object when a record is loaded.

### Raw page content policy

`ResultCodec()` defaults to `include_raw_content=False`.

Therefore the durable result normally omits:

- raw page text;
- raw HTML;
- raw asset attributes.

Those values are not required by `ExtractionEngine.confirm()` or confirmation learning. This avoids turning every review record into a full page archive.

A governed deployment that explicitly needs a source snapshot may use:

```python
codec = ResultCodec(include_raw_content=True)
```

Then text/HTML/attributes are included in the persisted payload.

## Value codec

Candidate values and metadata are not stringified silently.

The codec preserves these types explicitly:

- `None`;
- `bool`;
- `int`;
- finite `float`;
- `str`;
- `bytes`;
- `list`;
- `tuple`;
- mappings with string keys.

Unsupported arbitrary Python objects raise `ResultSerializationError`.

This prevents a persisted review candidate from changing type merely because the process restarted.

## Result stores

`ResultStore` defines:

- `load(job_id, item_id)`;
- `create(record)`;
- optimistic `update(record, expected_revision=...)`;
- filtered `list(...)`;
- `delete(job_id, item_id)`;
- `clear_job(job_id)`.

Three baseline implementations are included.

### In-memory

`InMemoryResultStore` is useful for tests and process-local execution.

### JSON

`JsonResultStore(directory)` provides:

- atomic temp-file + `os.replace` writes;
- hashed job/item path names;
- one durable JSON record per item;
- reload/list/delete/clear behavior.

Like the JSON checkpoint/profile stores, this is a simple local single-writer backend, not the preferred multi-process backend.

### SQLite

`SQLiteResultStore(path)` provides:

- stdlib `sqlite3` only;
- WAL mode;
- busy timeout;
- `BEGIN IMMEDIATE` writes;
- optimistic revision checks inside a transaction;
- shared state across processes on one runtime node;
- status/job indexes for review lookup;
- explicit close/context-manager support.

This mirrors the single-node production persistence direction established by `DP-ENGINE-006`.

## Optimistic review revisions

Every created result starts at revision `1`.

Every successful update increments the revision.

`DurableReviewCoordinator.confirm(... expected_revision=N)` can therefore reject stale browser/UI submissions if another reviewer/process already changed the record.

The result store never performs blind last-write-wins review updates.

## Executor integration

`JobExecutor` accepts:

```python
JobExecutor(
    checkpoint_store=...,
    result_store=...,
    result_codec=...,
)
```

When a URL extraction returns a semantic result (`succeeded`, `review_required` or `incomplete`), execution order is:

1. extraction completes;
2. durable result is written;
3. terminal checkpoint state is written.

Persisting the result **before** the terminal checkpoint is intentional.

### Crash-window recovery

If the process crashes after step 2 but before step 3, the durable checkpoint still says `running`, but the result already exists.

On resume, `JobExecutor` first checks for a matching durable result. If found, it:

1. restores the `URLExtractionResult`;
2. derives the terminal item state;
3. repairs the checkpoint;
4. returns the item with `resumed=True`;
5. does **not** fetch the URL again.

This removes an avoidable duplicate acquisition after the expensive work already completed successfully.

## Rehydrating terminal items

With a result store configured, ordinary checkpoint resume also reloads the durable payload into `JobItemResult.result` for terminal items.

Without a result store, `DP-ENGINE-007` behavior is unchanged: resumed terminal items have no live extraction payload.

This keeps durable persistence opt-in at the executor boundary and backward compatible.

## Clean restart semantics

`run(job, resume=False)` means a clean execution restart.

When a result store is configured, existing durable results for that `job_id` are cleared before the fresh execution begins, matching the fresh checkpoint behavior.

`clear_results(job_id)` is also available independently from `clear_checkpoint(job_id)`.

## Durable review coordinator

`DurableReviewCoordinator` provides the post-restart review path:

```python
coordinator = DurableReviewCoordinator(
    result_store,
    pipeline=pipeline,
    checkpoint_store=checkpoint_store,
)

pending = coordinator.pending(job_id="catalog-refresh")
record, result = coordinator.get("catalog-refresh", item_id)

candidate_id = result.extraction.decisions["price"].candidates[0].candidate_id
update = coordinator.confirm(
    "catalog-refresh",
    item_id,
    {"price": candidate_id},
    expected_revision=record.revision,
)
```

`confirm()` calls the existing `URLExtractionPipeline.confirm()` path on the reconstructed result.

Therefore the core review rule is unchanged:

- select an existing candidate id; or
- reject a review-required field with `None`.

There is still no manual replacement-value API.

No acquisition method is invoked during durable review continuation.

## Confirmation learning after restart

Because review goes through the normal pipeline `confirm()` method, `DP-ENGINE-005` structural learning still applies.

A production review worker should construct its review pipeline with the same persistent site-profile backend used by extraction workers (for example `SQLiteSiteProfileStore`).

The persisted result supplies the original source URL and candidate evidence needed by the learner; the page itself is not fetched again.

## Checkpoint synchronization

If a `JobCheckpointStore` is provided to `DurableReviewCoordinator`, confirmation also reconciles the job item state:

- final ready result -> `succeeded`;
- remaining review fields -> `review_required`;
- rejected/unresolved required result -> `incomplete`.

Attempt count is preserved.

`reconcile_checkpoint(job_id, item_id)` can repeat this synchronization explicitly.

### Cross-store failure boundary

Result update and checkpoint update are separate persistence operations and are not a distributed transaction.

Ordering is:

1. persist the reviewed result;
2. update the checkpoint.

If checkpoint persistence fails after the result update, the durable review decision is not discarded. `reconcile_checkpoint()` can repair the control-plane state later.

A future deployment that requires one atomic transaction can implement both concerns inside a common infrastructure adapter without changing the extraction/review contracts.

## Sensitive-data boundary

Unlike the `DP-ENGINE-007` checkpoint, the result store intentionally contains review data such as:

- source URLs;
- extracted candidate values;
- evidence excerpts/metadata;
- acquisition provenance.

It is therefore a **protected data/evidence store**, not a low-sensitivity control checkpoint.

This task does not pretend otherwise and does not copy result payloads back into checkpoint JSON.

Raw page content remains opt-in as described above.

## Failure semantics

- Result serialization failure prevents terminal persistence.
- Result-store failure is authoritative and is not silently swallowed.
- The executor leaves the pre-terminal `running` checkpoint state, allowing later recovery/retry.
- Existing result with the same payload/definition is idempotent.
- Existing result with different payload is not silently clobbered; `ResultConflictError` is raised.
- Job definition mismatch raises `ResultDefinitionMismatchError`.
- Stale review revision raises `ResultConflictError`.
- Tampered payload raises `ResultIntegrityError`.

## Human participation rule

The customer/reviewer still only performs the minimal governed action already established in `DP-ENGINE-001/005`:

- inspect automatically proposed candidates;
- confirm one; or
- reject them.

The reviewer does **not**:

- reacquire the page;
- inspect DOM/CSS/XPath;
- reconstruct a failed batch;
- re-enter extracted values;
- manage checkpoint files;
- manually copy evidence between processes.

## Explicit non-goals

`DP-ENGINE-008` does **not** implement:

- reviewer identity/RBAC;
- encryption-at-rest/key management;
- web review UI;
- distributed/network database deployment;
- cross-node transactions;
- object/blob storage for very large raw page archives;
- review assignment/claim/lease queues;
- SLA/escalation rules;
- publication/export sinks;
- manual value correction;
- CSS/XPath learning;
- authentication/session persistence.

Those layers can consume the durable result/review contract later.

## Acceptance evidence

The targeted `DP-ENGINE-008` regression harness verifies:

- codec round-trip preserves candidate values/ids/evidence;
- bytes/tuple metadata survives persistence;
- default codec omits raw page content;
- explicit full-snapshot mode preserves raw content;
- unsupported arbitrary values fail explicitly;
- payload hash detects tampering;
- initial persistence is idempotent for the same payload;
- differing existing payload cannot be silently overwritten;
- JSON store survives reload and lists pending reviews;
- two SQLite store instances observe shared durable state;
- SQLite revision conflicts are enforced;
- persisted review can be confirmed without reacquisition;
- review confirmation changes durable status to ready;
- checkpoint review state synchronizes to succeeded;
- definition mismatch blocks unsafe review;
- executor resume rehydrates terminal result payload;
- crash between result persistence and terminal checkpoint does not cause refetch;
- `resume=False` clears prior result state before reexecution;
- stale review revision is rejected.

Local targeted persistence/review harness: **14 tests passed**.
