# RC3-03 independent regression review — round 6

**Verdict: PASS for the new first-adoption claim/capability gate and the executed affected regressions.** This limited verdict does not replace the primary handoff review's original reproducers, full unit/render/CI results, actual-pilot evaluation or whole-card acceptance.

Reviewer `/root/rc3_03_regression_review` is not an implementation author. The actual pilot Project, old Task, original PNG and its one consumed image call were not modified or used as fixtures. I called no image tool and did not execute the actual SVG writer.

## Fixed source and change

- Snapshot `/workspace/work/rc3/reviews/rc3-03-code-snapshot-5dbdf72`.
- HEAD `5dbdf72089d6625449a23a52ef3e23859c597b4e`; tree `1b69a05050c63d0a2fbc4aaac86350611ad9f504`.
- Delta against `9dc661989e930c9fc08d7d179390e7cc61d47748`: `tasks.py` adds nine lines to the first-adoption gate; the handoff test file adds twelve cases and factors shared fixture builders, for 41 cases in that file.
- Python `/workspace/work/rc3/reviews/env-03-snapshot-5dbdf72/bin/python -I -B`; explicit core/tasks/production/generation origins all resolve within this immutable source's src tree.
- **All 2,913 tracked SHA256s unchanged before/after**, with identical HEAD/tree and clean status. No source, contract, method, HOME, original-material or old-evidence edits; no commit/push/merge.

The new guard applies to `changes.v1` consumers declaring `content_requirements_v1`, including direct consumers without `change_binding`. Their first adoption requires a running task, a named execution claim and the existing Host declaration/capability predicate. It sits after existing committed-receipt recovery and fact-settlement handling. Existing legacy/other-protocol paths do not receive a new generic claim requirement from this condition. Static review found this change consistent with its stated narrow boundary; the checks below exercised it independently.

## Executed selected regressions

**176 PASS, 0 FAIL, 0 SKIP, 59.84 s; exit 0.** These counts are my own executions on the fixed source above, not Owner/Root results.

| Selected scope | Passed |
| --- | ---: |
| Adopted-design handoff, including new first-adoption negatives/terminal replay | 41 |
| Late results, stops, withdrawal and call facts | 13 |
| Committed Task receipt recovery | 12 |
| Notes/visual inputs | 34 |
| Preproduction semantic consumption | 23 |
| Synthetic native-controller visual reuse/control boundaries | 32 |
| Earlier explicit prompt/classic compatibility repairs | 6 |
| Inherited page-visual gate | 15 |

Command used the absolute Python above, `-m pytest -q -p no:cacheprovider`, the corresponding eight files, private basetemp `/workspace/work/rc3/t03r6/regression-r6` and private JUnit output. Tool/cache environment came from env.sh, but the general editable Python was not used. Short TMPDIR `/workspace/work/rc3/t03r6`; explicit offline package settings. Raw `targeted.log`, `targeted.xml`, `before.json`, `after.json` are retained under `/workspace/work/rc3/reviews/rc3-03-regression-round6-5dbdf72/`.

The new tests cover reconstruct, repair and page-visual review: unclaimed, missing saved capability and missing execution-ref first submissions are refused without changing the current document; complete declared claims succeed; exact terminal recovery returns the original accepted receipt even after a synthetic terminal declaration fault, with no new content commit. That saved-claim fault injection is explicitly L1 test data, not an assertion about public mutation authority.

The inherited selection exercises actual original-protocol classic claims, Page/SVG acceptance, notes-only reuse, stale body/role/arrow/target controls, pause/revoke, late consumed/unknown facts, content qualification and exact/conflicting/corrupt receipt recovery. These remain distinct checks; passing receipt recovery does not grant new adoption/execution permission.

## Five independent public SDK probes

`direct-gate-probe.py` executed a new isolated synthetic L1 project, with no actual-pilot inputs. **All five checks PASS; exit 0.** Executable, log and JSON are retained.

1. A valid direct reconstruction envelope with no `change_binding` and no claim is refused with `claim the design consumer before returning its result`. The complete project filename/SHA256 map is identical before/after, including no new artifact/object/cache files.
2. A complete declared `changes.v1` claim with a real named execution then permits its first adoption. The actual stored task becomes completed with that execution identity.
3. Replaying the exact original terminal operation returns `already_applied` with the original accepted operation result. Every project file and its SHA256 remains unchanged; no new claim or adoption occurs.
4. Changing the terminal payload's artifact provenance description is refused. Complete project filename/SHA256 maps remain identical, rather than treating the previous receipt as permission to accept a different result.
5. A second direct consumer is cancelled before claim. Its first late submission records the existing late-settlement receipt and refuses the output; current blueprint/SVG stay unchanged. The next exact late repeat is refused with every project file unchanged. The original synthetic image author's consumed allowance remains byte-for-byte unchanged throughout.

The synthetic image/controller setup creates one artificial consumed image fact in its disposable project. It is an L1 protocol input, not a real model completion or fee; this reviewer made **zero actual image calls**. The probe's text-only SVG is a protocol artifact, not professional visual evidence.

## Limits and historical outcomes

No new defect was found within the reviewed nine-line product delta and the executed selection. The separate original first-adoption failures remain preserved at their old source and must be closed by the primary reviewer on this new source. Prior limited-PASS counts are not rebound to this HEAD.

I did not rerun unrelated UI, the complete unit/render suite, isolated installation or CI. Owner's earlier DNS/build failures and new full runs are neither counted nor waived here. No genuine native image integration, actual-pilot SVG, new native file/render sample, E2/E3, Owner/audience or desktop acceptance was evaluated. Overall readiness still requires the primary handoff review and the appropriate exact-head full checks; this report signs only **176 selected tests plus five independent SDK checks**.
