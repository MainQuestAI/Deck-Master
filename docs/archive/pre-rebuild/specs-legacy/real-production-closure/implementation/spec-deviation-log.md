# Real Production Closure Spec Deviation Log

## Status

Initial A0 deviations are accepted as implementation-baseline decisions. No runtime behavior has changed in A0.

## Deviations

| ID | Planned | Actual baseline decision | Reason | Impact | Status |
|---|---|---|---|---|---|
| A0-D001 | Use target commands such as `contract-validate`, `release-build`, `release-smoke`, `final-readiness`, `build`, `artifact-status` | Keep current CLI commands as compatibility anchors; add target names only in the task that implements the behavior | Current repository already has working command names and tests around them | Prevents command churn during A0; later tasks must update docs and tests when adding aliases | accepted |
| A0-D002 | Use `awaiting_agent_execution` and `needs_generation_execution` directly | Freeze them as new target semantics; keep current states readable until A3/A5 migrate producers and consumers | Existing run-state and workspace code already depends on current states | Avoids breaking existing run artifacts; requires explicit migration tests later | accepted |
| A0-D003 | Planning pack includes schemas under `docs/deck-master-real-production-closure-spec-pack/schemas/` | Treat planning pack schemas as drafts; runtime truth starts in `docs/contracts/` | Repository already separates runtime contracts, capability contracts, and skill task schemas | Prevents duplicate canonical sources; later tasks must synchronize copies deliberately | accepted |
| A0-D004 | A0 asks for capability lock draft | Fold capability source facts into `baseline-lock.json`; create release capability lock in C1 | Current release lock belongs to packaging and source vendoring, which C1 owns | A0 remains documentation-only; C1 still owns release reproducibility | accepted |
| A1-D001 | Draft v2 schema represents `errors` items as strings | Runtime v2 contract accepts string errors and object errors with at least `message` | Existing runtime tests and v1 handback convention already use structured error objects | Preserves compatibility while allowing simpler producer strings | accepted |
| A1-D002 | Legacy v1 has no guaranteed `source_fingerprint` | During v1 migration, provided fingerprints are validated; missing fingerprints are replaced with the current run fingerprint | v1 producers cannot supply a value they never knew about, but current-run binding still needs a canonical v2 value | Keeps safe v1 migration; v2 producers remain responsible for explicit fingerprint matching | accepted |
| A3-D001 | A3 lists A2 as dependency | Implement Deck Master-side dispatch, receipt, and batch import first; PPT-Deck-Pro-Max bridge remains A2 work in the separate repository | User roadmap keeps A2 in `PPT-Deck-Pro-Max` after A1 contract acceptance | Deck Master can produce Agent packages now; full external bridge validation waits for A2 | accepted |
| A3-D002 | Move fixture adapter to test-only | Keep bundled adapter in `scripts/capabilities/` but gate it to `fixture` and `dev` run modes | Existing bundled capability discovery expects the script path; moving it would create packaging churn | Production cannot execute placeholder output; fixture smoke path remains available | accepted |
| A4-D001 | A4 expects the final renderer path to produce HTML/PDF/PNG/PPTX through PPT Master/native rendering | Add a deterministic Deck Master build runtime first, using Python stdlib to produce contract-verified HTML, PDF signature output, page PNG signatures, and a minimal PPTX package | A0 dependency inventory shows `playwright`, `pptxgenjs`, and `python-pptx` are missing; adding external render dependencies would increase closure risk in this iteration | Artifact contract, checksums, editability metadata, and build/render handoff are closed now; visual-fidelity renderer integration remains a later adapter task | accepted |
| A4-D002 | Existing render tool UAT only accepts `deck_render_result.v1` | Accept both `deck_render_result.v1` and `deck_render_result.v2` | A4 emits v2 while legacy fixture renderer still emits v1 | Old fixture results and new production build results can both pass UAT | accepted |
| A2-D001 | `deck-master-export` can be read as producing page artifacts itself | PPT-Deck-Pro-Max bridge exports only from existing assembled HTML and screenshot artifacts; missing artifacts fail the command | The production boundary should not create synthetic result assets during handback | Prevents placeholder leakage; callers must complete PPT-side HTML assemble and screenshots before export | accepted |
| A2-D002 | A2 full test command originally used system Python | Full PPT-Deck-Pro-Max validation uses Codex bundled Python because system Python lacks `python-pptx` | `python-pptx` is declared as a repository dependency and required by the existing PPTX layout tests | A2 evidence records both the system-Python failure reason and the bundled-Python passing result | accepted |

## Review Rule

Future tasks must append any material deviation here before merge. A deviation is material when it changes command names, schema ownership, run-state semantics, production/fixture policy, or required validation behavior.
