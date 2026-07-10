# PPT Library v2 Integration

Deck Master supports two PPT Library v2 paths.

## Direct Search Path

`search-library` calls `ppt-lib select-slides` directly and consumes the default
PPT Library report shape:

```bash
python3 scripts/deck_master.py search-library \
  --run-dir <run_dir> \
  --library-mode real \
  --ppt-lib-command ppt-lib
```

This path is used during Deck Master planning and sourcing. It can read the
PPT Library v2 default output shape `{"report": ...}`.

## Standard Handback / Import Path

`import-library-selection` accepts only the Deck Master selection contract:

```bash
python3 scripts/deck_master.py import-library-selection \
  --run-dir <run_dir> \
  --input <selection.json>
```

New handbacks use the v2 contract. The v1 contract remains read-only compatible:

```json
{
  "schema_version": "deck_master_ppt_library_selection.v2",
  "run_id": "run_id",
  "status": "library_degraded",
  "source": "ppt_library",
  "preview_degraded": true,
  "selections": [],
  "warnings": [],
  "by_beat": {}
}
```

Each selection records `beat_id`, `page_task_id`, a query trace, the explicit
role strategy, retrieval method, preview status, and sanitized candidates.
Candidates expose stable identities and run-relative preview references. Raw
`source_file` and `source_path` values are excluded.

PPT Library should produce the Deck Master handback shape with its contract
mode, then import it for the same run:

```bash
ppt-lib select-slides \
  --plan narrative_plan.json \
  --brief "..." \
  --contract deck-master.v2 \
  --run-id <run_id> \
  --output selection.json
```

Deck Master still accepts v1 handbacks for migration. Canonical writes use v2.
The default `{"report": ...}` file remains a direct-search response and is not
an import contract.

## Sourcing and readiness

- New sourcing artifacts use `deck_sourcing_plan.v2` with one decision in
  `pages[]` for every page task.
- Selected `asset_key` values are globally unique unless the page task
  explicitly allows source repetition.
- `library-status` uses `deck_master_library_status.v2`; its runtime, contract,
  semantic search, role selection, fallback, preview, ranking, and hygiene
  fields are the shared readiness truth.
- Production and benchmark runs reject fixture library selection.

## Runtime Requirements

- Use Python 3.12+ for real PPT Library v2 integration.
- Confirm that PPT files, screenshots, historical proposals, and customer
  context are authorized for local indexing and reuse.
- Do not index Downloads, caches, raw customer folders, or private benchmark
  sources unless the user explicitly confirms that scope.

## Verification

```bash
ppt-lib capabilities --output json
ppt-lib select-slides --help
python3 scripts/deck_master.py validate-ppt-library-result --input <selection.json>
python3 scripts/deck_master.py rc-gate --tier ci --output-dir <output_dir> --skip-browser-smoke
```

For a cross-repo smoke, generate `selection.json` with PPT Library contract
mode, then import it with `import-library-selection` for the same Deck Master
run.

Full RC verification additionally requires local backend, benchmark, and a
read-only real run copy:

```bash
python3 scripts/deck_master.py rc-gate \
  --tier full \
  --benchmark-dir <benchmark_dir> \
  --uat-run-dir <read_only_run_copy> \
  --evidence-forbidden-marker <private_marker> \
  --output-dir <output_dir>
```

RC JSON and Markdown contain only safe summaries. Evidence writing fails when
absolute local paths, raw source fields, or configured private markers appear.
