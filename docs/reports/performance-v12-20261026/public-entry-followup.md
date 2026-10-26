# Public-entry review follow-up: #204, #140, #162

This follow-up addresses the independent audit of 7244477a. That commit's 637 installed passes remain evidence of its own identity; they are not claimed for this change. All fixtures are synthetic, with zero model/customer calls.

## Changes

- #204: import_report passes its captured artifact digest map to subject-binding validation. Standalone binding calls still derive their facts. Every review retains subjects/dependencies, policy/identity checks and a separate PPTX overlay. The original adoption boundary still hashes subject bytes.
- #140: an explicit fresh control read aborts/replaces the previous read-only fetch instead of awaiting it indefinitely. Passive refreshes share the current fetch. Only the owning promise clears the slot; existing route/control serial checks isolate late responses. No write is aborted or automatically retried, and no timeout/SLA is introduced.
- #162: both design strategies' actual blueprint prompt and canonical design references now distinguish native editable text/relations/principal objects from bounded replaceable raster assets; unsupported effects require upfront redraw/assetization/simplification and impact disclosure. Composition freedom is retained. Historical prepared/frozen prompt bytes remain unchanged. This proves contract transport, not generated-image quality.
- Original installed selectors are retained; the three new regression files are added to the installed entry.

## Validation before commit

Affected existing unit selection: 124 passed, 2 skipped, with one new counter assertion subsequently corrected as described below. Final nine new unit cases pass. Existing browser selection: 9 passed; the three new browser cases pass after correcting their gallery fixture to the required 24 pages. Ruff and diff checks pass. A separate read-only code review found no blocking issue; it did not execute tests and does not replace the parent's cloud review.

The installed 724 wheel independently fails the new never-returning-control test with aria-busy still true after explicit verified recovery. Candidate source passes both never-returning and late-response cases while preserving an unknown clear request without another POST, plus single-flight owner cleanup. The old installed package origin appears in the raw failure log.

Paired public import probe uses the exact 724 review_import module loaded from git against the otherwise current, unchanged supporting code, and the candidate module on the same machine/fixture. It is a function-path comparison, not a claim that the entire old package was installed for this measurement. Sixteen Page objects each exceed 16 KiB; physical Path.read_bytes calls and bytes are counted across the complete public import, including commit/adoption:

| Reviews | Old Page reads | Candidate Page reads | Old builder reads | Candidate builder reads | Required adoption reads |
|---|---:|---:|---:|---:|---:|
| 2 | 370 | 146 | 336 | 112 | 2 |
| 4 | 596 | 148 | 560 | 112 | 4 |
| 8 | 1048 | 152 | 1008 | 112 | 8 |

Other Page reads remain 32. This counter scope excludes non-Page objects and is not total process I/O or a latency result. The public regression checks one builder per import, zero Page reads during per-review binding, and one necessary Page hash per adoption. Initial assertion of identical total reads was incorrect because it omitted the original per-review adoption integrity check; the counter now names that cost and reports the full total rather than weakening product checks. Raw results and reproducible probe are in evidence/public-followup/.

Failure history is preserved: first new unit tests used an incorrect return wrapper and patched the wrong imported prompt alias; the corrected fixture injects the actual service dispatch alias and restores it before current-code frozen-input reads. First new browser fixtures used fewer than gallery's minimum 24 pages and failed before entering product code. No product assertion, skip rule or timeout was relaxed.

## Outstanding at this report snapshot

New candidate wheel build/independent affected installed verification and new-SHA CI are pending; their exact outcomes are supplied in the PR/parent handoff after execution. Full 724 remote unit matrix and renderer are green; its required browser and offline steps passed, while its installed batch was still running at last observation. Local librsvg provisioning remains blocked by the already-recorded system permission / official-source proxy failures; no bypass was attempted. No issue is closed or PR merged by this follow-up.
