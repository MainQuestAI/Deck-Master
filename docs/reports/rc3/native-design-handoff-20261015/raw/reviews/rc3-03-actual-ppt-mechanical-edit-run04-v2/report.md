# Actual p04 v2: correct physical-size native edit and relation pairs

Result: **A–D meet the expected headless engineering outcomes on the actual corrected-size v2 artifact**. The actual baseline and layout-only recompile both retain the frozen 13⅓×7.5 inch dimensions and 18/30 pt typography. Same-text wrong-cell and reversed-arrow native copies are rejected by located checks. This is not PowerPoint desktop verification, professional visual-quality approval, fair E3 qualification or card completion.

## Fresh actual inputs and fixed reader

The original is the actual v2 engineering PPTX from `run-04-native-ppt-v2-correct-physical/native/deck.pptx`, SHA-256 `4c951dde9044506ad7cade8e06de13c50ed25e5173210265cd2b7c61d2c38ef6`. The actual author v2 SVG is `82d3430688b9c4ff2fb89cedb99cabfd643fbb39cb03d274b65a60a2de245ded`. The fixed Page remains canonical SHA `cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b`; the frozen design's Page basis matches that same identity.

Seven actual input files were copied into this exclusive directory: PPTX, SVG, fixed Page, actual source IR, original render, frozen effective design and source font-file declarations. All originals retain identical before/after sizes and SHA-256. No active visual-review report was read, and there was no actual-project writer, source change, image-tool invocation or model call.

The reader remains the admitted installed **5db** phase: source `5dbdf72089d6625449a23a52ef3e23859c597b4e`, tree `1b69a05050c63d0a2fbc4aaac86350611ad9f504`, wheel `94f6f31fcadf4e5a493b77b7dcefd7cebe43edc033f9268266fdba07eeb9ffb2`, its own interpreter with `-I -B`. Full installed admission before and after verifies all 256 package/resource files against the same fixed wheel. No result here is relabeled as the later F9/cf61 source phase.

This is a fresh observation. The prior `a6ae66e3…` report and its larger-size artifact are neither overwritten nor reused as corrected-size acceptance evidence.

## Independent baseline and physical typography

The real installed `pipeline.readback` was rerun on this original actual v2 PPTX, independently of Root's result: **pass, zero findings**. Actual counts are **60 native shapes, 36 text runs, zero pictures and zero media members**. All 428 native characters and complete Page notes are present.

Actual presentation dimensions are **12,192,000×6,858,000 EMU**, exactly matching frozen 13⅓×7.5 inches. Each of the 36 nonempty native runs is measured under its source-bound object name: the declared title and section-heading roles use 30 pt, every other body run uses 18 pt. Missing/unrecognized size or source binding would fail; this is not inferred from a global maximum. The complete run census and physical fields are preserved in `baseline-independent-physical-typography.json`.

## A — edit native text, save and reopen

The actual native title run was changed using `python-pptx`, saved to a new PPTX, and reopened through a new `Presentation` instance. The title exactly retains the deliberate `机械编辑验证：` prefix after reopen; the one-slide/60-object structure, notes, correct physical dimensions and existing 18/30 pt fields remain. This verifies a real editable native text object persists an edit through headless save/reopen.

As expected, checking this intentionally changed copy against the original unchanged Page/IR fails; those raw findings are retained. The copy is not adopted or used as the fixed manuscript.

Artifacts: `A-python-object-text-edited.pptx`, `A-edit-observation.json`, `A-readback-against-unchanged-page.json`.

## B — all words unchanged, wrong table ownership rejected

This v2 layout has **three real native text carriers in each action cell**. Their measured row-origin separation is **929,640 EMU**, or **97.6 physical pixels at 96 ppi** (122 SVG logical pixels at the actual 0.8 scale). The reviewer moves all carriers of `unknown/action` to the other row and all carriers of `unsuitable/action` to the first row on a new native copy. No old-run geometry constant is reused.

The complete **36-run sequence and all 428 characters are exactly unchanged**, as are object names, source IR, Page, notes and non-target ZIP members. Only `ppt/slides/slide1.xml` changes. Readback fails with **exactly two `table_cell_ownership_mismatch` findings**, each naming the actual wrong-row cell. No missing-text/global-coverage failure is needed to detect the error.

Artifacts: `B-native-cell-row-ownership-swapped.pptx`, `B-ownership-observation.json`, `B-actual-readback.json`.

## C — all words unchanged, reversed actual native arrow rejected

The reviewer reverses the first actual native edge path's endpoints and mirrors its actual visible triangle arrowhead. The expected Page/source IR retain the original `collect` → `retrieve` relationship; no label, word, other relationship or node position changes.

The complete 36-run/428-character sequence is unchanged. Only the slide XML differs from the original package. Readback fails with **exactly one `reversed_arrow` finding**, located at `collect-retrieve`. The result observes actual native direction/geometry rather than trusting a direction label.

Artifacts: `C-native-edge-and-visible-arrow-reversed.pptx`, `C-direction-observation.json`, `C-actual-readback.json`.

## D — actual layout-only change, correct-size recompile

The actual v2 SVG's whole `main-chain` group is translated **2 SVG logical pixels down**. All Page text, atom/node/edge references and business relationships remain identical. The real installed SVG parser creates the new IR from this changed SVG, then the real installed compiler compiles it with dimensions derived from the preserved frozen design:

`slide_width_in × 96 = 1280`, `slide_height_in × 96 = 720`.

The actual source body/heading sizes are 30/50 SVG px; at the real 0.8 page scale they remain **18/30 physical pt**. The resulting native PPTX again measures **12,192,000×6,858,000 EMU**, and every one of its 36 runs passes the explicit role-size check. Complete notes remain unchanged. Actual readback returns **pass, zero findings**.

A separate native-coordinate verification measures **26 moved objects and 34 unchanged objects**, totaling the actual 60. Each moved object changes by exactly **15,240 EMU**, or **1.6 physical pixels**, corresponding to the 2 logical-pixel SVG translation. The other objects remain in place. The group's external margins, including half-stroke, remain at least 48 **SVG logical pixels** (left/right 49.25, top 153.25, bottom 555.25). Physical and logical pixel margins are recorded separately rather than conflated.

Artifacts: `D-real-svg-main-chain-moved-2px.svg`, actual parsed `D-actual-transformed-svg-ir.json`, `D-real-recompile/deck.pptx` and its actual compile manifest, `D-actual-readback.json`, `D-actual-physical-typography.json`, and `native-geometry-and-zip-delta-verification.json`.

## Scope, commands and retained failures

`run_mechanical_checks.py`, `execution.log`, `verify_native_geometry.py`, `geometry-verification.log` and `commands.txt` preserve the actual transformations and commands. Raw expected-negative reports are retained, including A's intentional text mismatch, B's two cell findings and C's direction finding. No checker was modified to obtain these outcomes.

The original and all four copies retain the same correct physical presentation dimensions and 18/30 pt native size fields; full per-role censuses are recorded for the original and D. Input hashes, all output bytes, native-package counts, before/after installed identity and the final manifest make the exact engineering phase inspectable.

No new negative-case render or visual-quality judgment is claimed. The actual original render is preserved as input; the prior and parallel professional visual review remain separate. Headless Python and native-object geometry checks do not prove PowerPoint desktop use, audience effectiveness, fair E2/E3, eight-page delivery or whole-card completion.
