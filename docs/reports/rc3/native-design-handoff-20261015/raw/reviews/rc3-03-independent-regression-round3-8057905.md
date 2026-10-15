# RC3-03 independent regression review — round 3

**Verdict: PASS for the incremental Plan-consumption repair and affected engineering regressions.** Reviewer `/root/rc3_03_regression_review` is not an implementation author. Actual image design/effect, human/desktop acceptance and whole-release readiness remain outside this verdict.

## Identity and change boundary

- Immutable source `/workspace/work/rc3/reviews/rc3-03-code-snapshot-8057905`.
- HEAD `8057905162f20926cfc1a0a96252bc6745f4e700`; tree `dda627ebcaa016716ebba0be16288ab573ce1e82`.
- Compared with previously reviewed `5fa4834b3d07d1a0690ed53f8259d20572db7694`: only `src/deck_master/design_requirements.py` and new `tests/rebuild/test_rc3_plan_visual_consumption.py`, 78 insertions/1 deletion.
- Absolute Python `/workspace/work/rc3/reviews/env-03-snapshot-8057905/bin/python -I -B`; explicit origins for core, design requirements, visual dependencies and content review resolve under this snapshot's src tree.
- Source before/after HEAD/tree/status identical and clean; **all 2,912 tracked file SHA256s unchanged**. No source, method, contract, original material, HOME or historical-review mutation; no push/merge.

The implementation excludes only `speech_policy.source` from the consumed global Plan projection when **both mode and output are `none`**. It deep-copies the policy and leaves the actual complete policy in the immutable Plan. Every other policy field, active mode/output/source, global structure and relevant roles remain in the shared projection. Legacy Plan v1 behavior is unchanged. This is a narrowly bounded consumption change, not migration, permission or acceptance-source rewriting.

The shared projection reaches requirements basis, visual task/recipe freshness, and editorial preproduction equivalence. That shared use is why affected notes, semantic/global invalidation, native-result admission and authorization/budget checks were rerun on this exact new source.

## Independent executions

**164 targeted PASS, 0 FAIL, 0 SKIP, 34.85 s**, process exit 0:

| File/scope | Passed |
| --- | ---: |
| New Plan visual-consumption scenarios | 4 |
| Design requirements resolver | 58 |
| Preproduction semantic consumption | 23 |
| Native-controller visual reuse/control negatives | 32 |
| Restyle references/scope/budget/fees | 13 |
| Inherited notes/visual input behavior | 34 |

Command used the absolute Python above, `-m pytest -q -p no:cacheprovider`, those six files, independent basetemp `/workspace/work/rc3/t03r3/regression-r3` and private JUnit output. Short TMPDIR `/workspace/work/rc3/t03r3`; tool/cache settings from env.sh; offline package settings. Raw `targeted.log` and `targeted.xml` are in `/workspace/work/rc3/reviews/rc3-03-regression-round3-8057905/`.

The new positive scenarios exercised a real Plan-version change from absent-speech `source=default` to `source=provided`, both before and after sealed-controller context issuance: current Page visual basis remains usable, the old fixed Request/basis still refers to its original Plan, synthetic completion settles consumed, and the result stays a candidate. Actual speech output/mode changes still stale visual inputs and reject native-result admission while keeping call facts. Active speech provenance remains a consumed dependency.

Affected negative regressions also executed selected Page body/role/arrow/target changes, global progression/order/time budgets, pause/revoke, late consumed/unknown results, budget exhaustion, scope replacement, exact original reference order and candidate-only behavior. Original Request bytes, review records and call facts remain retained. Notes-only and unrelated P2 design/body changes retain only the allowed P1 reuse. These are engineering observations over explicit synthetic L1 content/authority/reviews/controllers, not genuine image-model completions or professional approvals.

## Independent boundary matrix

`policy-boundary-probe.py` added **12 independent policy checks, all PASS**, across all schema-valid mode/output pairs:

- modes: `none`, `cues`, `verbatim`;
- outputs: `none`, `separate_script`, `pptx_notes`, `both`;
- each pair compared `default`, `provided`, `delegated` sources: **36 original stored Plan variants**.

Only the exact `none/none` pair produces source-equivalent consumed projections. All other 11 pairs retain source dependency, including active mode with output `none` and mode `none` with an active output. Each original Plan retains its actual source, all three original Refs per pair remain distinct, and the projection does not mutate any Plan. This is a synthetic L1 schema/consumer diagnostic; it does not endorse all mode/output combinations as meaningful real product requests.

Raw executable/log/JSON: `policy-boundary-probe.py`, `policy-boundary-probe.log`, `policy-boundary-probe.json`. It makes zero external/model calls and grants no new authority.

## Limits and attribution

No new defect was found within this incremental regression scope. Existing round-1/round-2 raw results and verdicts remain attributed to their original source SHAs; **238+2+10 from round 2 is not reattributed to this HEAD**. This round's own totals are 164 targeted plus 12 boundary checks.

As requested for this two-file repair, I did not rerun unrelated UI, broad suites, wheel installation, CI or native compile/render samples. No actual `image_gen` was called. Genuine controller/image integration, content-qualified representative pilot, E2/E3, installed candidate, selected-artifact delivery, human audiences, target desktop editing/notes and final original-scope audit still require their separately recorded outcomes. This PASS signs only the reviewed source delta and the explicitly executed engineering checks.
