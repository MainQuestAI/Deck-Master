# RC3-03 private pilot entry independent review — round 2

**Verdict: LIMITED PASS. R1 source-object guard finding is closed.** This accepts the reviewed private preparation script's bounded behavior for the next separately admitted integration step. It does not accept RC3-03 product code, positive installed-wheel execution, an image/candidate, actual effect quality, SVG/PPTX, human or desktop acceptance.

Reviewed script: `/workspace/work/rc3/native-image-pilot-03/prepare-pilot.py`, SHA-256 `93bbf6f438e654fe22d45bca19d463217f03a6ca9c9ad8b64ab53711b2aeb7b6`.

Reviewed readme SHA-256: `23a2f80adb3e1c1fba1a79d9e6c6be5c0e3fd4efa28f116fd19d38a422142300`.

Frozen SDK remains `/workspace/work/rc3/reviews/rc3-03-code-snapshot-5fa4834`, HEAD `5fa4834b3d07d1a0690ed53f8259d20572db7694`. My interpreter was `/workspace/work/rc3/reviews/env-03-snapshot-5fa4834/bin/python -I -B`; the imported SDK module actually originated from that frozen snapshot. This is a readonly review environment, not a positive installed-wheel admission.

## Finding closure and independent evidence

The fix changes only `Run.check()` and the matching readme statement. My independent AST comparison, after removing `Run.check` from both trees, found all remaining executable statements identical to the R1 snapshot. R1's script, report, original harness error and negative evidence remain unchanged in the round-1 directory.

The new guard obtains the pinned copy manifest through the existing pure-input verification, preserves the exact protected Document-value comparison, and walks every original `.deckmaster/objects/` entry in that fixed manifest. It uses the bound working Store's `read_object_bytes()` for each original object and additionally checks byte count and SHA. It does not infer Refs from prose paths or historical URLs and has no read/download fallback to replace missing working objects.

I wrote and ran `readonly-probes.py` independently; **11 assertions passed**, including these observed boundaries:

- A pristine actual readonly Store read exactly all **73** original object Refs from the pinned **107-file** manifest, including all three `sources[].extract` objects. This positive read used the unchanged pure original as its pristine Store; it did not run `init` or simulate a completed pilot initialization.
- In an ordinary filesystem copy created only inside this review directory, I removed the first actual source extract. `Run.check()` stopped with the frozen Store's actual `object file missing` error. The unchanged pure input was still available, so this confirms it did not compensate by reading that source from the pure input instead.
- In a separate isolated L1 copy, I changed bytes of that same source extract without changing its Ref. The actual frozen Store rejected it with `object bytes do not match declared sha256`.
- An in-memory readonly reader returning a wrong byte count was rejected by the additional guard. An in-memory Document missing its eighth page was still rejected by the preserved metadata comparison. These two observations are explicitly L1 checks and never modified a pilot or original file.
- Both pure style-input constructors again validated the actual frozen `style_input.v3` schema, retained p04-only targets, zero references, actual original fonts/sizes and palette, and used the current source revision.
- Ten actual frozen SDK signatures again bound successfully without executing their writers. A readonly admission negative again rejected the editable review interpreter against an installed candidate manifest.

The isolated negative copies under `l1-missing-source-isolated-copy/` and `l1-corrupt-source-isolated-copy/` are preserved as failed L1 filesystem copies, never admitted as pilot projects or used as fixture fallback. All 107 files in the pure original input and the reviewed live script retained their before/after hashes.

## Scope, budget and call path recheck

All previously reviewed routing and authorization statements are AST-identical. Manual reread confirms:

- The note stays genuine actual-conversation evidence plus explicitly labeled Root engineering choices, with runtime-computed `host_attested`; no verified-user, platform or professional-human assertion is introduced.
- Initial copy/admission remain exact and separate. Explicit Request replacement names the current request. Both scopes remain p04-only with `page_manifest_ref=None`, no membership/order change and exploratory purpose.
- Feasibility remains design-only, `design.feasibility`/`design.propose`, zero external calls and zero candidates; it does not confirm, dispatch or call the image tool.
- Begin retains exactly one external call and candidate, `candidate_only`, and no `candidate.adopt` action. Its sequence remains propose → confirm → plan(max_calls=1) → commit → task_start → complete prepared-input getter → immutable freeze → call_begin with the actual owned single allowance and same execution/request binding.
- Revision-bearing operations still obtain fresh base revisions. Initial tool parameters are exactly explicit `transparent_background=false` with zero references. The tool prompt comes from the frozen input, not a reconstructed summary.
- Exclusive pre-call inputs, actual post-call results and Documents, completed/error guards, original error payload/traceback and stop-without-retry behavior remain intact. No actual image/settle/accept/adopt/compiler/desktop entry has been added.

## Limits

Public SDK mutation/writer calls: **0**. Model/tool calls: **0**. The entry script itself was **not run**. Positive installed-wheel admission and actual init → feasibility → begin Runtime integration remain **NOT_RUN by this reviewer**. Runtime authorization effectiveness, real frozen full-content transmission, tool completion/fees, candidate output and later pipeline or acceptance outcomes require their own actual observations. This limited review result cannot be substituted for them.
