# High-Density Builder v2 Core Acceptance

Date: 2026-08-09

## Scope

This release candidate adds the independent `deck-builder-high-density` route:

```text
Page Packages
-> MBB storyline candidates and user selection
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
| CyberPPT-derived MBB content enrichment | Three-state MBB contract, full page registry, evidence and exact numeric guards, signed selection/seal tests |
| Content-aware ImageGen blueprint | Full locked-content/style prompt, signed challenge/result receipts, explicit approval, fresh provider smoke |
| Blueprint-to-native-SVG | Content Lock/Scene parity, production image and text gates, measured blueprint/SVG comparison |
| SVG-to-DrawingML PPTX | SVG-authoritative compiler, conversion trace, batch render, OOXML readback, SVG/PPTX comparison |

The source capability probe reports `ready` when schemas, Python packages, renderers, and fonts are present. The public Skill remains optional and `external_adoptable` until the release is merged and installed. The standard profile remains the default path.

## Contract Matrix

| Artifact | Contract |
| --- | --- |
| MBB plan | `deck_mbb_plan.v1` |
| MBB user decision receipt | `deck_mbb_user_decision_receipt.v1` |
| MBB selection receipt | `deck_mbb_selection_receipt.v1` |
| MBB Runtime seal | `deck_mbb_runtime_seal.v1` |
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
- Provider smoke lineage: the committed record is retired after the MBB contract migration and cannot satisfy the current release gate; a fresh provider run is required.
- Provider challenge status: `docs/qa/high-density-builder-v2/phase-4-provider-challenge-status.json`.
- Six-page external icon acceptance: `docs/qa/high-density-builder-v2/phase-4-six-page-icon-external-acceptance.json` remains `blocked_missing_local_benchmark_artifacts`; the six private page artifact sets are intentionally excluded from the repository.
- External 73-page MVP index: `docs/qa/high-density-builder-v2/phase-4-73-page-external-mvp-index.json`.
- Standard profile evidence: `docs/qa/high-density-builder-v2/phase-4-standard-profile-evidence.json`.
- Final QA/Review result: `docs/qa/high-density-builder-v2/phase-4-final-qa-review.md`.

Raw provider payloads, generated images, private 73-page source material, and local run directories are excluded from the repository.

## Validation

- Current branch verification: full pytest `1,399 passed`, with `105 subtests passed`.
- Focused high-density verification: `120 passed` across the builder, distinct-acceptance, and icon-stability suites.
- Local static checks: Ruff, Python 3.11/3.12 compileall, and `git diff --check` pass.
- The seven-page fixture remains covered by the current test suite. The committed provider record is historical and is excluded from the current MBB release decision.
- Standard profile regression remains covered by the current full suite; the committed standard-profile file is retained as historical evidence.
- Coverage, fresh provider smoke, and six-page external icon evidence have not been regenerated on the current MBB head.

## Release Decision

**Local implementation acceptance: pass. Release acceptance: blocked pending fresh MBB provider evidence, current coverage evidence, and the six-page external icon artifact refresh.**

## Rollback

- Keep old runs for audit; do not mark v1 process artifacts as v2 completed.
- Explicitly select the standard profile when high-density requirements or dependencies are unavailable.
- Do not silently fall back from high-density to standard after a high-density failure.

See `docs/migration/high-density-builder-v2.md` for run and contract migration rules.
