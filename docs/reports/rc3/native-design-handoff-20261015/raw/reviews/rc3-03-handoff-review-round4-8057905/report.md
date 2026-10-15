# RC3-03 independent actual handoff review, round 4

Verdict: **REQUEST_CHANGES** for the installed `8057905162f20926cfc1a0a96252bc6745f4e700` candidate. This is an independently reproduced actual SDK handoff failure, not a synthetic image/provider test and not an E2/E3 or human acceptance verdict.

## Observed identity and immutable evidence

- Source tree: `dda627ebcaa016716ebba0be16288ab573ce1e82`.
- Installed wheel: `dacfcf0ca16801d16c2dc082a2cde8e1041b6dc4054e4b2c3bfaac130a1a05a3`.
- Interpreter: the candidate's own isolated installed Python, with `-I -B`; module path checked against its installation manifest.
- Actual project: `native-image-pilot-03/run-02-project`, current revision `1056a6311ca4452b9b03b898906b1515`.
- Pending actual reconstruction Task: `6626b919b45f`, only `p04`, status `awaiting_host`; actual `tasks.task_inputs_current` returns true.
- Actual adopted blueprint: `dc12785b9efa870484a4eb578eef8859880b6d3769c363fa928fe302ff577526`.
- Its owned provenance GenerationRequest: `85815c301b12ddf8d4f3e1c706ba5d8086674377e6217b70ce525b54596b83a7`. The Store verified its bytes; this observation independently recomputed the frozen input hash and checked that the Request's Page Ref equals the actual current p04 Ref.
- `capture_readonly.py` directly called the installed `service.task_summary`, `editing._current_artifact_digests`, `production.resolve_design` and `tasks.task_inputs_current`. It imported no fixtures, called no writer, invoked no image tool, and generated no SVG or model output.
- All actual project files and all installed package files have identical before/after byte counts and SHA-256. Full inventories and actual raw SDK outputs are retained in this directory.

## F6: frozen design is lost between adopted image and native reconstruction

The adopted image's actual frozen `input.design_context` has the complete `content_requirements`, `content_basis`, `recipe_parameters` and `recipe_overrides`. Its `styles[0].layout_notes` contains the actual compiled density, composition, spacing, lines and icons rules. The reconstruction Task's public `page_design_contexts.p04` drops all four fields and restores the create-time default layout notes.

This is not an inferred mismatch: the installed accessor's output compares **equal to the old `resolve_design(page, document.design_context, assets)` result**, and **unequal to the actual adopted image's frozen design context**. The Root's instruction happens to point to the frozen Request as extra reading; that does not repair the SDK's contradictory authoritative work order.

The same observed drift reaches the existing `style:p04` dependency. The installed `_current_artifact_digests` yields `5fb5e15f8b296b5a14c1817ce4f8b98a0d74b2b8f7ae0d1a095a384a603f11ee`, exactly the legacy-style fingerprint. Applying that same fingerprint algorithm to the actual frozen style yields `5feae6c67bc4c21745605da077be6f00940c2d8686117c12c266fa420ef95196`. This demonstrates conflicting consumption bases; it does not establish that a future rendered SVG has already failed, since the actual SVG and preview are still null.

Static consumer audit on the immutable source locates the shared boundary:

- `service.task_summary`: reconstruction/repair/review page design contexts and page_visual asset dependency list still call the legacy resolver.
- `editing._current_artifact_digests`: current page style dependency uses the legacy resolver; `page_visual_summary` also obtains assets through it.
- `tasks.accept` page_visual validation: independently computes its allowed asset dependency set from that legacy resolver.
- `pipeline.page_asset_paths`: materializes permitted SVG images from the legacy resolver for preview and native compilation.
- `candidates.generation_basis` and `visual_dependencies.visual_task_inputs_current`: the new stored requirement consumption is currently special-cased to blueprint generation, while SVG/reconstruction falls through to legacy design comparison.

The RC3-03 card requires actual Page → frozen prompt → blueprint → SVG → PPTX preservation, and lists mixed versions as failure. This handoff must be repaired before continuing the actual native SVG writer.

## Minimal repair boundary and re-review criteria

Use one read-only resolver for **the effective design actually consumed by the current adopted blueprint**, then connect the existing reconstruction, SVG asset materialization, page_visual summary/validation/dependency fingerprint and SVG freshness consumers to that same result. Retain the exact frozen recipe/rules and requirements, with immutable provenance Refs for audit; no Page rewriting, additional image calls, new control objects or next-card default-flow/Studio/install migration is needed for this repair.

The resolver must validate genuine owned Store Refs and the frozen Request schema/input hash, project/Page identity, and corresponding actual generation/task provenance. A supplied string, convenient current recipe or stale unrelated project's Request cannot become the source of design authority. An existing claimed new Request that is unreadable, hash-invalid, wrong-page/wrong-project or internally inconsistent must fail explicitly; catching it and silently taking the legacy branch would reproduce the defect. Genuine historical sources without the new contract must retain their actual old resolver behavior. An old readable GenerationRequest without RC3 content fields must be distinguished from a partially malformed new context rather than guessed from today's technical writer floor alone.

Preserve the RC3-02 dependency semantics: compare registered consumed Page/Plan/recipe values, not a whole historical Page Ref or mutable global revision. Notes-only changes and unrelated-page changes must retain legitimate visual reuse. Actual target Page/body/role/recipe/assets changes must invalidate only affected consumers. The original frozen Request, adopted image bytes, native observation, consumed allowance and Task audit identity must never be rewritten to make the repair look retrospective.

Required follow-up is an immutable new source freeze, targeted positive/negative regression evidence for this resolver and each shared consumer, and an independent rerun of the actual read-only work-order accessor against the preserved pilot project. The actual writer should resume only after the repaired work order exposes its complete effective design. No source/live project edits were made by this reviewer.

## Limits

One actual pilot image had already been consumed before this review; this review does not re-evaluate its native tool authority, fees or visual acceptance. There is no actual native SVG, PPTX or desktop result in this observation. No fair E2 comparison, full E3 qualification, Owner/audience test, desktop test, whole-deck delivery or RC3-03 closure is claimed.
