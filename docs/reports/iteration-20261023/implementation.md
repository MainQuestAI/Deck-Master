# S1 / S2 implementation and S3 preparation

## Authority and baseline

Development follows the approved `Deck-Master-Next-Iteration-Review-and-Spec-20261023.docx` (Library `libfile_18d4bd3426d4819193fbe3810d7cae09`, all 1213 extracted lines read). S4 bidding is excluded. No remote push, merge, release, customer production or paid model batch is authorized here.

The ZIP download helper failed, including one normal local-target retry. The supported Library text fallback was read completely: 8548 lines, 417642 UTF-8 bytes, SHA256 `2f9b39a7e74716197b8982df34da40e5aa6236f19279d50aec44425297be47e9`. Applying it to `fdb8fca959a40d54e8cc2e4881533473a1838657` produced tree `13f925e917955262c97907f3065c445087cb07b2`. Local restore commit `6797b207` establishes source-tree equivalence to the reviewed 601 candidate, not possession of that commit or its original ancestry. The four previously verified narrow fixes were retained, not reimplemented.

## S1 contract and acceptance mapping

`current_work.py` composes existing completion, scope, review, eligibility and workbench action facts. It stores no second state machine. The reader pins artifact/control snapshots once. Default summary v1 and existing Host context shapes remain unchanged; summary v2 is explicitly negotiated by CLI, API, UI and four Skill readers. Create/continue/accept can request a separate post-action observation; a failed observation preserves the mutation result and instructs read-only recovery of the original operation.

Current actions sort by: verify execution, inspect failure, reconcile inputs, replan, handoff, compare candidates, read results, review quality, refresh stage, prepare stage; stable action ID breaks ties. Recovery takes precedence over output completion and outline review. Unrequested layers and historical production actions remain optional facts. Unknown scopes do not generate production instructions. Both UI surfaces consume the same projection, including role, primary action, remaining actions and evidence. Primary action navigation does not grant execution authority; normal permission, basis and CAS checks remain mandatory on writes.

Presentation distinguishes address availability, open attempt and system acceptance from frontend load and user visibility. The latter remain unknown unless actually observed. Authorized source browsing is distinguished from formal adoption in the canonical Skill guidance.

Tests: `test_current_work.py` covers read purity, protocol compatibility, CLI/API/Host equality, fixed historical snapshots, mutation observation failure, scoped requests, recovery priority and real Chromium rendering on both surfaces. The seven request categories are outline, manuscript, design plan, sample, full deck, local edit and history; existing X3 tests supply the design-plan cases. Fixtures are synthetic, not actual user content or independent capability evidence.

## S2 contract, recovery and acceptance mapping

Outline is an explicit `review_subject` within existing preproduction Review. It requires valid nonempty current Narrative and ContentPlan with matching project and narrative reference. Its only units are argument/progression. Empty pages are legal only for this subject and never mean whole-manuscript approval. Accepted records retain the original receipt/identity checks and exact Narrative/Plan dependency references. Outline records cannot satisfy manuscript gates or grant visual-production eligibility.

Deduplication considers subject, current Narrative/Plan/input basis and exact unit set. A matching active task is reused; a stale or differently scoped active task returns awaiting_recovery. Query its original execution/operation and use existing retirement/reissue before proceeding. No new paid execution is created to resolve an unknown result. Separate findings retain owner, ID, replaces and recheck semantics; null-page outline findings close only against changed current Narrative/Plan evidence in the same subject. Changing a version invalidates applicability.

Dispatch rechecks existing eligibility. Independent review unavailable yields a readable draft and needs_reviewer without dispatch or document writes; it never falls back silently to host_self. The new persisted subject raises the writer floor to outline-review.v1. Runtime schemas have exactly one byte-identical spec mirror each. Old task/review defaults remain unchanged.

The Master Skill orchestrates early review within existing authority/budget/capabilities using the explicit outline entrypoint. Legacy core continue behavior is preserved; a summary read never initiates review. Native review accepts explicit outline subject and uses the original operation recovery transport. Real automatic Host orchestration and real independent review remain not_run because native initialization failed before a model turn. The synthetic dispatch/claim/accept and finding tests prove contract mechanics only.

## S3 bounded experiment preparation

`tools/prepare_s3_experiment.py` creates 24 anonymous diagnostic items (12 problem/protected pairs), a separate withheld answer key, a stable randomized order and an execution manifest. A/B author resources are frozen from a supplied baseline commit with per-file hashes; reviewer inputs contain no answer labels. Both groups use identical facts/resources. A varies existing defaults; B varies method selection, continuation and co-creation. C is disabled until an observed B defect justifies one targeted addition.

No unvalidated naturalization rewrite was added to default methods. Conditional C candidates are: preserve factual strength and necessary limits when rewriting; require a concrete action/evidence progression rather than only labels; carry user experience into recommendation, body and diagram with explicit before/after comparison. These are hypotheses, not demonstrated improvements. Q10/Q12 additionally require real pixels and editable PPT objects, currently absent. First draft, first review, repairs, recheck, model/prompt/resource identity and actual usage must all be retained in a real run. Execution denominator is zero. No false-positive/false-negative rate or human comprehension result is claimed.

## Environment and boundaries

A read-only native session probe failed during initialize (ProviderUnavailable / tool_failed, process exit 1). It made no model call or Review. This does not independently establish the previously reported sqlite root cause or prove it repaired. Render doctor reports rsvg-convert unavailable; preview reconstruction and target-customer rendering remain unverified. No credentials, security settings or access scope were changed. No extra image calls or RP-24 Host identity/settlement evidence were created. Final candidate build/install/browser evidence is recorded separately in validation.md.
