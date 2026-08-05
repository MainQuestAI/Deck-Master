---
name: deck-builder-high-density
description: Build editable high-density PPTX decks from locked Page Packages through CyberPPT-derived NBB enrichment, content-aware image blueprints, native SVG reconstruction, and SVG-to-DrawingML readback.
triggers:
  - build high-density deck
  - editable high-density pptx
  - image blueprint to pptx
  - high-density builder
---

# High-Density Deck Builder

Use this Skill when the run has validated `page_packages/*.json` and the requested profile is `high-density`. This Skill owns the complete route inside Deck Master. CyberPPT, `native-svg-redraw`, Product Design `image-to-code`, PPT Master, and OfficeCLI are reference capabilities only. They are not runtime dependencies.

## First Checks

- Page Packages exist, are valid, unique, ready for build, and match the run ID.
- The high-density capability reports all v2 schemas and visual renderers ready.
- Production has an approved `deck_high_density_style_lock.v1`; missing lock enters style selection.
- The output profile is `production_pptx` or an explicitly permitted fixture/dev profile.

## Do Not Use

- Use for standard-profile decks or direct office post-processing.
- Use when the run has only an image or preview manifest and no validated Page Packages.
- Use to treat blueprint text as factual source material.

## Forcing Questions

- Which Page Package evidence supports each visible claim and numeric value?
- Which fixed style lock is approved for this run?
- Which elements must remain native and editable after handback?

## Runtime Ownership

Deck Master owns the v2 contracts, stage state, lineage, retries, compiler, readback, and canonical handback. Agent-owned actions return exact continuation artifacts and commands to this runtime.

## Canonical Chain

```text
Page Package + evidence/narrative context
-> CyberPPT-derived NBB plan
-> content_lock.v2
-> frozen content-aware blueprint_prompt.v1
-> approved ImageGen blueprint
-> page_scene.v2 + native SVG
-> measured blueprint/SVG review
-> SVG-to-DrawingML compiler
-> editable PPTX + OOXML readback
-> canonical handback -> deck-quality
```

Page Package remains the fact source. ImageGen provides composition evidence. The approved SVG provides the PPTX visual source. Scene is the semantic, measurement, text-reference, and acceptance sidecar.

## Allowed Commands

```bash
deck-master suite-status --capability deck_master.build.high_density.v1 --output json
deck-master build prepare --run-dir <run_dir> --profile high-density --output-profile production_pptx
deck-master build run --run-dir <run_dir> --profile high-density
deck-master build status --run-dir <run_dir> --profile high-density --watch --watch-timeout 30
deck-master next-step --run-dir <run_dir>
deck-master build retry --run-dir <run_dir> --profile high-density --page-id P001 --stage svg
```

## Runtime Stages

### A. NBB and Content Lock

Write `high_density_build/nbb/nbb_plan.json` and `high_density_build/content_locks/<page_id>.content_lock.json` using `deck_nbb_plan.v1` and `deck_content_lock.v2`.

Carry forward CyberPPT's NBB behavior: evidence ledger, storyline/SCR audit, conclusion, supporting arguments, caveat, SO WHAT, page material pool, density target, required component IDs, and required text refs. Every factual or numeric statement retains evidence lineage. Sparse pages, unsupported facts, missing components, and stale hashes block before blueprint generation.

### B. Style Lock and ImageGen Blueprint

The fixed CyberPPT-derived registry contains eight stable style IDs. Production must use an approved `high_density_build/style/style_lock.json`; fixture/dev may use the explicit deterministic default.

Before ImageGen, write `high_density_build/prompts/<page_id>.blueprint_prompt.json` using `deck_blueprint_prompt.v1`. The prompt must contain the real title, conclusion, content summary, evidence IDs, required components, target language, style lock, and prohibited page numbers/internal labels. The prompt artifact must exist before the image.

Write `high_density_build/blueprints/<page_id>.blueprint_manifest.json` using `deck_blueprint_manifest.v2`. Record prompt/content/style hashes, image hash, provider metadata, source canvas, contained 16:9 frame, and exact transform. Non-16:9 sources use an inscribed frame and never stretch.

### C. Image to Native SVG

Agent reads the actual blueprint and content lock, writes `page_scene.v2` plus approved native SVG, then uses the repository tools for validation and measurement. The canonical Scene path is `high_density_build/scenes/<page_id>.page_scene.json`; `page_scenes/<page_id>.json` is a compatibility mirror.

Every visible element has a stable ID, component ID, role, priority, source/target bbox, z-order, text ref or asset ref, editability target, and overflow policy. P0/P1 text is exact content-lock text. Whole-page/near-full-page images, `foreignObject`, scripts, iframes, external CSS/resources, hidden text layers, and unregistered images are blocked. Registered images are limited to 35% per asset and 50% in aggregate, and cannot cover P0/P1 text.

### D. Measured Visual QA

Render normalized blueprint and SVG at the same `1672 x 941` canvas. Metrics are generated from actual files with Pillow + NumPy and `rsvg-convert`, then written to `high_density_build/reviews/<page_id>.metrics.json`. The v2 review must bind renderer, source hashes, mask hash, thresholds, text-masked SSIM, P0/P1 bbox deltas, color/layout findings, and component coverage.

Initial gates: text-masked SSIM `>= 0.92`, P0 region SSIM `>= 0.92`, P0/P1 bbox edge delta `<= 2 px`, 100% P0/P1 text/component coverage, zero unresolved overflow/overlap/wrong-anchor findings. Production needs producer self-review and main review evidence.

### E. SVG to DrawingML and Handback

The compiler reads approved SVG DOM, `page_scene.v2` sidecar, content-lock notes/text refs, and registered asset map. Geometry, styles, visible text, and z-order come from SVG. The Scene cannot generate PPTX independently.

Supported native output includes text/tspan, rect/circle/ellipse, line/polyline/polygon, supported paths, controlled opacity/fill/stroke, registered images, groups, and notes. Unsupported SVG elements fail with the element ID and a recovery action. Write `deck_svg_to_drawingml_trace.v1`, `deck_pptx_readback.v2`, and SVG/PPTX render parity evidence. PPTX parity requires text-masked SSIM `>= 0.97`, P0/P1 geometry `<= 0.75 pt`, exact P0 text, complete P1 text, and full trace coverage.

## Exit Artifacts

- `nbb/nbb_plan.json`
- `style/style_options.json` and `style/style_lock.json`
- `content_locks/<page_id>.content_lock.json`
- `prompts/<page_id>.blueprint_prompt.json`
- `blueprints/<page_id>.blueprint_manifest.json` and normalized preview
- `scenes/<page_id>.page_scene.json`
- native SVG, SVG preview, metrics, self-review, and main review
- page PPTX trace, page/deck readback, and PPTX render parity
- `high_density_manifest.v2`, `build_manifest.json`, `artifact_manifest.json`, and `render_result.json`

## Next Skill

`deck-quality` consumes the canonical handback after the high-density manifest and readback gates pass.

## Agent Continuation

When Agent work is required, return `awaiting_agent_build` with `run_id`, page/stage, `input_refs`, `output_refs`, `required_schema`, `acceptance_command`, `resume_command`, and reason. Supported actions are `agent_nbb_enrich`, `agent_imagegen`, `agent_visual_reconstruct`, `agent_svg_repair`, `agent_self_review`, and `agent_main_review`. Style selection uses `awaiting_user_decision`.

`build status --watch` waits through `prepared`, `building`, and `awaiting_agent_build`; it exits only at `completed`, `blocked`, `failed`, `awaiting_user_decision`, or timeout.

## Stop Conditions

- `HD_CONTENT_LOCK_INVALID`
- `HD_BLUEPRINT_REGEN_REQUIRED`
- `HD_PAGE_SCENE_INVALID`
- `HD_SVG_REVIEW_FAILED`
- `HD_PPTX_EDITABILITY_FAILED`
- `HD_ASSET_POLICY_BLOCKED`
- `HD_CONTRACT_HANDBACK_FAILED`
- missing schema, Python package, SVG renderer, PPTX renderer, or approved style lock

## Safety Rules

- Keep all paths run-relative and reject traversal, cross-run packages, malformed contracts, and stale hashes.
- Keep Page Package evidence as the factual source; every derived claim must retain evidence references.
- Reject whole-page image wrappers, hidden text overlays, unregistered assets, unsupported SVG, and incomplete readback.
- Keep private benchmark sources and provider payloads out of the repository; retain only sanitized evidence indexes and metrics summaries.

Never use ImageGen text as facts. Never emit page numbers or internal generation annotations. Never bypass content coverage, visual metrics, review, readback, or `deck-quality`.
