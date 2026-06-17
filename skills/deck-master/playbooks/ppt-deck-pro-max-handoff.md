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

For each task in `generation_tasks/`:

```bash
ppt-deck-pro-max generate \
  --task generation_tasks/<task_id>.json \
  --output generated_assets/<beat_id>/ \
  --visual-system workspace/visual-system/ \
  --archetypes workspace/structure-assets/page_archetypes.md
```

If a task has `task_type: adapt`, preserve the selected reference slide
structure and rewrite it for the current run. If it has `task_type: generate`,
create a new page from the task brief.

## Write Result

Write `generation_result.json` per `schemas/generation_result.schema.json`:

```json
{
  "schema_version": "deck_generation_result.v1",
  "run_id": "<run_id>",
  "tool": "ppt-deck-pro-max",
  "task_id": "<task_id>",
  "beat_id": "<beat_id>",
  "status": "completed",
  "artifact_path": "generated_assets/<beat_id>/slide.pptx",
  "preview_path": "generated_assets/<beat_id>/preview.png",
  "errors": []
}
```

On failure set `"status": "failed"` and populate `errors`.

## Import Result

```bash
python3 scripts/deck_master.py import-generation-result \
  --run-id <run_id> --input generation_result.json
```

## Refresh Preview

```bash
python3 scripts/deck_master.py refresh-preview-from-generation --run-id <run_id>
```

## v0.9.6 UAT

After generation task/result exchange, run:

```bash
python3 scripts/deck_master.py uat-generation-tool --run-dir runs/<run_id> --tool ppt-deck-pro-max --require-preview
```

The report is written to `runs/<run_id>/uat_reports/generation_tool_uat.json` and `.md`.
