# RC5 content-method library: implementation revision

Status: development specification, not an implementation completion claim.
Baseline: `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8`.
Upstream: *Deck Master content-methods iteration spec v1.1*, Library
`libfile_0ba3de0075948191b274f3722324399b`; resource ZIP
`libfile_d09877ab18288191a381632e2d5c614f`.

The complete 598-line main specification was read through Library on
2026-10-20. Its ZIP and original Markdown byte downloads were refused by the
environment's network proxy (HTTP CONNECT 403); neither is represented here
as a successfully materialized original. Resource integration requires the
actual ZIP, including its proposed catalog and 52 seed resources.

This revision adopts v1.1 conditionally with the following binding corrections.
It does not replace its full method cards, examples, migration decisions or
acceptance conditions with an abbreviated implementation brief.

## Release sequence

The unpublished `1.0.0` preparation is corrected in an independent commit to
PEP 440 `1.0.0rc4`, proposed tag `v1.0.0-rc4`. No existing public release asset
is deleted. RC4 candidate materials are newly built from that correction.
RC5 implementation follows in separate commits, with package `1.0.0rc5` when
the candidate actually contains the implementation. RC5 needs a Draft PR and
CI follow-through; neither merging RC5 nor publishing formal 1.0.0 is authorized.
Product release versions do not globally rename internal schema versions.

## Binding implementation decisions

1. **Semantic resource class and transport kind are distinct.**
   Catalog classes `instruction`, `example`, `template`, `data`, `script`
   describe how Host should interpret bytes. Registered resources use the
   existing `method` transport kind in `work_context.v2`; `source_extract` and
   `page` retain their meanings. Do not turn example data into customer
   evidence or execute a script just because it was read. Validate full,
   manifest, warm delta, cold delta and fresh-session behavior.
2. **Explicit selection survives the final phase/scope binding.**
   Thread `selected_resource_ids` through the actual dispatch call stack,
   including `new_task`, `stamp_task` and `build_phase_task`, to the final
   producer freeze. It is call input, never a new durable Task field.
   Recompute final-stage defaults plus explicit selections; do not infer
   selection from a temporary manifest or keep obsolete stage defaults.
   Validate catalog membership and applicable role/stage/scope before
   persistence. Expand dependencies deterministically in dependency-first
   order, preserving declared traversal order and deduplicating IDs.
   Unknown IDs, cycles, duplicate catalog IDs/paths and out-of-scope selections
   fail concretely. No new method approval step.
3. **Frozen history stays truthful.**
   Keep all existing runtime IDs and canonical paths. Stored Tasks read only
   their own manifest; legacy selector behavior remains independently frozen.
   Missing or changed bytes remain `basis_changed`, not a refresh of old
   evidence. Existing continue/retire/reissue handles a new basis after
   outstanding calls are settled. Method changes never broaden authorization,
   rewrite a confirmed Narrative/Plan/Page, or cancel a valid narrow scope.
4. **One exhaustive catalog feeds runtime, build and install.**
   Merge the proposed seed catalog with the existing 13 runtime resources,
   installation reference, four Skill entry/agent files and resolver mapping.
   Keep the historical installed `resources/skill` root. Catalog registration
   and deterministic source/target mapping must agree across runtime,
   `tools/build_hook.py`, sdist inclusion and `install._wheel_skills`.
   Retain missing/unknown file, duplicate, symlink, traversal and exact byte
   checks. Installed reads cannot borrow from cwd or real HOME.
   Catalog metadata itself is included and verified. Research, benchmark
   answers, customer materials and fonts stay out of the Skill package.
5. **One authoritative location per rule.**
   `content-methods` keeps runtime contracts and navigation; method cards own
   derivation actions; `page-writing` owns visible prose; `narrative-patterns`
   owns candidate sequences; `method-review` owns finished-content critique.
   Merge or shorten old examples/calibration into links where appropriate.
   Preserve existing authorization, scope, freeze, identity and exit contracts.
   Case walkthroughs link to input/after assets rather than duplicating them.

## Delivery and evidence

Keep four public Skills, ten method cards, seven supporting guides, six
complete cases (40 after pages), twelve calibration examples, three optional
templates and the bounded arithmetic helper. Counts describe scope, not
content quality. Each resource must make reasoning, narrative or tradeoffs
visible in complete prose. Read all actual seed files before accepting them.
Apply v1.1's Gemini corrections and preserve synthetic/example labels.

Engineering acceptance T01–T12 from v1.1 remains applicable. Additional
targeted cases cover final-binding selection retention, removal of earlier
defaults, deterministic dependency closure, invalid/cyclic/out-of-scope
selection, old manifest hashes, every context body mode and complete wheel/
sdist/managed-release byte equality. Do not expand into unrelated validation.

After an integrated version exists, generate complete old/new manuscripts
for three unfamiliar inputs: operating diagnosis, options selection and
teaching. Keep the same actual model, Host, inputs, page count and tool
conditions within each pair; retain complete outputs and provenance.
Use Astra Medium when actually available, and record the actual model rather
than relabeling another model. Do not use the six teaching cases as the sole
effectiveness evidence. Report concrete improvements and regressions.
Check confirmed-draft local edits, speech-only, design-only and read-only review
scope separately. Author review, independent execution and human recognition
are distinct; unavailable external execution blocks only that evidence.

## Verified integration points

At the baseline, `freeze_task_methods` is called by `tasks.new_task`,
`collaboration_binding.stamp_task`, `content_production.build_phase_task`
and the existing method-basis reissue path. The build hook hardcodes fourteen
reference names; the installer separately enforces a static expected source
set. Both must migrate together. `work_context` currently accepts exactly
`method`, `source_extract`, and `page` transport kinds.

The checkout and `/workspace/.agents` contain no applicable `.agents/skills`
guidance. `AGENTS.md`, task index and recovery playbook remain the governing
repository instructions.


## Engineering checkpoint (2026-10-20)

The seed-independent foundation is implemented: one catalog containing only
existing resources, deterministic dependency validation, bounded Python dispatch
and independent read selection, final phase/scope freeze, preserved old basis,
common build/install mapping and frozen pre-catalog release compatibility.
`method-catalog.v1` is a feature writer boundary only when a committed Task
actually uses new IDs/paths; `work_context.v2` is unchanged. The package source
is now `1.0.0rc5` development, not a completed candidate.

The 52 seeds have not been imported. Host-facing CLI/service selection wiring,
full resource migration and actual paired manuscript evidence remain pending.
Synthetic test resources exercise these contracts and are not substitute seeds.
