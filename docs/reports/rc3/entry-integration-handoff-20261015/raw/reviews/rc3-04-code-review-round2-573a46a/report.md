# RC3-04 R2 independent source re-review

**CHANGES_REQUIRED.** The original independently demonstrated F1/F2/F3/F4/F6 are closed within this re-review's scope. All five original probes were rerun, and two finite related test selections passed (36 + 4 cases). The R2 natural-router change still misroutes the original Master coordination instruction (global F9); this was reported by B on the actual installation and independently confirmed here with a pure read-only call against fixed source. These findings do not constitute RC3-04/card, installed-package, human, or desktop acceptance.

## Fixed identity and boundaries

- HEAD `573a46a85bf93d71a13652756bc3a6cdb1fab6ae`, tree `135769e0b16d6397baa51b5c098425b9a80eb9ff`, parent R1 `7a8578baa210a92b92ae98922ff3236edf4d5975`.
- Source `/workspace/work/rc3/reviews/rc3-04-code-snapshot-573a46a`; interpreter `/workspace/work/rc3/reviews/env-04-snapshot-573a46a/bin/python`; actual imported module is the snapshot's `src/deck_master/__init__.py`, version `1.0.0rc3`.
- Read fixed AGENTS, original RC3-04/v1.2 specifications, preparation inventory and R2 handoff. Handoff SHA256 `129e9c4424391d47ab1b472b4a6f9493cda8eee29a26487655e19dde0bd651a6`.
- Source before/after: **3619 tracked files, identical bytes, clean status**. Both own identity JSON files SHA256 `287c71b43109099757580d5894498d82b221d1f6cdb694ae1d837d35818f5230`. This identity format differs from Root's supplied before manifest; no equality of differently encoded manifests is implied.
- R1 report remains untouched, SHA256 `002d53531ff471f2e408c79988653c753f5efd782093f5ef16bf87554c84eab3`.
- Reviewed the entire R1→R2 product delta: 22 runtime/schema/UI/example paths, retained as `product-delta.patch` and `product-delta-files.json`. Test/diagnostic changes were read where needed to assess the actual finite controls and fixture provenance. No product, tests, fixtures, originals, private oracle, or other arm's FINAL was edited/read outside the authorized scope; no sub-agent was spawned.

## Remaining must-fix: global F9

**Original Master natural instruction is routed to Content after the R2 negation correction.** Input:

> 请协调这次档案值班培训的策划与后续职责，先把真实范围和下一责任说明白，不制作整套PPT。

`src/deck_master/method_resources.py:191` removes the excluded `不制作整套PPT` clause, but its selection at lines 223–230 has no recognition of the affirmative coordination/responsibility request. The remaining noun `策划` selects `deck-content`; the result is `content_intent=plan_only`. This contradicts the original Master coordination path and the function's stated fallback for unclear/mixed responsibility.

Own evidence `F9-readonly-router-confirmation.json` contains the exact input, actual `deck-content/plan_only` output, imported source path and module SHA256 `1aecd96fac2a234d1ea762d99c6f523c3ae7e6cad9734a5959bc4a4d2ca107a3`. It is a pure read-only router call, not an installed Host run. Root/B separately supplied the actual installed `read_skill_methods('deck-master', entry_mode='natural', project=<real new project>, text=<same input>)` refusal, with raw setup stdout/stderr under `reviews/rc3-04-fixed-host-paths-573a46a/`. Their observation is attributed, not relabeled as our execution.

Fix must preserve this original Master coordination request and the already required finite genuine Content/Review/Design/session-resume controls; merely adding an explicit Skill name to the test input would not repair the natural path. Owner is handling the next fixed candidate. No additional language quota or expanded broad-suite requirement is introduced here.

## Original failure re-review

| Finding | Actual R2 observation and closure basis |
| --- | --- |
| F1 complete import bypassed narrow scope | Original two-page→p1-only import now raises `EligibilityBlocked`; both original pages and current control remain intact. `_manuscript_write_set` at `project_initialization.py:124` computes removals/additions/order and Page/Plan/Narrative/speech/constraint/output effects before staging; adoption uses the same normalized payload. Legal bounded p1 copy with unchanged p2 and legal explicit full-membership import both pass. Supplied outline cannot relax the actual Document hard page limit. **Closed.** |
| F2 historical same-source A→B→A resurrected request/credit | The retry returns `already_started`, the original A identity, `request_state=superseded`, `creates_request=false`, `refreshes_credit=false`; current B and its collaboration facts remain unchanged. `_matching_request_source` at `collaboration.py:326` searches committed ancestry, independent of derived caches. Closed/paused source does not reopen; a genuinely new explicit instruction at the same locator remains allowed. **Closed.** |
| F3 reconciliation adopted forged source identity | Original claimed input_revision result with nonexistent source/version/locator raises `EnvelopeError`; invalid output is not adopted and Document remains identical. `_accept_input_revision` at `content_production.py:1284` now reuses complete mapping and real-source validation for candidate Narrative, Plan, Page atoms and speech nodes before publication. Legitimate imported/null-Narrative copy without invented evidence passes. **Closed.** |
| F4 strict external-review gap appeared successful | Original source-only strict probe now retains its honest `needs_reviewer` report and returns shared HTTP409/CLI4. `collaboration_api.py:163` implements this mapping. Real public adapter invocation was used by the probe; no professional report identity was manufactured. **Closed.** |
| F6 delivery published after committed pause | Original deterministic lock-contention probe begins with synthetic ready facts, commits official pause while export is waiting, then releases the export lock. R2 refuses and publishes no delivery bundle; fresh paused export also refuses. The related revoke race passes. `exports.py:512` now acquires export serialization before the project lock, reloads and guards current control under that lock, and retains it through publication/copy; `_copy_bundle` at line572 stages then atomically renames visible destination. **Closed.** |

F2 raw stdout is deliberately retained unchanged and requires interpretation: the old probe prints `request_recreated=true` because it compares current B with original A, and computes a pure planner budget key for retained B. Those booleans do not describe the returned historical replay or an actual new call/fee. The full saved reply/current-state comparison proves A was not recreated. `original-probe-verdicts.json` records the actual closure assertions; no real fee, token or model consumption was inferred from planner keys.

The export race uses `_passing_deck` from the fixed `tests/rebuild/test_export.py`, explicitly **L1 synthetic** setup (helper SHA256 `1aaeae0cc3c9cc7158cbc9dfa2b868643edbbec76ad7e52863d7eee281fcc53e`). Actual OS locks and official pause/export APIs produce the race. It does not constitute real native rendering or professional/human approval. R1 originals, raw failures, and the original scripts remain intact.

## Affected product-delta checks and positive paths

| Delta | Independent source assessment and finite evidence |
| --- | --- |
| C1 v2 content-operation input/schema and derived lineage | Active plan schema references the actual v1/v2 input union; shared operation acceptance retains the same guard and actual derived identities. Merge/split lineage and recursive table/bullet edits pass selected existing operation tests. No immutable original contract was rewritten. |
| C2 Plan/source navigation, restore and honest imported basis | Actual Plan/Page links preserve source versions and historical basis; imported roles remain unverified facts. Navigation after lost acknowledgement/later edit and restore of an explicitly imported Plan pass. Candidate Narrative/Plan checks bind to their actual staged refs. |
| C3 bounded direct copy editing | Retained atoms keep real links; deleted atoms drop them; imported/null-Narrative unknown atoms can remain unknown. Authored Narrative requiring a new mapping still requires Host rewrite. Recursive body edit and stale retained original-basis controls pass. |
| C4 recovery of canceled reconciliation/old blueprint | Service catches only the specific old blueprint/content-basis incompatibility. Other errors propagate; a fresh dispatch still uses normal scope/pre-review/credit gates. Canceled input_revision recovery uses its real current server-built context before guarding. Recovery-once, retired-task/change-reason preservation and late-result refusal controls pass. |
| C5 settlement evidence and replay | Empty object/list/whitespace reports cannot fabricate settled invocation facts; exact existing receipt replay does not start a new attempt or upgrade native/fee facts. Adding genuinely missing invocation retains report provenance; changed report/invocation conflicts. New finite settlement module plus original synthetic native terminal-replay control pass. |
| Hard page limit/self-supplied outline | Limit is checked against actual resulting membership and the Document's Task fact, even if provided Plan max is null/larger. Selected explicit-outline rejection and legal full/bounded import positives pass. |
| Style-analysis basis and actual scope | Style analysis creates a real bounded Task under lock/CAS and actual grant. It binds registered style/font inputs while generic other Tasks keep manuscript binding. Unrelated Page edit stays legal; changed actual inputs refuse without writes/calls. Both selected controls pass. |
| Selected historical artifact/current control | Current policy is reloaded inside the export transaction. Historical selected artifact cannot reassert an old human-required/approved policy. Selected historical/current-policy control passes without claiming human approval. |
| UI/import adapters and example migration | Read complete changed public draft-intake, collaboration desk, launcher and CSS logic. Pure preview exposes actual required scope; request replacement and complete import are separate current-CAS actions. Non-2xx review payload preserves downloadable report. The synthetic W07 example now uses explicit bounded workorders/claims/fidelity and actual acceptance, with no production fixture fallback. Actual browser F5 acceptance belongs to the separate UI reviewer and was not executed here. |
| Four-Skill methods/routing | Canonical method-reader/manifest integrity path was reviewed; F9 remains in the changed natural router. Actual installed 16 paths, package-byte admission, F7/F8 lifecycle and Host consumption belong to Root/B evidence, not to this source-runtime check. |

Finite execution is reproducible from `execution-record.md`: five independently rerun original probes; `targeted-positive.log` **36 passed in 8.96s**; `targeted-recovery.log` **4 passed in 1.66s**. The selection spans legal narrow/full import, closed/paused replay plus genuine new instruction, honest null-Narrative edit, Plan history/restore, merge/split, recursive copy, generation settlement/replay, canceled Task recovery, style basis and selected delivery/current-control locking. These are software fixture/control results, not real provider/native or professional approval. No broad suite/render batch was run or borrowed as our PASS.

## Conclusion and exclusions

**Original five findings: re-review PASS within the recorded failure/positive scope. Fixed R2 source candidate: CHANGES_REQUIRED because global F9 remains confirmed.** This report does not close other reviewers' findings or Root's wider regression results. No merge/release/card acceptance is authorized by the finite passes.

Real human Owner/listener trials, PowerPoint desktop editing, real new model/native-image execution and new professional approval are **NOT_RUN/deferred**. Actual installed/browser/package proof is attributed to its executing reviewer. No scope, floor, immutable receipt or unknown fee fact was promoted by this review. Review work is frozen after evidence hashing; await only a new fixed-source follow-up for the remaining affected change.
