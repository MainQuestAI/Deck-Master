# High-Density Builder v2 Migration

Date: 2026-08-08

## Migration Rule

High-Density Builder v2 does not upgrade v1 process artifacts in place. Keep the old run for audit, then start from validated Page Packages and run high-density prepare again.

The Page Package remains the fact source. Existing v1 content locks, blueprint manifests, page scenes, visual reviews, traces, readback reports, and high-density manifests can be recognized for preview or migration diagnostics, but they cannot satisfy v2 completion gates.

## Required Steps

1. Preserve the existing run directory as read-only evidence.
2. Verify every Page Package is valid, unique, `ready_for_build`, and bound to the current run ID.
3. Run high-density prepare to create v2 build state and style-selection artifacts.
4. Approve one of the eight fixed style locks for production.
5. Let the Agent write two or three `deck_nbb_plan.v1` storyline candidates.
6. Record the user-selected storyline with `build retry --stage content_lock --storyline-id <id>`.
7. Let the Agent enrich only the selected storyline; the runtime validates and seals it before writing `deck_content_lock.v2` artifacts.
8. Regenerate prompt, blueprint, Scene, native SVG, PPTX, visual review, readback, and handback artifacts.
9. Run `next-step`, Deck Quality, and final readiness against the new run.

## State And Action Changes

NBB selection uses three states:

- `pending_user_decision`
- `selected_pending_enrichment`
- `approved`

Agent continuation uses two separate NBB actions:

- `agent_nbb_candidates`
- `agent_nbb_enrich_selected`

The storyline selection action records user intent only. It does not create, refresh, or overwrite Agent-authored SCR or page plans. The selection is valid only with `nbb/selection_receipt.json`, signed by the Runtime and bound to the candidate set, evidence ledger, selected storyline, and Page Package hashes.

An approved NBB plan is valid only with the matching signed `nbb/runtime_seal.json`. Editing the plan, selection receipt, or any Page Package invalidates that seal and blocks Content Lock generation.

Blueprint prompts now contain a signed provider challenge that fixes the original run mode. A completed provider result requires a second signed receipt bound to the prompt, request metadata, approval, and image hash. Existing unsigned provider evidence must be regenerated from a fresh provider call.

Production visual review now starts from a signed Runtime challenge. Producer self-review and main review must use separate action IDs and reviewer IDs, carry the current SVG/blueprint/metrics hashes, and preserve main-to-self review lineage.

## Invalidation

A Page Package change invalidates the deck-scoped NBB plan, all content locks, prompts, blueprints, scenes, SVGs, PPTX artifacts, visual reviews, traces, readback reports, and canonical handback artifacts.

A style-lock change invalidates prompts and every downstream visual artifact. A visible SVG change invalidates DrawingML, trace, render comparison, readback, and handback. A Scene-only visual mutation cannot alter PPTX geometry or rendering.

## Failure Policy

- Malformed or stale Agent NBB output returns the matching Agent recovery action and cannot create a content lock.
- Unknown storyline IDs keep the run in the user-decision state.
- Unsupported SVG elements fail before compile with the element ID, unsupported property, and recovery command.
- Missing renderers, Python packages, schemas, or fonts block capability readiness.
- Missing PPTX pages or failed batch rendering blocks readback and handback.
- Visual parity failures return SVG repair and cannot enter completed.

## Compatibility

- The standard profile retains its existing contracts and remains the default.
- Fixture/dev may auto-select deterministic NBB and style inputs for reproducible tests.
- Production and benchmark modes cannot use fixture fallback or placeholder provider evidence.
- OfficeCLI remains optional after the core PPTX has passed readback and visual gates.
