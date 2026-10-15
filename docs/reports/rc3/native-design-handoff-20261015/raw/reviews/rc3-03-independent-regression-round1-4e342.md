# RC3-03 independent regression review — round 1

**Verdict: REQUEST_CHANGES.** Reviewer `/root/rc3_03_regression_review` is not an implementation author. The new engineering and inherited browser checks executed successfully, but the actual frozen production prompt still instructs an unconditional missing-data schematic fallback that conflicts with the original RC3-03 scope.

## Frozen source and independent execution

- Snapshot: `/workspace/work/rc3/reviews/rc3-03-code-snapshot-4e342`.
- HEAD `4e342b81390186b8b090bc31ffa6af7bef46b165`; tree `7c801ed0f4383969c3169fa5868cba2ab47e459d`; base `da7bcbc97475d10907b0c795026af5652c3a95d9`.
- Interpreter: `/workspace/work/rc3/reviews/env-03-snapshot-4e342/bin/python -I -B`. Three explicit imported core modules resolved under this snapshot's `src/deck_master`; no live worktree product imports.
- Read AGENTS, task index, recovery playbook; original immutable RC3-03; original v1.2 CONTRACTS §11.4/11.4.1 and MIGRATION; current handoff preflight G01–G11 and native-image bridge G12. The files supplied acceptance scope; they did not independently authorize an image call or human signoff.
- Before/after HEAD and tree are identical; all **2,908 tracked file SHA256s unchanged**, and both Git status checks clean. No source edit, commit, push, merge, actual HOME modification, or original-material modification.
- Tools/cache setup sourced `env.sh`, but every Python execution used its explicit snapshot interpreter. Short TMPDIR `/workspace/work/rc3/t03r`; offline package settings; independent basetemp directories; pytest cache disabled.

All evidence below was executed by this reviewer. Owner broad-unit/render results and other agents' observations are not counted as my runs.

## Finding R1 — contradictory missing-data fallback enters the actual frozen prompt

**Priority: P1; fix before merging RC3-03.** `src/deck_master/production.py:247` unconditionally adds:

> If a chart needs data absent from the input, use an unlabeled schematic marked 示意数据, without plausible-looking values.

The original RC3-03 implementation item 6 explicitly disallows using a no-data decorative quantitative chart as a fallback; the preflight also called for narrowing this instruction. Appropriate qualitative teaching diagrams may be preserved when actually supported by the fixed manuscript. The current generic instruction makes no such distinction.

I created an isolated SDK `workbench.v3` project whose fixed copy explicitly requires a real ROI comparison, states that revenue/cost/time data are absent, and forbids a schematic quantitative substitute. Normal `continue` dispatched the blueprint task, `stored_blueprint_request` returned its real immutable preparation, and `generation.freeze` successfully froze that exact input. Its actual prompt contains both the fixed prohibition and the unconditional fallback quoted above. Thus the issue reaches production preparation and the immutable frozen request; it is not merely unused method prose.

The final probe's preparation is `286d91768a91dc30d9de6c992586c01fff926a6bb3c9f39b2c8691e3f26b7b95`; request `req-988bffa6877c495598dcb88ce3f0f74e`; actual first-write floor `rc3.v1`. The allowance remains reserved and **zero image tools were called**. Raw frozen JSON is under `rc3-03-regression-round1-4e342/probe-run3/no-data-frozen-request.json`; the first independent reproduction remains at the evidence directory root.

Requested correction: stop instructing a missing quantitative-data substitution. Direct a required-data gap back to content, preserve the supplied manuscript/qualifications, and limit any schematic permission to an explicitly supported qualitative/teaching use. Add a focused prompt/freeze regression proving the corrected instruction reaches the actual preparation/frozen input. This finding does not require inventing a general NLP completeness detector, and it does not assert that an uncalled model generated a bad chart.

## Executed regressions

Seven selected new RC3 files: **168 PASS, 0 FAIL, 0 SKIP, 30.88 s**. Breakdown from my JUnit XML:

| File | Passed | Main observed behavior |
| --- | ---: | --- |
| `test_rc3_design_requirements.py` | 58 | Full raw requirements, honest fidelity nulls, current mapping conflicts, consumed semantic/global/decision slices |
| `test_rc3_design_recipes.py` | 34 | Real target binding, no-old-image initial path, zero-call feasibility, seven executable dimensions, allowed overrides, fixed references |
| `test_rc3_design_workflows.py` | 2 | Two authorized initial pages arriving in reverse order remain candidates; unrelated auto prompt cannot freeze |
| `test_rc3_restyle_workflows.py` | 13 | True target first, original JPEG/PNG style bytes, exact frozen parameters, used versus unused font scope, budget/control changes and late call facts |
| `test_rc3_preproduction_semantics.py` | 23 | Same-text semantic negatives; legitimate layout and SVG geometry positives; page/unit versus global progression; isolated speech/notes effects |
| `test_rc3_native_image_bridge.py` | 24 | Sealed provider/context and exact frozen binding, invalid contexts, genuine-call ledger mechanics, pause/revoke/scope/target changes, exact settlement replay |
| `test_rc3_design_native.py` | 14 | Actual editable PPTX/readback/render, table row/column ownership, node responsibility, direction and native-only arrow-ending corruption, legal SVG transforms |

Command used absolute snapshot Python, `-m pytest -q -p no:cacheprovider`, those seven files, `--basetemp=/workspace/work/rc3/t03r/regression-r1`, and a private JUnit path. Raw command results: `targeted.log` / `targeted.xml`.

Two actual Chromium inherited panels: **2 PASS, 0 FAIL, 0 SKIP, 14.49 s**, with `--require-browser`:

1. Screenshot upload → analysis → confirmed spec → explicit trial handoff → project restoration, `test_visual_styles_browser.py::test_screenshot_ui_upload_reasoning_confirmation_dispatch_and_restore`.
2. Studio page-source style → compare → explicit adopt/expand/review, `test_studio_style_browser.py::test_studio_style_two_routes_compare_adopt_expand_and_review[page]`.

These are real Chromium and real core transactions with the tests' explicitly synthetic image/control/acceptance fixtures. They prove inherited UI transaction execution, not real image design quality or human approval. The tests' page-error lists were empty. Raw evidence: `browser.log` / `browser.xml`. No v3 UI implementation was claimed or required by this unchanged static UI surface.

## Additional independent probes

`independent-probes.py` used the installed snapshot SDK and test-sibling fixture constructors only. Its own oracles and transaction sequence are separate from the selected tests. Final complete run: **5 PASS, 1 product FAIL**, where the product FAIL is R1 above.

- **Actual frozen A0 CLI refuses new floor:** `continue` and `task start` were invoked with `/workspace/work/rc3/baseline-a/venv/bin/python -I -B -m deck_master` against the new RC3-floor project. Both exited 4 with `current.json: unsupported minimum writer; use the matching core`. Complete project-file hash maps remained identical before and after each command. These are real old-core executions, not monkeypatched writer ranks.
- **One-call authorization cannot commit two pages:** a two-page planning recipe under a one-call/one-candidate L1 grant failed atomically with `budget_exhausted`; current pointer and existing Task refs stayed unchanged, no new Task/reservation committed, zero tools invoked. The tentative in-memory first reservation did not leak into the committed ledger.
- **One-page candidate and exact capabilities:** the same grant legally dispatched one candidate-only Task with exactly one `content_requirements_v1` and the explicit `style_recipe_v3` capability. A Host declaring only the older capability set was refused before claim mutation. No candidate was adopted or model called.
- **Complete raw material through actual getter/freeze/begin:** seeded raw multiline density rationale and qualification containing `54/120=45%`, noncausal and non-savings limitations survived exactly across stored projection, generation input, and parsed literal prompt. `content_basis` was absent from the prompt. Actual formal Task claim, request freeze, and SDK call begin succeeded; its ledger is honestly `in_flight` because no tool invocation/completion was performed. This SDK-begun synthetic probe is not a real image call or a completed native event.

Final results and exact identities are in `probe-run3/independent-probes.json`, with frozen requests and actual old-CLI stdout/stderr. All controller/authority/review fixtures in the selected files and additional probes are **synthetic L1**. No self-labeled JSON is presented as a real native/model/human observation.

## Native file observations and limits

The 14 native tests exercised real compiler, font resolution, rsvg/LibreOffice render, PPTX XML readback, and programmatic edit/save/reopen. Their synthetic manuscript uses a four-node human-confirmation chain plus a real three-column exception table, a 10 ms unit, and an explicit engineering-only qualification. Original SVG/native PPTX and positive/negative renders remain under the private basetemp, indexed with actual byte counts/SHA256 in `selected-native-artifacts.json`. The broader `native-artifacts.json` is an all-selected-test JSON/image/native-file inventory, not a count of genuine image-tool outputs.

I visually inspected my actual native positive PNG and the wrong-row negative PNG. The positive presents four clearly labeled left-to-right nodes, a two-row exception table, the 10 ms unit, and its limitation. The negative preserves the strings while exchanging the two exception actions across owners; the readback fails at the affected cell atom. This observation supports the precise engineering sample only; it is not a professional visual-design acceptance.

NOT_EVALUATED: actual `image_gen` completion/real bridge integration, real content-qualified representative-page pilot, E2/E3 effects, an installed 03 wheel, whole-deck final quality, broad unit/render/CI, original full-scope delivery, actual Owner or nonwriter human audiences, target desktop PowerPoint editing/notes acceptance. No AC-D/CQ or global release PASS is signed by this engineering review.

## Preserved harness failures

The first custom probe run correctly observed R1 and an actual unchanged old-core refusal, but my oracle initially recognized `minimum_writer` and not the returned phrase `minimum writer`, incorrectly labeling that refusal FAIL before aborting. Its raw JSON/stdout/stderr/log remain untouched. Run 2 corrected that oracle, then aborted because my additional “no Tasks” assertion overlooked an already-existing Task from fixture setup. Run 3 corrected the check to compare committed Task refs before/after the refused batch and completed all six probes. The first two are harness failures, not product regressions or spliced green runs; neither was erased or relabeled retroactively.

Product source remained frozen and unmodified through all runs. Re-review must target the eventual new fixed SHA; the successful 168+2 executions on this SHA do not override R1 or apply automatically to a later revision.
