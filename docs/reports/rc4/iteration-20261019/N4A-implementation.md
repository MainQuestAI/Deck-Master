# N4A working-context transport evidence

Evidence class: **SYNTHETIC_ENGINEERING**. This report records the working-tree implementation based on `a08bc68c1cbbbc806205104c2bb01f3f096305f0`; it is not a release, customer performance result, model-application receipt, or professional review. The candidate's authoritative AC status remains in the single execution ledger maintained by the integration owner.

The implementation adds `work_context.v2` as an explicit read protocol. Existing calls retain v1 shapes. The new packaged schema and the sole mirror in this iteration's `contracts/` are byte-identical and registered in the existing schema/package boundary checks.

## Entry and recovery behavior

- Python: `read_task_methods`, `read_skill_methods`, `task_summary`, `_pending_host_tasks`, `create`, and `continue_project` accept `read_protocol`, `body_mode`, and `cache_offer`. An adapter can separately supply an actually observed `observed_context` containing its session and context generation.
- CLI: `methods`, `create`, and `continue` accept `--read-protocol work_context.v2`, `--body-mode full|delta|manifest`, and `--cache-offer FILE`. `methods --review-unit` retains N3's scope selector. CLI offers do not establish observed Host context and therefore cannot suppress bodies.
- `capabilities.read_protocols` declares the new protocol and modes separately from business protocol capabilities. A Host connecting to an older runtime checks this declaration first and omits the read options to use v1 if v2 is absent. Explicit unsupported requests return `read_protocol_unsupported` with the supported protocols.
- `full` is the v2 default and can always retrieve bytes again. `manifest` returns no bodies and always has `context_ready=false`. `delta` suppresses only exact kind/SHA identities offered for the adapter's matching observed session and generation. A restart, compaction, new session, missing observation, or different hash produces cold full bodies.
- The response's sole `bodies` table contains method/source/page UTF-8 bytes represented without newline normalization. Method manifests retain their frozen SHA; body references identify actual bytes. Each body has a retrieval locator and a `returned`, `omitted_by_cache_offer`, `manifest_only`, or `unavailable` state. Returning bytes or suppressing transmission never records application, authorization, consumption, or independence.
- New methods come exclusively from N3's resolver. Drift retains dispatch hashes and reports the actual readable release separately. Missing methods make that current release unavailable. Missing/corrupt source or original-image resources retain readable parts and precise refs with `context_ready=false`.

`create`/`continue` negotiation is validated before the original business function runs. Read projection uses a request-local immutable reader/decoder proxy; it does not publish disk caches, modify project compatibility, or write Task/Document/authorization/call/consumption records. The cache is discarded at the end of each response. Page bodies include full notes and mappings; original images remain exact immutable binary refs and retain actual image dimension verification.

## AC-to-evidence mapping

| AC | Executed evidence |
| --- | --- |
| AC-N4-01 | Default v1 comparison; capability declaration; structured CLI error; invalid protocol/mode/offer rejected before project directory creation and before any change to an existing project's complete file snapshot. |
| AC-N4-02 | Two pending Tasks with shared methods/sources; actual serialized complete body occurrences equal one. Role/Task sample shows each legacy method body twice and each v2 body once. All source IDs and ordered method entries retained. |
| AC-N4-03 | First full, exact observed session/generation delta, new session, new generation, no observation, changed body, manifest, and full re-fetch tests. Hydrated delta equals full. |
| AC-N4-04 | N3 manifest equality across all modes, frozen legacy selector, changed bytes, missing method, frozen dispatch digest, actual current release, and readable source retention. |
| AC-N4-05 | Compose plus real adopted-image reconstruct/page_visual/final fixtures; full v1/v2 work-order equality after dereference, full Page/notes/mappings, design/font/physical constraints, identical original artifact/file hashes and dimensions; corrupt original image, extract and Page negative cases preserve readable immutable facts. |
| AC-N4-06 | Instrumented actual `Store.read_object_bytes`, actual `json.loads`, method `Path.read_bytes`, and dispatch `Store.load_document`. Duplicate Task ref test also proves one Task decode. Probe counters and serialized sizes are in `N4A-counts.json`. |
| AC-N4-07 | Four Skill responsibilities through named/natural/Master/recovery paths, including real design/review Tasks; context/completion and complete work-order fields match v1. Full project byte snapshots unchanged by reads; delta preserves scope, capabilities, produced-against, review units, original-image refs and allowed contract facts. |

## Commands and observations

```bash
.venv/bin/python -m pytest -q tests/rebuild/test_rc4_work_context.py tests/rebuild/test_rc3_early_methods.py tests/rebuild/test_rc3_content_methods.py tests/rebuild/test_cli.py tests/rebuild/test_package_boundary.py --disable-warnings --maxfail=1
.venv/bin/python docs/reports/rc4/iteration-20261019/N4A-probe.py
```

The final combined regression command returned **64 passed** (22 N4A cases plus existing method/CLI/package checks); the resumed final run returned **64 passed in 9.74s**, recorded in `N4A-focused-tests.txt` and `N4-validation-resumed.txt`. This includes the damaged-Page fallback and actual public negotiated create/continue checks preserving persistent business protocol and writer floor. Earlier 62-case observations are superseded. The complete probe counters, Python/platform information, source SHA, exact executed source hashes and dirty-tree observation are in `N4A-counts.json`; all samples contain synthetic materials only. The probe is rerunnable and rewrites its own evidence files without retaining a generated project. Run the accompanying normalization script afterward when preparing portable evidence.

Measured double-Task response: each of two Task objects and two extract objects has exactly one real JSON decode; each of three canonical method files has one real bytes read; the shared dispatch Document has one load. Every unique complete serialized method/extract body appears once. Exact response byte counts are recorded rather than a token/cost/time improvement claim. v1 pending summaries contain only method metadata while v2 full additionally returns method bytes, so those byte totals are not a compression ratio. The same Skill/Task methods samples do contain comparable method bytes.

Deliverables: `N4A-counts.json`, `N4A-v1-pending.sample.json`, `N4A-v2-full.sample.json`, `N4A-v1-skill.sample.json`, `N4A-v2-skill.sample.json`, and the runnable probe. Runtime measurements use exact immutable extract bytes, including the extract format's own locator text; the transport does not rewrite that source format. Candidate samples have only locator strings normalized for portability. `N4-evidence-normalization.json` preserves raw/normalized file hashes and, where an embedded extract contains a locator, both body hashes. Declared resource hashes and measured byte counts identify the original runtime bytes, not the normalized display; the raw samples remain outside the repository with a SHA256 manifest.

N4B history lookup has its separate report. The final candidate commit/CI belong to the integration owner. No N4A-specific external tool, renderer, paid model, activation, or publishing step is required by these focused checks. These fixtures do not prove that a live external Host has read/applied the returned methods; an offer without separately observed context stays cold full.
