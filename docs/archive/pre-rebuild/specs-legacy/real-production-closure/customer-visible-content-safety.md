# Customer Visible Content Safety

## Purpose

Deck Master must block customer-facing PPT delivery when internal planning language, template placeholder labels, production instructions, or sensitive markers appear in the final PPTX package.

This gate is a production safety boundary. Prompt instructions can reduce risk, but final delivery clearance is based on artifact inspection and `final_readiness`.

## Content Boundary

Only these fields may become slide text:

- `customer_visible_content.title`
- `customer_visible_content.body_brief`
- `customer_visible_content.evidence_summary`

These fields are internal or limited-purpose and must not become slide body text:

- `internal_production_notes`
- `content_boundary`
- `layout_instruction`
- `reference_slide`
- task metadata
- generation status

Speaker notes may use `speaker_notes`, but the PPTX package is still scanned before delivery because notes can be exposed during client handoff.

## Blocking Terms

Deck Master ships a default forbidden term list for internal production language and template placeholders, including terms such as:

- `关键图示`
- `证书墙`
- `缩略图`
- `卡一`
- `左屏`
- `右屏`
- `功能证据 + 业务价值`
- `待补`
- `占位`
- `制作`
- `讲标`
- `评审`
- `评分`
- `内部`
- `Brief`

Projects can add stricter terms in:

- `<run_dir>/quality/forbidden_terms.md`
- `<workspace>/quality/forbidden_terms.md`

Blank lines and lines starting with `#` are ignored.

## Required Gates

Run delivery quality with the final PPTX artifact:

```bash
python3 scripts/deck_master.py quality-gate --run-dir <run_dir> delivery --artifact <run_dir>/build/deck.pptx
```

This writes both:

- `quality_reports/delivery_gate.json`
- `quality_reports/customer_visible_safety_gate.json`

Production final readiness requires `customer_visible_safety_gate.json`. Missing, invalid, or blocking safety reports prevent client export.

## Repair Standard

When this gate blocks:

- remove or rewrite the hit text in the generated slide source or template
- regenerate the PPTX
- rerun delivery quality gate
- rerun final readiness

Do not approve P0 customer visible safety findings with overrides.
