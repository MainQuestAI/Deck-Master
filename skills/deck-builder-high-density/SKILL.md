---
name: deck-builder-high-density
description: Build or revise editable high-density Deck Master pages from locked page packages and approved SVG.
---

# High-Density Deck Builder

## Use When
The run uses the high-density profile and has validated Page Packages. For a selected-page change, read [local edits](../deck-master/playbooks/local-edits.md).

## Do Not Use
Standard-profile decks and standalone Office edits use their own routes. Blueprint text is not factual evidence.

## First Checks
Inspect build status if not already known. Reuse the approved storyline, style lock, packages, and valid page artifacts. Check capability readiness on first use or a dependency failure.

## Forcing Questions
Ask for missing storyline/style choices on a new run or an actual direction change. Existing explicit choices can be recorded and reused. Evidence and editability questions are resolved from the package and current contract where possible.

## Runtime Ownership
Deck Master owns lineage, stage batches, retries, compilation, and readback. Page Packages supply facts; approved SVG supplies the visual source. Scene is the semantic sidecar.

## Allowed Commands
```bash
deck-master build status --run-dir <run_dir> --profile high-density
deck-master build prepare --run-dir <run_dir> --profile high-density --output-profile production_pptx
deck-master build run --run-dir <run_dir> --profile high-density
deck-master build retry --run-dir <run_dir> --profile high-density --page-id P001 --stage svg
```

Run the returned acceptance and resume commands after completing the pending action. Read only the current stage in [stage protocol](references/stage-protocol.md): A for content, B for blueprints, C for scene/SVG, D for visual review, E for PPTX handback. Section F is for release acceptance.

Process current `pending_pages` and `rework_queue` using each task's actual input/output refs. Preserve completed pages. Default producer self-review uses a local receipt; independent review and external signatures follow the saved policy.

## Exit Artifacts
high_density_manifest, deck_pptx, artifact_manifest, render_result.v2, and current page readback evidence.

## Next Skill
deck-quality for the changed artifact's required gates.

## Stop Conditions
A required capability/input is unavailable or a reported contract error cannot be repaired within scope. Report its page, stage, and repair command. Complete available Agent tasks without asking the user to repeat authorization.

## Safety Rules
Keep run-relative paths and current hashes. Preserve claim bindings and business-number evidence. Ordinary structural titles, customer names, dates, and page metadata do not require business evidence. Reject whole-page image wrappers, hidden overlays, unregistered assets, unsupported SVG, and incomplete readback. Customer-visible output must exclude production annotations.
