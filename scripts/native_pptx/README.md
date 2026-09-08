# Native runtime dependencies

The default native workflow verifies each local capability separately:

- **Compile:** Python `python-pptx`, SVG normalization and DrawingML emission. The probe writes a synthetic native PPTX and reopens its slide, objects and editable text.
- **SVG validation:** `rsvg-convert`. Text contrast and SVG/PPTX parity require actual SVG rasterization. A missing or failing renderer blocks the default native workflow even when PPTX emission succeeds.
- **PPTX render:** `soffice` (LibreOffice) and `pdftoppm` (Poppler). Every render uses an isolated LibreOffice profile, bounded subprocess timeouts, complete-page validation and PNG decoding before publishing results.
- **Fonts:** the preferred font is **Noto Sans SC**. The probe resolves an actual font file through Fontconfig (`fc-match`) or `DECK_MASTER_NATIVE_FONTS_DIR`, rasterizes Chinese/Latin/numeric sample glyphs, rejects missing-glyph boxes, and records the actual family, file hash and raster hash. A verified fallback is named explicitly. This sample proves baseline glyph availability, not coverage of every customer font.

`probe_native_runtime()` reports compile, SVG render, PPTX render and fonts independently. A kernel-only success cannot establish rendering or client delivery readiness. Real render smoke results are cached only while the compiler source, relevant executable identity and selected font hash stay unchanged. Failed observations are not cached.

Native callers pass explicit `svg_paths`, `output_root` and `canvas_mode="native"` to `NativeCompileRequest`. Each SVG must carry its pinned hash. Native output uses exact 16:9 slide dimensions and one contain mapping for geometry, fonts, strokes and effects. Legacy callers retain their 1672×941 mapping. `readback_pptx()` on native results performs structural readback; its `visual_review="not_run"` is deliberate. Independent visual review and current-version approval remain mandatory for delivery.
