# High-Density Builder v2 Core Acceptance

Date: 2026-08-08

## Scope

This release candidate adds the independent `deck-builder-high-density` route:

```text
Page Packages
-> NBB storyline candidates and user selection
-> selected-storyline enrichment and runtime seal
-> Content Lock and content-aware ImageGen blueprint
-> approved native SVG
-> editable DrawingML PPTX
-> render parity, OOXML readback, and Deck Quality handback
```

CyberPPT, PPT Master, native-svg-redraw, image-to-code, and OfficeCLI remain reference implementations or optional downstream tools. The runtime does not import or compose those Skills.

## Core Capability Status

| Capability | Acceptance evidence |
| --- | --- |
| CyberPPT-derived NBB content enrichment | Three-state NBB contract, full page registry, evidence and exact numeric guards, signed selection/seal tests |
| Content-aware ImageGen blueprint | Full locked-content/style prompt, signed challenge/result receipts, explicit approval, fresh provider smoke |
| Blueprint-to-native-SVG | Content Lock/Scene parity, production image and text gates, measured blueprint/SVG comparison |
| SVG-to-DrawingML PPTX | SVG-authoritative compiler, conversion trace, batch render, OOXML readback, SVG/PPTX comparison |

The source capability probe reports `ready` when schemas, Python packages, renderers, and fonts are present. The public Skill remains optional and `external_adoptable` until the release is merged and installed. The standard profile remains the default path.

## Contract Matrix

| Artifact | Contract |
| --- | --- |
| NBB plan | `deck_nbb_plan.v1` |
| NBB user decision receipt | `deck_nbb_user_decision_receipt.v1` |
| NBB selection receipt | `deck_nbb_selection_receipt.v1` |
| NBB Runtime seal | `deck_nbb_runtime_seal.v1` |
| Content lock | `deck_content_lock.v2` |
| Style lock | `deck_high_density_style_lock.v1` |
| Blueprint prompt | `deck_blueprint_prompt.v1` |
| Blueprint manifest | `deck_blueprint_manifest.v2` |
| Provider Runtime receipt | `deck_provider_runtime_receipt.v1` |
| Provider Host receipt | `deck_provider_host_receipt.v1` |
| Page Scene | `deck_page_scene.v2` |
| Visual metrics | `deck_visual_metrics.v1` |
| Visual review | `deck_visual_review.v2` |
| Visual main-review receipt | `deck_visual_main_review_receipt.v1` |
| SVG-to-DrawingML trace | `deck_svg_to_drawingml_trace.v1` |
| PPTX readback | `deck_pptx_readback.v2` |
| High-density manifest | `deck_high_density_manifest.v2` |
| High-density status | `deck_high_density_status.v2` |
| Provider smoke evidence | `deck_high_density_provider_smoke.v1` |

## Acceptance Evidence

- AF-01 through AF-20: `docs/qa/high-density-builder-v2/phase-4-af01-af20-matrix.json`.
- Seven distinct pages: `docs/qa/high-density-builder-v2/phase-4-seven-page-e2e.json`.
- Fresh production ImageGen lineage: `docs/qa/high-density-builder-v2/phase-4-provider-smoke-evidence.json`.
- Provider challenge status: `docs/qa/high-density-builder-v2/phase-4-provider-challenge-status.json`.
- External 73-page MVP index: `docs/qa/high-density-builder-v2/phase-4-73-page-external-mvp-index.json`.
- Standard profile evidence: `docs/qa/high-density-builder-v2/phase-4-standard-profile-evidence.json`.
- Final QA/Review result: `docs/qa/high-density-builder-v2/phase-4-final-qa-review.md`.

Raw provider payloads, generated images, private 73-page source material, and local run directories are excluded from the repository.

## Validation

- Full pytest: 1,365 passed and 105 subtests passed.
- Coverage: 82%, with the 80% release floor enforced by `coverage report --fail-under=80`.
- Local static checks: Ruff, compileall, and `git diff --check` pass.
- The seven-page fixture and fresh production provider smoke pass their lineage, visual, DrawingML, readback, handback, and `deck-quality` render gates.
- Standard profile prepare, run, and preview-gate evidence is recorded in `phase-4-standard-profile-evidence.json`.
- GitHub Actions Python 3.11/3.12 CI, contract/schema checks, preview gate, release smoke, and CI RC gate pass on source commit `4af2928b3a98ddeafba2abe49a890f3051458afc`.
- Final independent review and QA remain required before changing PR #26 from Draft.
- Seven-page canonical handback is consumed by `deck-quality`.
- The fresh production provider page passes signed challenge/result lineage, blueprint/SVG and SVG/PPTX visual gates, independent review evidence, and readback lineage.

## Rollback

- Keep old runs for audit; do not mark v1 process artifacts as v2 completed.
- Explicitly select the standard profile when high-density requirements or dependencies are unavailable.
- Do not silently fall back from high-density to standard after a high-density failure.

See `docs/migration/high-density-builder-v2.md` for run and contract migration rules.
