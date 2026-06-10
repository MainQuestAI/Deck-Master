# Deck Master Built-in Quality Gate

Date: 2026-06-10
Status: IMPLEMENTED MVP

## 1. Positioning

Quality Gate is a built-in Deck Master subsystem.

It is no longer treated as an external integration. The former `ppt-quality-gate` skill remains useful as a standalone reusable skill, but Deck Master must own the quality runtime, reports, blocking rules, and Web Studio visibility.

## 2. Gate Model

Deck Master now supports three gate types:

- `draft`: checks deck brief, claim map, page tasks, page jobs, evidence gaps, and information density before rendering.
- `render`: checks rendered PPTX page count, sparse pages, and possible full-slide image migration.
- `delivery`: checks final PPTX page count, forbidden/internal wording, media package signals, and delivery blockers.

All gates write first-class run artifacts:

- `quality_reports/draft_gate.json`
- `quality_reports/render_gate.json`
- `quality_reports/delivery_gate.json`
- Matching Markdown reports for human review.

## 3. Scorecard

Each report uses the consulting-style 1-5 rubric:

- Narrative Integrity
- Page Job Clarity
- Information Density
- Evidence And Specificity
- Screenshot And Asset Integration
- Layout Variety
- Consulting-Style Expression
- Visual Readiness
- Delivery Readiness

Status values:

- `pass`
- `conditional_pass`
- `rework_required`

Any P0/P1 finding or `rework_required` blocks delivery.

## 4. CLI

Draft Gate:

```bash
python3 scripts/deck_master.py quality-gate --run-id <run_id> draft
```

Render Gate:

```bash
python3 scripts/deck_master.py quality-gate --run-id <run_id> render \
  --artifact /path/to/rendered.pptx \
  --expected-pages 18
```

Delivery Gate:

```bash
python3 scripts/deck_master.py quality-gate --run-id <run_id> delivery \
  --artifact /path/to/final.pptx \
  --expected-pages 18 \
  --forbidden 内部 \
  --forbidden Brief
```

If `--expected-pages` is omitted, Deck Master uses `preview_manifest.json` page count when available.

## 5. Web Studio

`/api/deck` now returns run-level quality summaries and page-level quality findings. Web Studio displays quality findings in the page detail panel so the user can see blocking reasons and repair instructions next to each page.

## 6. Current Boundary

The MVP uses standard library PPTX package inspection. It does not yet perform full visual rendering, font measurement, screenshot crop judgment, or semantic language review.

Those checks should be added after Deck Master has a stable PPTX assembly path and a real Danone AI Consumer regression sample.
