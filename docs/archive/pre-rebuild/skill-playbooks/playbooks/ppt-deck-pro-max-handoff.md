# Playbook — PPT Deck Pro Max Handoff

How to hand off page generation tasks to PPT Deck Pro Max and return results.

## Prepare Handoff

```bash
python3 scripts/deck_master.py prepare-generation-handoff --run-id <run_id>
```

This writes `generation_tasks/index.json` with one task entry for each page that
needs `generate` or `adapt` work.

## Per-Task Structure

Each task carries:

- `task_id`, `beat_id`, `page_title`
- `generation_brief`
- `claim_ids`, `evidence_refs`
- `workspace_refs` (visual-system, page archetypes)
- `quality_requirements`
- `style_constraints`

## Invoke PPT Deck Pro Max

Production runs dispatch an Agent package instead of executing the bundled fixture adapter:

```bash
python3 scripts/deck_master.py run-generation --run-id <run_id>
```

This writes:

- `generation_dispatch/dispatch_package.json`
- `generation_dispatch/agent_instructions.md`

The session status becomes `awaiting_agent_execution`. The Agent reads the dispatch package, creates the requested assets, and writes one result JSON per task into `generation_results/`.

Equivalent explicit dispatch entry:

```bash
python3 scripts/deck_master.py generation-session dispatch --run-id <run_id>
```

## Write Result

Write one `deck_generation_result.v2` JSON per task:

```json
{
  "schema_version": "deck_generation_result.v2",
  "run_id": "<run_id>",
  "session_id": "<session_id>",
  "task_id": "<task_id>",
  "page_id": "<beat_id>",
  "beat_id": "<beat_id>",
  "producer": {
    "capability": "ppt-deck-pro-max",
    "version": "<version>",
    "source_ref": "<source_ref>"
  },
  "status": "completed",
  "source_fingerprint": "<sha256 from dispatch_package.json>",
  "artifacts": [
    {
      "artifact_id": "<beat_id>_artifact",
      "kind": "page_pptx",
      "path": "generated_assets/<beat_id>/slide.pptx",
      "media_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "sha256": "<artifact_sha256>",
      "bytes": 123,
      "validation_status": "validated",
      "editability": "native"
    }
  ],
  "preview": {
    "artifact_id": "<beat_id>_preview",
    "kind": "page_png",
    "path": "generated_assets/<beat_id>/preview.png",
    "media_type": "image/png",
    "sha256": "<preview_sha256>",
    "bytes": 123,
    "validation_status": "validated",
    "editability": "not_applicable"
  },
  "created_at": "2026-06-22T00:00:00+00:00"
}
```

On failure set `"status": "failed"` and populate `errors`.

## Import Result

```bash
python3 scripts/deck_master.py generation-session import-results \
  --run-id <run_id> --input generation_results/<task_id>.json
```

Batch import is also supported:

```bash
python3 scripts/deck_master.py generation-session import-results \
  --run-id <run_id> --input generation_results/
```

Every import writes a receipt under `generation_import_receipts/`.

## Fixture Adapter

```bash
python3 scripts/deck_master.py run-generation --run-id <run_id> --run-mode fixture
```

The bundled adapter is fixture/dev only and must not be used as production evidence.

## v0.9.6 UAT

After generation task/result exchange, run:

```bash
python3 scripts/deck_master.py uat-generation-tool --run-dir runs/<run_id> --tool ppt-deck-pro-max --require-preview
```

The report is written to `runs/<run_id>/uat_reports/generation_tool_uat.json` and `.md`.
