# Root single-page PPT observer helper review

Verdict: **PASS for the corrected helper's bounded observation design**, SHA-256 `3a3162ac343ab5e7a56ad7572349b0c7106071116edf2a42c08d55ba85a90e29`. This is a source/signature review plus read-only installed admission. The helper was **not executed**, and no actual preview, PPTX, readback, render or effect PASS is claimed.

## Identity and actual read-only checks

- Reviewed copy: `observe-native-ppt-reviewed-v2.py`; the initial `a37e861d…` copy and exact fix diff are also retained.
- Installed source: `5dbdf72089d6625449a23a52ef3e23859c597b4e`, tree `1b69a05050c63d0a2fbc4aaac86350611ad9f504`.
- Wheel: `94f6f31fcadf4e5a493b77b7dcefd7cebe43edc033f9268266fdba07eeb9ffb2`.
- Installation manifest SHA-256: `bcb668040f2c5e7cd0613b792517f6ec055f1d5925b5e5a582c076e67dfdbb10`.
- Actual installed `-I -B` imports and signatures for preview, SVG parsing, font resolution, compilation, readback and rendering match every call in the helper. Raw signatures, module origins and current document fields are preserved in `installed-signatures-and-fields.json`.
- The actual current project has eight Pages; p04 retains fixed Page SHA `cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b`, its speaker-notes field is a string, and its logical canvas is 1600×900. At inspection, the actual p04 SVG/preview slots remained null; the script must be run only after formal adoption supplies a real SVG.
- The reviewer independently loaded the pinned admission helper and called **only** its read-only `installation()` function. All 256 installed package/resource files match the fixed wheel and release metadata. Raw identity is retained in `independent-readonly-installed-admission.json`.

The admission helper SHA is pinned to `4f51363e867cdc367416a4b665a7537db5f2d1fa1c343b73cab848187790e782`. Its module-level statements define imports, constants, functions and a class; `runpy.run_path` does not satisfy its `__name__ == '__main__'` guard. Retrieving `installation` therefore does not run its preparation/writer entrypoint. The reviewed observer repeats full installed admission before and after its future operation.

## Original findings repaired

The initial helper's two concrete findings are recorded in `initial-review.md` and were sent to Root before execution.

The corrected preview branch verifies both the exact `derived_from=[entry.svg]` and the exact single SVG dependency SHA/page identity. Its postconditions also preserve every p04 entry slot except `svg_preview`, in addition to all eight Page Refs, the other seven full entries, Narrative, ContentPlan and outputs. This prevents an image derived from a different SVG from silently becoming a matched pair in the observation. An existing mismatched preview will be preserved as failure evidence rather than called passing.

The corrected compile branch preserves raw readback findings, reports actual render count, and computes mechanical status as PASS only when readback says `pass` and exactly one render exists. It carries that status into the root observation. `completed` denotes execution completion; visual quality and desktop approval remain null. Consumers must inspect `mechanical_check_status` rather than infer PASS from process exit or `completed=true`.

## Scope and gate handling

The preview action uses the real SDK `pipeline.preview_svg_page`, whose installed implementation invokes the shared `render.preview` eligibility guard before attaching the p04 preview. It does not manually write the current document or bypass the SDK transaction.

The compile action copies the exact adopted SVG bytes from the Store, compiles one `SvgInput`, supplies full current p04 notes, records the returned readback and actual renderer outputs, and requires the **entire project document** to remain unchanged. It calls the pure library compiler into a separate engineering output directory. It does not call project production, assembly, export, readiness approval or delivery APIs, and it never assigns the engineering file to `Document.outputs`. The explicit one-page scope makes this a legitimate bounded engineering observation, not a replacement for the formal eight-page production/delivery gate. Run output must stay in the intended intermediate observation directory outside the project; the helper assumes this Root-controlled argument.

The reader records actual image origin as the prior `8057905…` generation phase, separately from the current 5db reader. It does not retroactively change that image's Request, native observation, allowance or execution identity. There is no image-tool invocation, fixture fallback, new manuscript text or model SVG output authored by this helper. Native-shape/text/picture counts are descriptive observations, not a design/editability quality verdict.

## Limits

No actual project writer, compiler, renderer or image tool was run by this reviewer. The preserved actual project was only read through Store accessors. This review cannot prove that a not-yet-generated SVG, actual PPTX or real rendering passes, and cannot close E2/E3, whole-deck delivery, Owner/audience use or desktop editing. Future helper runs must preserve their real outputs, failures and before/after state and report those separately.
