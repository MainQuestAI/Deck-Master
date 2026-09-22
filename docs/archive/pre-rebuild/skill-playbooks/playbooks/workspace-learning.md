# Playbook — Workspace Learning Pack

How to build and use the workspace learning pack so that learnings from past
runs inform future Agent executions.

## Build Learning Pack

After a run reaches the approved queue or delivery stage:

```bash
python3 scripts/deck_master.py build-learning-pack --workspace <workspace>
```

Outputs:

- `workspace/learning/workspace_learning_pack.json`
- `workspace/learning/agent_context_summary.md`

## What's in the Pack

- **High-value patterns**: narrative patterns that repeatedly produce good results
  (e.g., "problem diagnosis → target architecture → phased roadmap").
- **Frequent failure modes**: quality findings that recur across runs (e.g., "ROI
  page missing client metrics").
- **Strong assets**: historical slides with high approval and delivery rates.
- **Agent guidance**: concrete instructions for the next Agent run.

## Use at Start of Run

At the start of every new run, before generating narrative advice:

```bash
python3 scripts/deck_master.py show-learning-pack --workspace <workspace>
```

Apply `agent_guidance` items to:

- Narrative advice generation (prefer patterns that work).
- Source decisions (favour strong assets).
- Page generation briefs (avoid known failure modes).

## Data Sources

The pack aggregates:

- `assets/asset_feedback.jsonl`
- `assets/asset_health_report.json`
- `delivery/delivery_outcome.json`
- Run-level `preview_manifest.json`
- `quality_reports/`
- `approved_queue.json`
