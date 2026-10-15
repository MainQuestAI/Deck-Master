# RC3-03 independent handoff repair review, round 5

Verdict: **REQUEST_CHANGES**. The actual frozen-context handoff defect is repaired, but the newly declared direct-consumer capability contract can be bypassed at acceptance. The two reproduced acceptance failures below block a PASS.

## Fixed review identity

- Source HEAD: `9dc661989e930c9fc08d7d179390e7cc61d47748`.
- Tree: `495f23e60d386a4199d3861c676f0d926c7f6c48`.
- Source: immutable `reviews/rc3-03-code-snapshot-9dc6619`.
- Interpreter: exclusive `reviews/env-03-snapshot-9dc6619/bin/python -I -B`, with actual imported module origins recorded in `verification.json`.
- This review independently ran the source tests, independent probes and actual project cold-read. No Owner test counts or diagnostic results are substituted for this evidence.
- All 2,913 tracked source files have identical SHA-256 before/after the review and the checkout remains clean. Tests only wrote disposable synthetic projects and this exclusive evidence directory. The actual installed-805 pilot project was accessed read-only.

## Own verification results

| Run | Result | Evidence and limit |
|---|---|---|
| New source handoff regression file | 29 passed, 15.32 s | `source-29-tests.log`; synthetic L1 SDK cases, no native model quality claim |
| Independent contract probes | **2 failed, 5 passed**, 3.84 s | `independent-probes.log`; real SDK transactions on disposable synthetic projects |
| Actual preserved 805 pilot cold-read under fixed 9dc SDK | PASS for handoff only | `actual-observation.json` and raw actual task/context/Request outputs |

The external independent pytest file did not inherit the repository's marker registration; its one `PytestUnknownMarkWarning` concerns a render marker imported from an existing setup helper. No render test ran in that probe invocation. No failure was converted to a PASS and no failed raw log was replaced.

### Actual F6/F7 handoff correction independently confirmed

The preserved actual project remains at revision `1056a6311ca4452b9b03b898906b1515`; Task `6626b919b45f` remains the original awaiting-host no-capability Task. Cold reading it with the fixed SDK now yields all 11 full-design keys. `page_design_contexts.p04`, the single-page `resolved_design_context`, `resolve_page_design(require_current=True)`, and the actual adopted image's immutable Request `input.design_context` are exactly equal. The source Request's input hash was independently recomputed. The rendering resolver agrees and `style:p04` now matches the full recipe-aware fingerprint `aea8ea4b43ab242f7f75a4bef462309c4e6df9795a535dd663ed208f76b74068`.

Every actual project file has identical before/after size and SHA-256, including the old Task, Request, original PNG, native observation and consumed allowance. No historical Task capability fields or execution attestations were rewritten or upgraded, and no closed native observation was reauthenticated against the new reader installation. This is fixed-source SDK cold-read evidence; it is not presented as a newly installed 9dc wheel run.

### Source and independently exercised boundary checks

The new shared adopted-design getter verifies owned artifact → Request → Attempt → author Task → stored preparation, retaining complete immutable context. Reconstruction/page_visual summaries, SVG asset materialization, style dependencies and SVG basis use this source. Synthetic source cases cover missing/foreign/hash-invalid/unowned/partial provenance rejection, real legacy pre-03 generation contracts, notes-only/unrelated-page/unused-font/overridden-default/speech-source equivalence, relevant body/role/direction/used-font/target changes, and formal `changes.commit` SVG handoff.

Independent probes additionally confirmed: stripping both modern Request and Attempt pointers does not downgrade to legacy; a combined visible Page/SVG change cannot borrow old adopted design; content-only preproduction work orders remain available despite a broken image Request; initial Page+SVG with no adopted image retains the proposed Page path; and new consumer dispatch does not deduplicate into a historical no-capability Task or rewrite that historical Task. These five checks passed.

## F8: direct modern consumers accept without their claimed capability contract

### F8a — no claim, no execution identity, accepted SVG

Exact failing case:

`test_direct_modern_reconstruct_must_reject_accept_without_claim`

The public SDK dispatches a new direct reconstruction Task with `protocol_version=changes.v1` and required `content_requirements_v1`, `style_recipe`, `style_recipe_v3`, without a `change_binding` (correct for a direct task). The probe never calls `task_start`. Its state is `awaiting_host`, `execution_ref=null`, `host_protocol=null`. A normal reconstruction SVG envelope nevertheless returns `accepted`; the Task becomes `completed` and its SVG is adopted. The test expected rejection and failed with `DID NOT RAISE`.

This first case uses no record corruption. The text-only SVG is explicitly synthetic contract data, not a native reconstruction or fidelity result.

### F8b — acceptance does not recheck recorded required capability

Exact failing case:

`test_direct_modern_reconstruct_accept_rechecks_recorded_caps`

The probe first legitimately claims the same new contract through `task_start`. In its disposable test project only, explicit fault injection creates a fresh Task record whose saved Host declaration omits `content_requirements_v1`, while the required-capability list retains it. Acceptance again returns `accepted`, completes the Task and adopts SVG. This independently proves the acceptance boundary does not consume the required contract even though the claim boundary checks it.

`capture_failed_probe_state.py` subsequently read both failed projects without mutation. The exact before/after Tasks, page slots and committed acceptance receipts are retained in the two `test_direct_modern_reconstruct*-raw-state.json` files and summarized in `failed-probe-observations.json`. The observations are real SDK outcomes over explicitly synthetic L1 data, never actual pilot results.

### Cause and minimal repair

`changes.validate_result` obtains `action_for_task` and returns immediately when a direct Task has no change binding; its `check_host` and running/execution checks occur only after that return. `generation.adoption_binding` likewise returns for this `changes.v1` Task because it is not a `generation.v1` image-generation Task. The generic acceptance path provides no replacement for either check.

Apply the explicit modern direct-consumer claim and capability check at the acceptance boundary that actually owns these Tasks: a matching saved supported protocol/capability declaration, running status and nonempty execution identity must precede adoption. Reuse the existing check, without fabricating a change plan/binding, upgrading historical 805 Tasks, or changing closed observations. Preserve idempotent terminal replay and existing call-fact settlement behavior. Re-review must cover direct reconstruction, relevant repair/review consumers and their positive valid claim paths.

## Scope limits

The previous installed-805 R4 REQUEST_CHANGES report remains unchanged. Neither the 29 source passes nor the actual full-context cold-read cancels F8. Owner's broader fixed-source checks are outside this review and cannot be inferred from these counts. There were zero new image calls, zero native SVG calls, no PPTX/render result and no fair E2/E3, whole-deck, Owner/audience or desktop acceptance claim. Native SVG execution must wait for the next frozen repair and independent PASS.
