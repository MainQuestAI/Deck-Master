---
name: deck-builder-high-density
description: Build editable high-density PPTX decks from locked Page Packages through NBB enrichment, visual blueprints, native SVG, and DrawingML readback. Use for high-density consulting decks that need image-led composition with editable final output.
triggers:
  - build high-density deck
  - editable high-density pptx
  - image blueprint to pptx
  - high-density builder
---

# High-Density Deck Builder

Use this Skill when the run already has validated `page_packages/*.json` and the requested builder profile is `high-density`. The Skill owns the complete high-density route: content enrichment, blueprint generation, semantic scene reconstruction, native SVG, editable PPTX, readback, and canonical handback.

The implementation is repository-owned. Do not compose this route by invoking CyberPPT, `native-svg-redraw`, PPT Master, or another Skill as a runtime stage.

## Use When

Use after the Producer has created validated Page Packages and the requested output is an editable, high-density PPTX. Use for dense consulting pages that need an ImageGen composition blueprint followed by native reconstruction and readback.

## Do Not Use

Do not use for ordinary standard builds, final quality approval, unsupported customer claims, or a run whose only input is `preview_manifest.json` in production mode.

## First Checks

- Page Packages exist and are ready for build.
- The high-density capability is available.
- The output profile is `production_pptx`.
- The run has a 16:9 visual system lock or an explicit default lock.

## Forcing Questions

- Are all key claims, numbers, caveats, and speaker notes locked to the Page Package?
- Which page regions are P0/P1 and must pass exact text and geometry readback?
- Has the blueprint been checked for ratio drift, page numbers, and internal annotations?

## Runtime Ownership

This Skill owns the high-density build profile inside the `deck-builder` stage: NBB enrichment, blueprint continuation, scene reconstruction, native SVG, editable PPTX, readback, and canonical handback. `deck-quality` owns final quality and delivery approval.

## Allowed Commands

```bash
deck-master suite-status --capability deck_master.build.high_density.v1 --output json
deck-master build prepare --run-dir <run_dir> --profile high-density --output-profile production_pptx
deck-master build run --run-dir <run_dir> --profile high-density
deck-master build status --run-dir <run_dir> --profile high-density --watch
deck-master next-step --run-dir <run_dir>
deck-master build retry --run-dir <run_dir> --profile high-density --page-id P001 --stage svg
```

## Exit Artifacts

`content_lock.v1`, blueprint manifest, `page_scene.v1`, native SVG, preview PNG, visual review evidence, native PPTX, PPTX trace, readback report, `high_density_manifest.v1`, `build_manifest.json`, `artifact_manifest.json`, and `render_result.json`.

## Next Skill

`deck-quality`

## Stop Conditions

- `HD_CONTENT_LOCK_INVALID`
- `HD_BLUEPRINT_REGEN_REQUIRED`
- `HD_PAGE_SCENE_INVALID`
- `HD_SVG_REVIEW_FAILED`
- `HD_PPTX_EDITABILITY_FAILED`
- `HD_ASSET_POLICY_BLOCKED`
- `HD_CONTRACT_HANDBACK_FAILED`
- missing high-density capability

## Safety Rules

Keep internal production notes out of customer-visible content. Do not treat ImageGen text as a fact source. Do not emit page numbers or internal generation annotations. Do not wrap the main page in a whole-page image. Do not bypass P0/P1 overflow, visual review, readback, or `deck-quality`.

## Contract And Entry

Start by checking the capability and preparing the run:

```bash
deck-master suite-status --capability deck_master.build.high_density.v1 --output json
deck-master build prepare --run-dir <run_dir> --profile high-density --output-profile production_pptx
deck-master build run --run-dir <run_dir> --profile high-density
```

The input truth source is `page_packages/*.json`. `preview_manifest.json` may only be adapted in `fixture` or `dev` mode. Production runs must stop with `HD_CONTENT_LOCK_INVALID` when Page Packages are missing.

## Workflow

### 1. Content Lock And NBB Enrichment

For every Page Package, write `high_density_build/content_locks/<page_id>.json` using `content_lock.v1`.

- Preserve the exact customer-visible facts, numbers, claims, caveats, evidence bindings, and speaker notes.
- Carry forward the NBB enrichment pattern: classify page role and density, expand explanatory structure, identify derived claims, reserve regions for key numbers and tables, and choose a multi-region composition for dense pages.
- Treat ImageGen text as layout evidence only. It cannot add facts or replace locked text.
- Exclude page numbers, generation notes, internal labels, production comments, and unsupported claims.
- A Page Package hash change invalidates its lock and all downstream artifacts.

### 2. Blueprint Generation

When a visual blueprint is required, use the active Agent ImageGen capability with the prompt produced from the content lock, density analysis, style lock, and visual inventory. Save the image as:

```text
high_density_build/blueprints/<page_id>.png
```

The generated image is a composition blueprint, never the final PPTX content. The adjacent manifest must be `high_density_build/blueprints/<page_id>.manifest.json` and include:

```json
{
  "schema_version": "deck_blueprint_manifest.v1",
  "run_id": "<run_id>",
  "page_id": "<page_id>",
  "image_path": "high_density_build/blueprints/<page_id>.png",
  "image_sha256": "<64hex>",
  "prompt_sha256": "<64hex>",
  "source_canvas": {"width": 1672, "height": 941, "unit": "px"},
  "slide_frame": {"x": 0, "y": 0, "w": 1672, "h": 941},
  "fit_mode": "approved_frame",
  "internal_annotations": [],
  "approved": true,
  "created_at": "<date-time>"
}
```

Before approval, inspect the blueprint for ratio drift, hidden annotations, page numbers, and internal production labels. Use one uniform frame transform; do not stretch a non-16:9 source.

### 3. Scene Reconstruction

Rebuild the blueprint into `high_density_build/page_scenes/<page_id>.json` using `page_scene.v1`.

- Reuse visible text from the content lock through `text_ref`.
- Give every element a stable `element_id`, role, priority, bbox, editability target, and asset policy.
- Every text element declares preferred and minimum size, maximum lines, and an overflow policy.
- P0 includes title, key claim, key numbers, SO WHAT, core table text, and sources. P1 includes major cards, connectors, chart labels, and explanatory text.
- Preserve the canonical 1672 x 941 canvas and reject out-of-canvas geometry.
- Add `evidence_refs` when the region depends on a locked evidence binding.

### 4. Native SVG And Visual Review

Compile the scene to `high_density_build/svg/<page_id>.svg` and render its preview to `high_density_build/previews/<page_id>.png`.

- Use native text and shapes for all P0/P1 content.
- Whole-page images, `foreignObject`, `script`, `iframe`, CSS `style`, external assets, and hidden overflow are blocked.
- Compare the SVG preview to the blueprint at full-page and high-density regions. Check title, key numbers, tables, connectors, icons, annotations, and footer alignment.
- Production runs require a passing `high_density_build/reviews/<page_id>.visual_review.json`. Fixture and dev runs may use the deterministic review adapter.
- The review records the current SVG and blueprint hashes; a stale review is rejected before PPTX compilation.
- The review must report `text_masked_ssim >= 0.92` and `bbox_max_delta_px <= 2.0`; PPTX readback allows at most `0.75 pt` per P0/P1 bbox edge.
- Any P0/P1 overflow or unresolved visual drift blocks the page and returns a stage-specific retry command.

### 5. Editable PPTX And Readback

Compile all approved scenes into `high_density_build/pptx/deck_high_density.pptx`.

- Keep text, rectangles, lines, supported paths, and registered assets as editable objects.
- Registered assets must use a Page Package `asset_bindings` entry with `approved: true`, a run-relative PNG/JPEG path, and a matching SHA-256. Reference them from a scene with `asset_ref=<asset_id>` and `asset_policy=registered`.
- Full-page image wrappers, external image URLs, unregistered assets, and stale asset hashes stop the build with `HD_ASSET_POLICY_BLOCKED`.
- Preserve one documented px-to-slide-unit transform.
- Write `high_density_build/traces/pptx_trace.json` and page traces so every output object maps to a scene element.
- Run OOXML readback for slide count, speaker notes, P0/P1 text, geometry, and image relationships.
- A failed readback blocks the build with `HD_PPTX_EDITABILITY_FAILED`.

### 6. Canonical Handback

On completion, write and validate:

```text
high_density_build/high_density_manifest.json
build/build_manifest.json
build/artifact_manifest.json
render_results/render_result.json
```

`high_density_manifest.v1` carries internal lineage. The canonical artifact and render manifests carry only final PPTX and page preview artifacts and use run-relative paths. The next stage is `deck-quality`; high-density self-review does not approve final delivery.

## Agent Continuation And Recovery

When an Agent action is required, return `awaiting_agent_build` in `high_density_build/status.json` with the exact page, stage, input, output, and resume command. The canonical build manifest remains `building` during this state.

Inspect progress with:

```bash
deck-master build status --run-dir <run_dir> --profile high-density --watch
deck-master next-step --run-dir <run_dir>
```

Retry one page or stage after repairing its artifact:

```bash
deck-master build retry --run-dir <run_dir> --profile high-density --page-id P001 --stage svg
```

Use the stages `content_lock`, `blueprint`, `page_scene`, `svg`, `visual_review`, `pptx`, `readback`, and `handback`. Never route a high-density run through `awaiting_external_render` or `import-render-result`.

## Completion Gate

The run is complete only when all of these are true:

- every Page Package has a current content lock;
- every page has an approved blueprint, valid scene, native SVG, preview, passing visual review, and page trace;
- P0/P1 text and geometry pass readback;
- PPTX contains native editable objects and no whole-page image wrapper;
- all four lineage and canonical handback contracts validate;
- `deck-quality` can consume the canonical handback.
