# RC3-03 independent regression review — round 7 / F9

**Verdict: PASS within the reviewed F9 repair and selected compatibility scope.** No new defect was found in this scope. This is not a full-suite, installed-release, actual-image, E2/E3, desktop, human or overall RC3 acceptance verdict.

Reviewer `/root/rc3_03_regression_review` is not an implementation author. I read the original 5db reproducer script to understand its trigger, the new five-file diff and its tests. I did not read another reviewer's F9 conclusions or borrow Owner/Root results as my own.

## Fixed source and integrity

- Immutable snapshot `/workspace/work/rc3/reviews/rc3-03-code-snapshot-cf61e5e`.
- HEAD `cf61e5e717fc852263b5a5baf4d97a07e126362b`; tree `96188d691ced737113019aea4a61a769812f6794`.
- Reviewed against `5dbdf72089d6625449a23a52ef3e23859c597b4e`: production, visual dependencies, candidates, styles and one dedicated test file.
- Python `/workspace/work/rc3/reviews/env-03-snapshot-cf61e5e/bin/python -I -B`. Core, production, candidates and visual-dependencies origins explicitly resolve within this snapshot's src tree.
- **All 2,914 tracked file SHA256s unchanged before/after; identical HEAD/tree and clean Git status.** No source/install/actual-project edits, commit, push or merge. My new scripts, temporary projects, raw logs and report are confined to this review directory; the inherited short TMPDIR uses the existing scratch location `/workspace/work/rc3/t03r6`.

The repair collects the current head once per actual Decision identity before scope/topic filtering. Full consumed-design comparison retains actual semantic Decision identity plus registered effective digest while leaving original audit Refs in the immutable basis. Modern blueprint freshness now performs that full comparison before the manuscript-identity shortcut. Candidate compatibility reuses its frozen encoding only when the complete normalized current design equals that actual frozen context; it does not accept an arbitrary alternative digest. All changed call sites supply the Store used to validate immutable Decision objects.

## Independent targeted execution

**217 PASS, 0 FAIL, 0 SKIP, 77.16 s; exit 0.** Counts from my own JUnit output on this exact source:

| File/scope | Passed |
| --- | ---: |
| New Decision visual-consumption repair | 24 |
| F7/F8 adopted-design handoff and first-adoption gate | 41 |
| Preproduction semantic consumption | 23 |
| Earlier explicit prompt/classic compatibility repairs | 6 |
| Notes/visual inputs | 34 |
| Late results, stops and retained call facts | 13 |
| Exact/conflicting/corrupt committed receipt recovery | 12 |
| Existing candidate transactions/recovery | 19 |
| Synthetic native-controller reuse/control cases | 32 |
| Restyle references, scope, budgets and fees | 13 |

Command used the absolute Python above, `-m pytest -q -p no:cacheprovider`, those ten files, private basetemp `pytest-temp/` and JUnit `targeted.xml` in this directory. env.sh supplied tools/cache paths, with `PIP_NO_INDEX=1` and `PIP_FIND_LINKS=/workspace/work/rc3/wheelhouse`; no general editable Python was used. Raw log `targeted.log`, JUnit, before/after tracked hashes and explicit origins are retained.

F9 positives execute same-identity public Decision replacements before context, after context and after candidate receipt while keeping old frozen request/candidate digest bytes. Negative cases execute value, page scope, layer scope, topic, disposition, status and different-identity changes, including a same-manuscript-identity case that must bypass no semantic check. The withdrawn-status case uses explicit schema-valid L1 fault injection; it does not assert a public status writer or real withdrawal instruction. Consumed and unknown late outcomes keep the sent-call ledger and refuse stale adoption. Same-effective-value Decisions with different identities do not collapse. Foreign/mismatched audit references are refused; unconsumed other-page/topic updates preserve P1 reuse. Received candidates become stale on genuine consumed changes and cannot be planned for adoption.

The F7/F8, legacy, content and receipt selection also verifies exact named claims/capabilities, no-claim refusal, terminal replay without fresh adoption, body/role/arrow/target/control changes, notes-only and unrelated-page reuse, classic original preparation/claim behavior, current preproduction review and cancellation/withdrawal history. Existing candidate all-or-none, cancellation, interrupted-adoption and restore cases ran on the new source. These results are independent executions, not the Owner's reported affected-suite count or a new full-suite claim.

All image/controller/authority fixtures are explicit synthetic L1. Artificial PNGs, JSONL or controller records used by tests do not establish that an actual image tool ran, a human approved anything or a professional image matched the manuscript.

## Five independent probe results

`independent-probe.py` executed a separate, public SDK transaction sequence with independent oracles, using only disposable synthetic L1 data. **Five checks PASS; exit 0.** It does not import the new F9 test's setup/oracles.

1. **Current head and audit identity:** create a real public style Decision, dispatch its fixed recipe Task, then record a legal same-Decision-ID `replaces` version. The resolver returns exactly the new head, original context retains the old Ref, full consumed values compare equal, and the unchanged manuscript identity does not stale the Task.
2. **Actual candidate plan/adopt after another audit version:** freeze/begin and settle an explicit synthetic controller result, receive its candidate, then legally replace the same Decision again with the same effective values. Candidate JSON and its exact original design digest stay unchanged. Public `candidates.plan` and `candidates.adopt` succeed without another call. Original frozen Request bytes remain identical. This exercises actual adoption, beyond merely reading candidate status.
3. **Real change despite unchanged manuscript identity:** open a reconstruction task from that adopted image, change only the Decision's value through the public writer, and verify manuscript `content_identity` stays equal while task freshness becomes false and current adopted-design resolution refuses changed consumed inputs. Thus the new fast-path ordering preserves a real semantic boundary.
4. **No arbitrary second digest:** a read-only contrast changes an executable density parameter in an otherwise equivalent context. `_recorded_design_basis` retains this changed full context and produces a different digest instead of selecting the frozen encoding. This is a helper-level diagnostic, not a fabricated candidate or production permission; public real-change candidate refusals are covered separately above and in the executed tests.
5. **Current content requalification remains possible:** edit the Page through the real SDK after the Decision change, then complete actual preproduction dispatch/claim/accept under the honestly declared synthetic `host_self` fidelity policy. Current content qualifies, but the old image/reconstruction stays stale. The original image allowance stays consumed, total external allowances remain exactly one, and original frozen Request bytes stay intact.

Script, log and exact JSON identities/results are retained as `independent-probe.py`, `independent-probe.log`, `independent-probe.json`. This reviewer called zero actual image tools and created no actual-pilot native SVG.

## Remaining boundaries

Only this new source and my own runs support this scoped PASS. I did not run or claim a new full unit/render/browser/CI campaign, execute the offered installed release, or borrow its 256-byte-match result. Prior failed reproducers, earlier limited PASS reports and their source-specific counts remain preserved and are not rebound here.

The actual 5db pilot's image, consumed fact, page-visual records and later engineering outputs are separate historical evidence; no actual Project, original PNG, old Task or installed bytes were modified or reclassified. The F05 physical-size helper issue was not evaluated or repaired by this review. Neither engineering fixtures nor an actual engineering singleton constitute a fair full E2/E3 comparison, human audience evidence or desktop acceptance.

Overall readiness still requires the appropriate exact-head broader checks and remaining actual effect/delivery gates. This report signs only the F9 five-file delta and **217 selected tests plus five independent probes**.
