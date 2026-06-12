# Playbook — PPT Library Handoff

How to invoke PPT Library for candidate slide selection and return results to
Deck Master.

## Input

Read `sourcing_plan.json` or `page_tasks.json` to identify which beats need
`reuse` or `adapt` sourcing.

## Invoke PPT Library

```bash
ppt-lib search \
  --query "<beat topic / claim>" \
  --archetype "<page_archetype>" \
  --industry "<industry>" \
  --limit 5 \
  --output library_results/beat_<id>.json
```

## Output Schema

Each candidate must carry (see `schemas/ppt_library_candidate.schema.json`):

- `slide_id` (required)
- `canonical_slide_id`
- `title`
- `text_summary`
- `source_file`
- `page_number`
- `screenshot_path`
- `confidence` (0–1)
- `narrative_role`
- `page_archetype`

## Validate Before Import

```bash
python3 scripts/deck_master.py validate-ppt-library-result \
  --input library_results/selection.json
```

## Decision

After selection:

```bash
python3 scripts/deck_master.py decide-sourcing --run-id <run_id>
```

Deck Master writes `sourcing_plan.json` with `reuse`, `adapt`, `generate` or
`manual_placeholder` per beat.
