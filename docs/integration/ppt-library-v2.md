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

The input must use:

```json
{
  "schema_version": "deck_master_ppt_library_selection.v1",
  "run_id": "run_id",
  "source": "ppt-library",
  "selections": []
}
```

PPT Library v2 should produce this shape with:

```bash
ppt-lib select-slides \
  --plan narrative_plan.json \
  --brief "..." \
  --contract deck-master.v1 \
  --run-id <run_id> \
  --output selection.json
```

Deck Master does not treat the default `{"report": ...}` file as an import
contract. Use direct search for the default report shape, or use the Deck
Master contract for handback/import.

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
```

For a cross-repo smoke, generate `selection.json` with PPT Library contract
mode, then import it with `import-library-selection` for the same Deck Master
run.
