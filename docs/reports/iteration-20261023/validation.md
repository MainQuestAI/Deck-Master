# Candidate validation — 2026-10-23

## Identity

- Local branch: `codex/s1-s3-local-20261023`.
- Restore: `6797b2070d8650ea0e319bae0c39cd2c052a40c6`; restored tree `13f925e917955262c97907f3065c445087cb07b2` (source equivalent to reviewed 601; original ancestry not recovered).
- S1/S2: `2b83e3a8502ca67da961b2bf310e4b281be3c9d0`.
- S3 preparation/spec: `84623816a295440083f79574e59e9f2854eb0e6c`.
- Built product candidate: `4a2e8f877444227b5c6288c1ee21c8ae4119cd4c`; tree `3a00a56ad5b727dfa48e9a8a568473a0b308b7e3`.
- Build source_dirty: false. Wheel/sdist version remains the repository's 1.0.0; exact candidate identity comes from SHA and manifest, not version alone.
- Wheel SHA256: `b04c818b2df3dce043bf0fe015012f3d500ed5c4dc3a59a2f0e9221bdf7d7ed6`.
- Sdist SHA256: `4556e8f9aee93917f8cb5fa00a41d1648eb81c6ce69b3f3f6a80962fbbaaf143`.

## Engineering evidence

Source core gate: 341 passed (core-candidate.log). After the subject-specific native prompt/return correction, native/outline gate: 16 passed (native-outline-final.log). Final source vertical gate: 46 passed, including 20 real Chromium cases across both shipped surfaces (source-final-vertical.log). Core and vertical files are disjoint: 387 source tests in total; the additional 16-test native follow-up overlaps this set. The first installed gate had 377 passed / 9 failed because its isolated test environment lacked setuptools (all nine failures were ModuleNotFoundError in build/resource tests). The required build-test dependencies were installed and the exact final wheel rerun without changing assertions. Old failing exploratory logs are retained and are not acceptance evidence; fixes preserved required assertions and byte-identical schema mirrors.

Final isolated installation gate: **387 passed**, including **20 required real Chromium cases**, with no skipped browser gate (installed-final.log). All **362 package files** matched the wheel manifest; all **91 loaded deck_master modules** resolved inside the isolated site-packages directory (installed-final-proof.json).

The build verifies canonical Skill inventory and package resources; installation additionally audits every loaded deck_master module against site-packages and compares each package file to wheel SHA256. Browser tests use real `/usr/bin/chromium`, both shipped surfaces and synthetic project fixtures. Screenshots preserve observed frontend load; they do not prove a remote user saw a loopback URL, real customer visual quality, model judgment or target-host behavior.

S3 preparation integrity passed: 24 anonymous items, 37 frozen baseline reference files, separate answer key, hashes checked. Actual execution denominator = 0. There are no measured false-positive/negative rates or observed human comprehension results.

## Remaining acceptance and exact blockers

| Action / target | Result | Reason / next boundary |
| --- | --- | --- |
| Library ZIP materialization to this executor | failed, handled by supported text fallback | Helper download failed twice; no additional bypass/retry. Full text hash and resulting tree verified. |
| Native Codex Review session initialize | environment_blocked; model/review not_run | ProviderUnavailable, phase initialize, category tool_failed, exit_code 3 / process_exit_code 1. No turn started. Does not establish sqlite root cause or repair. |
| Rebuild previews using local renderer | needs_tool / not_run | rsvg-convert missing; soffice/pdftoppm present. No renderer workaround or visual pass claimed. |
| Real S1 Host continuation and S2 automatic independent outline loop | not_run | Explicit entrypoints and Master orchestration implemented; real Host initialization unavailable. Legacy core continue is intentionally not an automatic new-budget trigger. |
| S3 A/B authoring, independent blind review, human comprehension, Q10/Q12 visuals | not_run | No functioning verified Host execution; no paid/customer batch authorization. Q10/Q12 need actual pixels/editable objects. C remains disabled. |
| RP-24 real Host identity/settlement reuse | not_run | Inherited engineering coverage retained; no new execution, fabricated receipt or shifted quota. |
| Remote push / PR / merge / release | not_attempted; inherited publication authorization unresolved | This branch and its artifacts are local only. Parent must resolve exact branch/commit/PR authorization; no alternate-channel publication was attempted. |

No credentials, security settings, customer files, paid production or remote publication were changed. Full implementation/acceptance mapping: implementation.md. S4 is outside this task.

## Local evidence locations

- `/workspace/handoff/final-release/release.json` and adjacent wheel/sdist: exact build identity and exhaustive inventory.
- `/workspace/handoff/core-candidate.log`, `source-final-vertical.log`, `native-outline-final.log`, `installed-final.log`: test outputs.
- `/workspace/handoff/installed_final_checks.py`, `installed-final-proof.json`: reproducible isolated runner and import/file audit.
- `/workspace/handoff/source-final-artifacts/`, `installed-final-artifacts/`: browser screenshots and synthetic fixtures.
- `/workspace/handoff/native-startup-probe.json`, `native-channel.json`, `render-doctor.json`: environment evidence, no real model execution.
- `/workspace/handoff/s3-frozen/manifest.json`, `preparation-check.json`: experiment preparation identity, hashes and zero-execution denominator. Give reviewers only `reader/`, withhold `private-answer-key.json`.
- `/workspace/handoff/local-handoff.json`: final branch/commit/tree and incremental bundle/diff hashes. These files are local, not externally published.

This validation record is a documentation-only commit after the built candidate. Product, Skill, schema, test and experiment-tool bytes remain identical to the built commit.
