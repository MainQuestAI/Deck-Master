# RC3-03 independent regression review — round 5

**Verdict: PASS for the executed handoff engineering regressions only.** This is not overall merge readiness or the actual-pilot F7 signoff. Root reported a separate broad-suite failure still awaiting attribution; this limited PASS does not override it, the independent actual handoff review, or later gates.

Reviewer `/root/rc3_03_regression_review` is not an implementation author. No actual pilot Project, PNG, old Task or other actual-pilot file was modified or used as a fixture. I did not call an image tool or execute the actual native SVG writer.

## Frozen identity and reviewed change

Snapshot `/workspace/work/rc3/reviews/rc3-03-code-snapshot-9dc6619`; HEAD `9dc661989e930c9fc08d7d179390e7cc61d47748`; tree `495f23e60d386a4199d3861c676f0d926c7f6c48`. Delta reviewed against `8057905162f20926cfc1a0a96252bc6745f4e700`: ten files, including one new handoff test file. I read the preserved round-4 actual handoff REQUEST_CHANGES report to establish the observed defect and its stated repair boundary; I do not relabel that old failure.

The new owned-provenance resolver connects adopted blueprint design to reconstruction/repair/page-visual work orders, style/asset dependencies, SVG materialization and freshness. It reads the exact frozen recipe/context through the actual owning Task, Request and Attempt; checks project/Page/Ref/input-hash relationships; refuses malformed modern lineage rather than silently defaulting; and retains genuine legacy behavior. New visual consumers declare their required capabilities. Preproduction review continues to consume the current content stage rather than requiring an old image's frozen design.

Absolute interpreter `/workspace/work/rc3/reviews/env-03-snapshot-9dc6619/bin/python -I -B`; core, production, pipeline, service and editing origins explicitly verified inside this immutable snapshot. **All 2,913 tracked SHA256s are identical before/after; HEAD/tree/status remain identical and clean.** No source/contract/method edits, commit, push, merge, HOME change, original-material change or historical-evidence rewriting was performed.

## Independently executed tests

**167 PASS, 0 FAIL, 0 SKIP, 55.93 s; process exit 0.** No Owner/Root counts or logs are included in these results.

| Selected file/scope | Passed |
| --- | ---: |
| New adopted-design handoff | 29 |
| Existing page-visual gate | 15 |
| Existing native pipeline | 14 |
| Notes/visual inputs | 34 |
| Preproduction semantic consumption | 23 |
| Synthetic native-controller visual reuse | 32 |
| Earlier explicit prompt/classic compatibility repairs | 6 |
| Actual native relation/readback/render/editable files | 14 |

Command used the absolute snapshot Python above, `-m pytest -q -p no:cacheprovider`, those eight files, private `--basetemp=/workspace/work/rc3/t03r5/regression-r5` and private JUnit output. Short TMPDIR `/workspace/work/rc3/t03r5`; env.sh provided only tools/cache paths; offline package settings. Raw `targeted.log`, `targeted.xml`, `before.json`, `after.json` are retained under `/workspace/work/rc3/reviews/rc3-03-regression-round5-9dc6619/`.

Executed handoff positives covered full frozen context for reconstruct, repair and page-visual review, matching style fingerprints, direct versus change-plan capability declarations, asset materialization/SVG acceptance, legacy historical generation at a technical RC3 notes floor, first Page+SVG and combined Page/blueprint/SVG adoption, and no reinterpretation of closed generation observations by a newer reader. Fault cases covered missing Request, foreign project, bad frozen hash, wrong owner and partially stripped modern context. Notes-only, unrelated P2, absent-speech provenance, unused fonts, overridden default layout and a new sibling recipe retained the original adopted design only when applicable; selected body/role/arrow/font/target changes continued to refuse stale consumption. Existing scope, revoke/late, consumed/unknown and notes protections were exercised in the selected inherited tests.

Handoff image/controller/authority fixtures are explicitly synthetic L1. Their PNGs and events are artificial protocol inputs, not native image-model outputs or professional fidelity evidence. A formally accepted synthetic SVG in those tests is an envelope/consumption diagnostic, not a visual quality verdict.

## Independent complete content-requalification probe

One additional independently scripted probe **PASS**, process exit 0: `requalification-probe.py`, `.log` and `.json`.

It uses only a new isolated synthetic L1 project and goes beyond merely opening a review task:

1. Create a formally adopted synthetic blueprint and open its new exact-capability reconstruction task.
2. Make a real SDK Page title edit, making the prior image consumption stale.
3. Dispatch, claim and accept current preproduction records through the SDK under the honestly declared `host_self` fidelity policy, then verify current content qualifies again.
4. Confirm this content qualification does **not** revive the old image design or reconstruction Task. `resolve_page_design(..., require_current=True)` still rejects changed consumed inputs; claiming the old visual Task is refused with no current mutation.
5. Verify original Request, adopted image metadata/blob and Attempt hashes remain unchanged. The original author allowance is still consumed, its ledger is unchanged, and total external allowances remain exactly one.

This verifies the content-requalification/visual-freshness boundary without inventing independent review, human approval, a second call or an actual provider fee. The probe's synthetic controller was used only in its disposable project; the real pilot's preserved objects were not read into it or modified.

## Actual native files and limits

The 14 native sample tests on this source used the real compiler, CJK fonts, rsvg/LibreOffice render, DrawingML readback and programmatic edit/save/reopen. Same-text wrong row/column ownership, responsibility, source arrow and native-only arrow ending negatives remained located failures; legal geometry transforms passed. They are manually authored synthetic engineering SVGs/Pages, not actual pilot/image-to-SVG model output.

I inspected this run's actual positive native PNG: the four-node human-confirmation chain, two-row exception table, 10 ms unit and engineering-only qualification are visible. Relevant original and rendered files remain in the private basetemp; the positive sample's byte counts/hashes are indexed by `actual-native-render-files.json`. This proves the specified engineering sample, not target PowerPoint desktop or professional visual acceptance.

NOT_EVALUATED here: the actual pilot accessor/owned-Request result against the real preserved image, actual native SVG model writing, actual image tool, fairness/E2/E3, installed candidate, full unit/render/browser/CI suites, selected-file final delivery, human Owner/audiences or desktop acceptance. No broad failure was reproduced or waived by this limited selection. Older round-1/2/3 counts keep their original source attribution and are not added to this round's totals.

The independently executed scope is **167 selected tests plus one complete requalification probe**, all passing. Overall repair/merge readiness still depends on the actual handoff review and resolution of the separate broad result reported by Root.
