# Actual p04 native PPTX mechanical edit and relation-pair observation

Result: **the requested headless engineering checks A–D met their expected results** on the actual p04 artifact under the fixed **5db** installed phase. The two deliberately wrong native copies were rejected by located relation checks despite identical text. The layout-only recompile passed. This is neither PowerPoint desktop verification nor professional visual-quality approval, fair E3 qualification or RC3-03 completion.

## Actual inputs, reader and isolation

The reviewed original PPTX is the actual native result `run-02-native-ppt/native/deck.pptx`, SHA-256 `c93179007f6e478a3ac8736d712e18a709519ddc7a027550228745619274a4ae`. The actual author SVG, original rendered PNG, fixed Page and original parsed SVG IR were copied byte-for-byte into this evidence directory. Their original and copied bytes remain preserved. The fixed Page's independently recomputed canonical SHA is `cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b`.

The reader is the actual isolated installed interpreter for source `5dbdf72089d6625449a23a52ef3e23859c597b4e`, tree `1b69a05050c63d0a2fbc4aaac86350611ad9f504`, wheel `94f6f31fcadf4e5a493b77b7dcefd7cebe43edc033f9268266fdba07eeb9ffb2`, invoked with `-I -B`. Full before/after installed admission verifies all 256 package/resource files match that wheel and release. This evidence is not relabeled as any later F9 source repair.

This reviewer independently ran the real installed `pipeline.readback` on the original PPTX first: **pass, zero findings**, one slide, 59 native shapes and 35 text runs. The original notes match the complete fixed Page notes. No Root readback verdict was borrowed. No fixture graphics, precomputed PASS, live visual-review report or replacement Page was used.

All mutations and new files are confined to this exclusive review directory. All five original input files have identical before/after byte counts and SHA-256; installed files also remain identical. There was no project writer, image-tool call or native model call. The parallel actual project/review workflow was not modified by this reviewer.

## A — actual editable native text, save and reopen

Using `python-pptx.Presentation`, the reviewer located the real `atom:p04:title` native text object, changed its actual run text from the original title to the same title prefixed with `机械编辑验证：`, saved a new PPTX, created a fresh `Presentation` from the saved file, and verified the reopened native object contains exactly the new text. One slide and 59 native objects remain, and complete notes are unchanged.

The altered copy was also checked against the **unchanged original Page and source IR**. It correctly fails with `svg_ppt_text_mismatch` and `unverifiable_text_mapping`; that intentional manuscript mismatch is retained in `A-readback-against-unchanged-page.json`. This copy was never adopted into the actual project. The result demonstrates a real native text object can be edited and persist across headless save/reopen. It does not substitute for opening/editing/saving/reopening in PowerPoint.

Artifact: `A-python-object-text-edited.pptx`; exact object text and reopened observation: `A-edit-observation.json`.

## B — same text, wrong table-row ownership is detected

The two actual `exceptions` table action cells contain three native text carriers for `unknown` and two for `unsuitable`. On a new native PPTX copy, the reviewer moved every carrier of the first cell down by 126 px and every carrier of the second cell up by 126 px, swapping their physical row ownership while keeping their column, text, object names and all other parts unchanged. The expected Page and SVG IR remain the originals.

The 35-run text sequence and all **428 characters** are exactly unchanged, stronger than merely preserving a global character multiset. The only modified ZIP member is `ppt/slides/slide1.xml`; notes and all other members are byte-identical.

Actual readback returns **fail with exactly two `table_cell_ownership_mismatch` findings**, correctly locating `unknown/action` and `unsuitable/action`. There is no global text-coverage failure: the located native geometry check observes ownership even while all text remains present.

Artifact: `B-native-cell-row-ownership-swapped.pptx`; raw findings: `B-actual-readback.json`; complete before/after positions: `B-ownership-observation.json`.

## C — same text, reversed native arrow is detected

On another new original copy, the reviewer reversed the actual `edge-collect-retrieve` native custom-path endpoint order and mirrored the corresponding real independent triangle arrowhead. This changes both the native path's direction and the visible arrow's direction, without touching any text, node location, Page, source IR or unrelated relationship. It is not a metadata-only direction label change.

The complete 35-run/428-character native text sequence is unchanged. Again only `ppt/slides/slide1.xml` changes. Actual readback returns **fail with exactly one `reversed_arrow` finding**, naming `collect-retrieve`, from `collect` to `retrieve`.

Artifact: `C-native-edge-and-visible-arrow-reversed.pptx`; raw finding: `C-actual-readback.json`; original/reversed native endpoints and triangle vertices: `C-direction-observation.json`.

## D — real layout-only SVG change and recompile retain relations

The reviewer copied the actual author SVG and added `translate(0 2)` to its entire `main-chain` group. The fixed Page, every visible text string and all atom/node/edge bindings remain unchanged. The installed parser generated the new IR from that actual modified SVG; it was not hand-authored or patched to manufacture a matching result. The same installed compiler then produced a real new native PPTX using the complete original notes and actual resolved font files.

Actual readback returns **pass, zero findings**. A separate read-only geometry comparison verifies all 26 native objects belonging to that group moved exactly **2 px / 19,050 EMU down**, while the other 33 objects stayed in place. The actual frame retains at least 48 px external margin, including half its stroke: left/right 49.25 px, top 159.25 px, bottom 547.25 px. No business semantics were changed to obtain the positive result.

Artifacts: `D-real-svg-main-chain-moved-2px.svg`, `D-actual-transformed-svg-ir.json`, `D-real-recompile/deck.pptx` and its actual compile manifest. Raw readback: `D-actual-readback.json`; native movement and ZIP-member verification: `native-geometry-and-zip-delta-verification.json`.

## Reproduction and limits

`run_mechanical_checks.py` contains the complete executed SDK calls and actual-copy mutations; `execution.log` records the run. `verify_native_geometry.py` independently rechecks the saved actual native outputs and the byte-preserved non-target ZIP members; its output is in `geometry-verification.log`. The exact interpreter/arguments and reproduction commands are preserved separately. The script is deliberately exclusive-output and must not be rerun over its existing evidence directory.

The original actual rendered PNG is preserved as an input; no visual-quality judgment is made here and no new negative-case render was needed for these native geometry checks. Positive D tests layout equivalence, not design quality. Headless Python object editing and native XML/geometry mutation remain engineering observations. Human Owner/audience use, PowerPoint desktop editing, fair E2/E3, full eight-page delivery and overall card closure remain outside this result.
