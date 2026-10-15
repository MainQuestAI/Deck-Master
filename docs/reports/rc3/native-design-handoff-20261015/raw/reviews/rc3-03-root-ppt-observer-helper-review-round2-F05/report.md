# F05 physical canvas and per-run typography helper re-review

Verdict: **PASS for the revised measurement/helper logic only**, helper SHA-256 `7fe47e10d9e419cd8408aa8316c032fca6ff122e2e15059c118419ac27232251`. No new conversion, preview, render, project writer or SVG repair was run. This does not certify that the current actual SVG will convert successfully at the corrected physical size.

## Actual size attribution and prior scope correction

The frozen adopted design requires 13⅓×7.5 inches, with a 1600×900 logical SVG canvas. Independent read-only access through the actual installed 5db `resolve_page_design` confirms those fields and its real call signature. The installed compiler accepts dimensions at 96 px per physical inch. Therefore the correct `CompileOptions` dimensions are **1280×720**, with expected native `p:sldSz` **12,192,000×6,858,000 EMU**.

The prior actual engineering PPTX `c93179007f6e478a3ac8736d712e18a709519ddc7a027550228745619274a4ae` independently measures **15,240,000×8,572,500 EMU**, or **16⅔×9.375 inches**. Its 35 actual text runs have explicit point sizes 18/30 in that larger file. The previous helper supplied the logical 1600×900 values as physical compile dimensions, producing this 1.25× mismatch. The formal installed pipeline already uses `canvas.slide_*_in * 96`; there is no compiler/product-size defect established here.

The prior helper review did not check this physical-inch binding. Its limited PASS did not establish canvas/typography compliance. The earlier mechanical A–D observations remain observations on that larger engineering artifact and cannot be relabeled as checks of a corrected-size file. All earlier artifacts and reports remain unchanged.

The native `type="screen4x3"` is a template label. The reviewed check correctly uses the actual `cx/cy` values and does not mistake that label for the actual aspect ratio.

## Initial F05 revision findings and correction

The initial F05 helper `0a148342…` fixed dimension binding but used a global min/max font predicate and ignored visible runs without explicit size. `initial-0a148342-review.md` records the two REQUEST_CHANGES findings, exact counterexamples and their immediate report to Root. The old helper bytes and exact change diff are preserved.

The revised helper now:

- Resolves the complete adopted design with `require_current=True`, uses its physical inches for compilation, saves that actual context, and compares produced native EMU dimensions with the frozen values.
- Reads each nonempty native `a:r/a:t` under its owning named native shape, then checks that run's actual `a:rPr@sz` in hundredths of a physical point.
- Uses a declared fixed-p04 role mapping: `atom:p04:title` and `atom:p04:block:exceptions-heading:text` are headings, while all other actual source-IR text objects use body size. The latter block is a Page paragraph used as a section heading by this existing visual layout; this mapping changes no Page semantics and is not inferred from current size or boldness. In particular the bold main-chain condition and bold table headers remain body text.
- Requires every measured visible shape name to exist in the actual parsed source IR, both heading identities to occur, and every visible run to meet its own frozen role threshold (18 pt body, 30 pt heading). A missing explicit size is `fail_or_unverifiable`, not omitted from the check.
- Makes mechanical status fail when the readback/render-count check, physical canvas check or per-run role-size check fails. Actual findings and each run's measurement remain saved, even if the process exits normally. `completed` is execution completion; quality/desktop approval stays null.

## Independent checks actually executed

Only the role-measurement AST block was extracted from the exact reviewed helper, with no execution of its `main`, preview, font resolution, compilation or rendering. It was evaluated against the preserved actual prior native XML and explicit **in-memory L1 predicate controls**, never a fabricated PPTX output.

All seven expected outcomes were observed:

| Input to the exact role-check block | Observed result |
|---|---|
| Prior actual native 35-run role census, font-role check only | True; physical mismatch remains a separate known failure |
| Secondary heading 24 pt while title is 30 pt and body 18 pt | False |
| Title 18 pt with a body enlarged to 30 pt | False |
| Visible body run missing explicit `sz` | False/unverifiable |
| Body 17.99 pt, below frozen 18 pt | False |
| Visible native shape name absent from source-IR text names | False |
| Missing second declared heading | False |

Raw per-run actual measurements, the extracted-block controls and exact source identity are preserved in `revised-role-predicate-observations.json`. The inspector uses the actual fixed installed 5db module; no newer F9 product source is substituted.

The existing compiler formula predicts that the unchanged 24/40 px SVG text at the corrected 0.8 page scale would become 14.4/24 pt. This is explicitly **a formula prediction only**. No new PPTX has been produced by this reviewer, and a future real conversion must preserve its actual outputs and report its actual typography/readback/render status before any author repair or acceptance claim.

## Preserved inspection setup failure

The first attempt to capture the mutable helper stopped when Root had already replaced `0a148342…` with its repaired version. The subsequent inspector could not find its not-yet-copied frozen input and stopped before any SDK access; `readonly-check.log` preserves that traceback. The exact initial file was then recovered from Root's retained v3 copy, verified against its known SHA, and the separate successful `readonly-check-attempt2.log` was saved. This setup race is not a product or conversion failure and was not converted into a PASS result.

## Limits

The reviewer did not run the observer helper, compile or render any artifact, change the actual project, edit any SVG, or alter old evidence. These observations validate the intended physical/typographic measurement boundary, not an actual corrected conversion, visual design, PowerPoint desktop use, full eight-page delivery, E2/E3 or card completion. Future runs must use a fresh output directory and inspect the saved mechanical status rather than infer PASS from exit status.
