# Final v3 p04: scoped headless mechanical checks

**A–D meet their expected engineering outcomes on the new final-v3 artifact.** Independent baseline readback passes. These results do not decide F07 visual readability, PowerPoint desktop use, fair E3 or card completion; those verdicts remain null.

The actual original PPTX is SHA-256 `0c145ff3f055c5c7926f97ee9ec5bdbd641bb4fbc1bcbbae732b7fd828d057c8`; its actual author SVG is `fb9eb0ce88c0db3cc7d0c82255ac1fefeec11cb6491aaa82c199446faa81b5a1`. The fixed Page remains canonical SHA `cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b`. This fresh run uses the admitted installed **5db** source `5dbdf72089d6625449a23a52ef3e23859c597b4e`, wheel `94f6f31fcadf4e5a493b77b7dcefd7cebe43edc033f9268266fdba07eeb9ffb2`, with its absolute interpreter and `-I -B`. It is not relabeled as cf61/F9.

Actual baseline: **60 native shapes, 36 text runs, 428 characters, zero pictures/media**; independently executed readback has zero findings. Dimensions are exactly **12,192,000×6,858,000 EMU** (13⅓×7.5 inches). Every visible run has its source-bound role checked: body **18 pt**, the two declared headings **30 pt**. Actual complete notes match the unchanged Page.

| Actual-copy check | Observed outcome |
|---|---|
| A: edit title through `python-pptx`, save, instantiate a fresh reader | New text persists; dimensions, per-run typography and notes remain correct. The deliberate text change correctly fails comparison with the unchanged Page. |
| B: swap all three native text carriers from each of the two action cells | All 36 text runs and 428 characters remain in the same XML sequence. Readback reports exactly two located `table_cell_ownership_mismatch` findings for `unknown/action` and `unsuitable/action`. |
| C: reverse the real first edge's path endpoints and mirror its real visible arrowhead | All text remains unchanged. Readback reports exactly one `reversed_arrow`, naming `collect-retrieve`. |
| D: move the real SVG's whole main-chain group 2 logical pixels down, parse and compile it again | Real compilation at **1280×720**, derived from frozen physical inches, passes readback with zero findings. Actual dimensions, each role's 18/30 pt and notes remain correct. |

B uses this v3 artifact's measured row separation: **952,500 EMU = 100 physical pixels at 96 ppi = 125 SVG logical pixels**. B and C change only `ppt/slides/slide1.xml`; every other ZIP member, including notes, is byte-identical. No prior-layout geometry constant is reused.

D uses the actual modified SVG to generate its IR; no IR or Page is fabricated. Native-coordinate comparison observes **26 objects moved by 15,240 EMU (1.6 physical pixels)** and **34 objects unchanged**. The 2 SVG-pixel movement is consistent with the actual 0.8 scale. The moved group keeps logical SVG margins, including half-stroke, of 49.25 px left/right, 143.25 px top and 569.25 px bottom; physical margins are recorded separately. Actual per-run typography, physical dimensions and complete notes are independently checked for **all four copies**, not only D.

`execution.log`, all raw positive/negative readbacks, per-copy physical/typographic censuses, original/copy packages, actual D compile manifest and geometry/ZIP deltas are preserved. The scripts and `commands.txt` record the exact operations. Seven original input files and all 256 admitted installed files have identical before/after bytes; no original SVG/PPTX, actual project, source or earlier evidence was edited. No checker modification, synthetic fixture or prebuilt result was used. The active visual review was not read.

This is engineering evidence about the new actual file. It does not test audience readability, close F07, replace a desktop edit/save/reopen session or provide a whole-deck/E3 verdict. Prior artifacts and their reports remain separate and unchanged.
