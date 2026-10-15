# F05 initial helper revision: REQUEST_CHANGES

Inspected SHA-256 `0a148342c51aad0efd46f6910fc59ebefe0f95baee1d7d6a6c5b48fa79021e52`. Its physical canvas conversion and actual EMU comparison are correct for the frozen pilot; its initial font predicate is insufficient.

1. A global minimum ≥18 pt and maximum ≥30 pt does not prove each heading uses ≥30 pt. Evaluating the exact helper AST on the explicit L1 counterexample body18/title30/section-heading24 returns true despite the undersized second heading. Title18/body30 likewise incorrectly returns true.
2. Extracting only `a:rPr` elements which have `sz` omits visible runs with unresolved size. An exact-AST extraction probe with one 30 pt run and one visible run missing `sz` returns `[30]` and the old predicate says true. The unresolved run should prevent a typography PASS.

These are helper classification/measurement gaps, not actual new conversion results or generated native files. Both were immediately reported to Root. Raw exact-AST probes and the old actual PPTX field census are preserved in `readonly-field-and-predicate-observations.json`.
