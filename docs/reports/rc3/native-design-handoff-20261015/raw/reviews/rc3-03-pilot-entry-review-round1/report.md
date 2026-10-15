# RC3-03 private pilot entry independent review — round 1

**Verdict: REQUEST_CHANGES (one bounded guard finding).** This verdict applies only to the private entry script and its readme. It neither accepts RC3-03 product code nor records an SDK integration, image generation, image quality, native SVG, editable PPTX, human or desktop acceptance result.

Reviewed identity:

- Script: `/workspace/work/rc3/native-image-pilot-03/prepare-pilot.py`, SHA-256 `d58831e885d336ea4f206eaec14224b2c64c6a1c35b7d8541f0505551d95b07f`.
- Readme SHA-256: `bcfeb665db238edf4ef05c6633268ebc680cc45a03d0d0aca5ffe9a303d76a78`.
- Frozen SDK: `/workspace/work/rc3/reviews/rc3-03-code-snapshot-5fa4834`, Git HEAD `5fa4834b3d07d1a0690ed53f8259d20572db7694`.
- Independent interpreter: `/workspace/work/rc3/reviews/env-03-snapshot-5fa4834/bin/python -I -B`; actual imported module origin was that frozen snapshot's `src/deck_master/__init__.py`. It was deliberately not represented as an installed wheel.

## R1: Verify the working copy's protected source object bytes

Severity: medium. Location: `Run.check`, lines 116–125; readme's statement that each step preserves source original-object bytes.

`content(current)` compares protected Document values, including source descriptors and their immutable `extract` Refs. The subsequent byte verification reads only Narrative, Plan and eight Page objects. `source_files()` verifies the separate pure `input-project`, not the working project. Consequently a missing or corrupt working `sources[].extract` object can pass this admission check while all Ref values and the original pure input remain unchanged. This is a guard-completeness defect; this review does not claim that any current public SDK writer corrupts source objects.

Independent negative probe `negative_guard_probe_source_object_not_checked` uses an in-memory readonly Store wrapper around the actual original Document. Its `read_object_bytes` would reject the first actual source extract, `.deckmaster/objects/4e/4e9f516105de7192a0ec3c8b1c629bd53826f2dd1089d5a4b91d26ae913621f8.json`. `Run.check()` still returns normally and never asks the wrapper for that Ref. No file was corrupted, copied into a live SDK mutation or replaced with a fixture.

Requested fix: verify all stored Refs reachable from the protected content roots, including `sources[].extract`, with the real Store byte/hash reader, or verify the original immutable-object subset against the already frozen copy manifest. Preserve the exact Document-value comparison and all eight pages. A negative check must show that an unverifiable working source extract stops before any operation; the pure input and original project must stay unchanged. Do not fetch or rewrite the source's historical `original_uri` to compensate.

## Reviewed boundaries without an additional finding

- Initial copy verifies the pinned record and authorization note, compares all 107 input files and 1,313,764 bytes, and requires absent disjoint pilot-local paths. The script rejects symlinks encountered while collecting source files. Root must still admit the exact installed candidate and code-review outcome separately.
- Installation admission checks isolated/no-bytecode execution, expected source SHA, exact installed module path within interpreter prefix, source-clean release metadata, wheel hash, all package files against wheel/release and manifest count. My actual readonly negative probe rejected the editable snapshot interpreter against an installed manifest. Positive installed admission and actual wheel SDK execution remain **NOT_RUN by this reviewer**.
- The authorization note accurately separates actual user statements from Root's bounded engineering choice. Declared evidence is `host_attested_instruction` without client-set assurance, transport receipt or human/platform claims; frozen SDK `resolve_evidence` computes `host_attested` for that evidence kind.
- Request replacement explicitly names the current open request. Both scopes name only p04, use `page_manifest_ref=None`, disallow page membership/order changes and remain exploratory. Feasibility has design-only scope and grants only `design.feasibility`/`design.propose`, with zero external calls and candidates. The sample replacement adds blueprint scope and grants a single call and candidate under `candidate_only`, with no `candidate.adopt` action.
- The pure `style_input` constructor was independently executed against actual readonly source objects for both intents. Both results validate the frozen `style_input.v3` schema, keep p04 as the only target, have zero references, and retain actual fonts, sizes and palette. Shape checks match four nodes, three edges and the two-row/three-column exception table. These are schema and input-projection observations, not image/model effect results.
- Ten actual frozen SDK function signatures were independently bound without invoking their writers. Manual source tracing confirms the response extraction used by this script: top-level request assurance and authorization_ref, proposal_id and plan_id, `operation_result.recipe_id` and task_ids, frozen top-level request_id/input, and call_begin attempt_id. No signature or return-wrapper mismatch was found.
- Each revision-bearing mutation obtains the actual current base revision; confirm follows its immutable proposal and commit follows its immutable plan. The full prepared-input getter is frozen unchanged, initial parameters must be exactly explicit `transparent_background=false`, and call_begin binds the single task-owned allowance, same execution and actual frozen request. Only the frozen prompt is copied into proposed tool arguments.
- Inputs are exclusively recorded before SDK operations. Prior step input records and completed/error records stop retry. Errors preserve type, payload and traceback, and the readme accurately requires checking committed Store state after uncertain persistence. No image dispatch, settle, accept, adopt, SVG, compiler or desktop function is exposed here.

## Independent evidence and limits

`readonly-probes.py` is this reviewer's own source, not the preparer's parser or Root's build audit. Corrected run: eight probe assertions passed; one of those intentionally confirms the R1 negative guard gap and is not a product PASS. All 107 pure input files and the reviewed script retained their before/after hashes. Public SDK mutation calls: **0**. Model/tool calls: **0**.

The initial run recorded seven passes and one harness `KeyError('ref')` because my negative probe incorrectly assumed the source-descriptor key. It is preserved in `probe-results-harness-error-original.json` and `probe.log`. I corrected only the probe to the actual `extract` key, reran the complete readonly probe set and kept `probe-corrected.log` plus `probe-results.json`. The original harness failure is not attributed to the product.

Actual init → feasibility → begin integration, positive installed-wheel admission, Runtime authorization effectiveness, prepared-input content delivery, native tool execution, fees, candidate acceptance and all later pipeline results remain **NOT_RUN** here. They must be observed with the admitted installed candidate after R1 closes; this review's static/signature checks do not substitute for those observations.
