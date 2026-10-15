# RC3-03 independent handoff and acceptance re-review, round 6

Verdict: **PASS for the reviewed F7/F8 repair and affected handoff/acceptance boundaries** on fixed source `5dbdf72089d6625449a23a52ef3e23859c597b4e`. The original round-5 REQUEST_CHANGES evidence remains unchanged. This is not whole-card, CI, native SVG quality, E2/E3 or human acceptance approval.

## Fixed identity and independent execution

- HEAD: `5dbdf72089d6625449a23a52ef3e23859c597b4e`.
- Tree: `1b69a05050c63d0a2fbc4aaac86350611ad9f504`.
- Immutable checkout: `reviews/rc3-03-code-snapshot-5dbdf72`.
- Exclusive interpreter: `reviews/env-03-snapshot-5dbdf72/bin/python -I -B`.
- All eight affected imported core modules resolve to this snapshot; actual origins and final source verification are recorded in `verification.json`.
- Every one of 2,913 tracked source files has the same SHA-256 before and after this review; Git remains clean. No live worktree was tested and no Owner result/count was used as this review's evidence.

## Own results

| Verification | Own result | Preserved evidence |
|---|---|---|
| New source handoff/claim regressions | **41 passed**, 22.97 s | `source-41-tests.log` |
| Original seven independent R5 probes plus ten acceptance/replay probes | **17 passed**, 9.91 s | `independent-17-probes.log` |
| Preserved actual 805 pilot cold-read using fixed source SDK | **PASS for handoff only** | `actual-observation.json`, full actual work order/context/Request and project inventories |

The original seven-probe file was copied byte-for-byte, SHA-256 `5da6c409fc4146b19e59185384103bc95c3506fb0dfa37b66b4f772b78d99c94`. Its two exact previously failing cases now pass by actually rejecting adoption:

- `test_direct_modern_reconstruct_must_reject_accept_without_claim`.
- `test_direct_modern_reconstruct_accept_rechecks_recorded_caps`.

The five other original checks still pass: stripped-modern-lineage downgrade refusal; visible Page/SVG changes cannot borrow the old design; content-only preproduction work remains accessible with a bad image Request; initial Page+SVG without image lineage retains the proposed Page path; and a newly dispatched modern Task is distinct from the old no-capability queue record.

## F8 acceptance closure

The nine-line product repair sits in the common adoption path after actual call-fact settlement and the shared eligibility judgment, and before writing any adopted result. It applies to Tasks explicitly carrying the existing `changes.v1` contract and `content_requirements_v1`, including direct Tasks with no `change_binding`. It checks actual `running` status, a nonempty execution identity and the existing `generation.check_host` declaration/capability validation. No fictitious change plan or new protocol was added.

Beyond the original two probes, independent disposable L1 SDK tests verify missing execution identity for reconstruction, repair and page_visual review; both unclaimed and missing-capability refusal for repair and page_visual review; and valid full-claim acceptance followed by exact terminal replay for all three kinds. Rejection leaves the current document unchanged. The 41 independently executed source tests also cover the full three-kind × three-fault matrix and retained consumed-call facts.

Exact terminal operation receipt recovery still precedes the new first-adoption check. Each independent positive/replay probe deliberately removes capability declarations and execution identity from a **disposable synthetic terminal Task after its accepted operation**, then verifies the exact original envelope returns `already_applied` with the original accepted revision. The current document, all file bytes and file membership remain identical before/after replay. Raw accepted/replayed responses, terminal records and complete file inventories are retained in `replay-reconstruct-observation.json`, `replay-repair-observation.json` and `replay-review-observation.json`. This proves no second authoritative adoption or duplicate call fact; it does not claim zero disk syscalls, because the inherited implementation refreshes its derivable journal cache with identical bytes.

Historical Tasks and already-closed receipts are not rewritten by this new capability gate. The exact closed-receipt and cancelled/late handling remain earlier in the acceptance flow. The fix neither grants an old Task a new capability nor reauthenticates its historical native tool receipt.

## Actual frozen-context handoff remains corrected

The actual pilot remains revision `1056a6311ca4452b9b03b898906b1515`, original awaiting-host Task `6626b919b45f`, with its old protocol/capability fields unchanged. The source Request hash is independently recomputed and all of these actual values compare exactly equal:

- Actual Request `input.design_context`.
- `resolve_page_design(require_current=True)` and `resolve_page_rendering_design`.
- `task_summary.page_design_contexts.p04` and the single-page `resolved_design_context`.

The context retains all 11 keys, including full `recipe_parameters`, `recipe_overrides`, `content_requirements` and `content_basis`; `style:p04` agrees with the actual complete recipe-aware rendering fingerprint `aea8ea4b43ab242f7f75a4bef462309c4e6df9795a535dd663ed208f76b74068`. `tasks.task_inputs_current` is true. The immutable adopted image remains SHA-256 `8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c`.

Full before/after actual project file inventories match byte counts and SHA-256, including the original Task, Request, PNG, native observation and consumed allowance. No fixture is imported into this actual cold-read script and no writer/tool is invoked against the real pilot. This is fixed-source SDK read evidence, not a claim that this review installed or tested a 5db wheel.

The source regressions preserve genuine legacy pre-03 generation behavior without inferring migration from today's writer floor, reject damaged/foreign/unowned modern lineage rather than falling back, keep content-only preproduction separate from visual consumption, and exercise notes-only/unrelated-page/unused-font/speech-source reuse together with relevant target/body/role/direction/used-font invalidation. The shared adopted design remains the source for reconstruction work orders, SVG assets, page_visual requirements and dependency checks, and SVG basis/freshness.

## Evidence limits and next boundary

All native-looking output used by the pytest setup is explicitly synthetic L1 protocol data. No image-generation or native-SVG model call was made during this review; no SVG fidelity, final PPTX, rendering, E2 comparison, full E3, Owner/audience or desktop result is claimed. The actual pilot remains unmodified and has no actual native SVG. Owner's broader fixed-source suite, installed candidate admission and subsequent actual native reconstruction have separate evidence and remain outside this limited PASS.
