# Real Production Closure Test Evidence

## C2 Evidence — Stage / Verify / Activate / Rollback

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- `suite-install` now builds a release under `~/.deck-master/staging/`.
- The staged release must pass manifest, capability lock, checksum, required package, self-contained entrypoint, and smoke checks before activation.
- Activation moves the prior `current` release to `previous`, then moves the verified staged release to `current`.
- Activation failure attempts to restore the prior `current` release.
- `release-rollback` restores `previous` to `current` and verifies the restored release.
- `release-smoke` verifies either the current release or an explicit release root.
- Release verification ignores runtime-only files such as Python bytecode caches and `release-activation.json`.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_skill_installation` | pass | 39 installer/release tests passed |
| `HOME=<tmp>/home python3 scripts/deck_master.py suite-install --target codex` | pass | Temporary HOME install completed through staging and activation |
| `HOME=<tmp>/home python3 scripts/deck_master.py release-smoke` | pass | Activated release verified as valid |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 scripts/deck_master.py setup-status --include-suite --output json` | pass | Setup status JSON parses |
| `python3 scripts/deck_master.py suite-status --output json` | pass | Suite status JSON parses |
| `python3 -m unittest discover -s tests` | pass | 787 tests passed |

New C2 test coverage verifies:

- Tampered release checksum blocks verification.
- `suite-install` activates only a verified staged release.
- Failed staged verification leaves the existing `current` release untouched.
- Rollback restores the previous verified release.
- Smoke verification remains valid after activation metadata is written.

Accepted C2 constraint:

- C2 changes release installation semantics and release verification. It does not yet add archive packaging, CI release jobs, or RC report generation; those remain C4 scope.

## C1 Evidence — Self-Contained Release Tree

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Release tree now includes a bundled `scripts/` directory.
- Release entrypoint `bin/deck-master` resolves its own release root at runtime and calls `scripts/deck_master.py` inside the release tree.
- Release build writes `release-manifest.json`.
- Release build writes `deck_capability_lock.json`.
- Release build writes `SHA256SUMS` for release integrity checks.
- Existing `suite-build-release-tree` command remains available.
- New `release-build` command is available as the target release-building entrypoint.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_skill_installation` | pass | 35 installer/release tests passed |
| `python3 scripts/deck_master.py release-build --output <tmp>/release --force` | pass | Temporary release package built; release manifest and capability lock parse; release entrypoint starts with `--help` |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 -m unittest discover -s tests` | pass | 783 tests passed |

New C1 test coverage verifies:

- Release package contains required skills, product capabilities, contracts, scripts, manifests, capability lock, and checksum list.
- Release entrypoint does not embed the source checkout's `scripts/deck_master.py` path.
- Release entrypoint can start with `--help` from the release package.
- `SHA256SUMS` includes runtime scripts, release manifest, and capability lock.

Accepted C1 constraint:

- C1 adds self-contained release build output only. Stage, verify, activate, rollback, and release smoke behavior remain C2 scope.

## B1 Evidence — Unified Artifact Validator

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Runtime validator: `scripts/runtime/artifact_validator.py`.
- Runtime contract: `docs/contracts/artifact-validation.v1.schema.json`.
- Supported artifact checks:
  - HTML: signature/markup check.
  - PDF: `%PDF-` signature.
  - PNG: PNG magic bytes.
  - JPEG: JPEG magic bytes.
  - SVG: SVG/XML signature.
  - PPTX: zip package plus required Office parts.
  - JSON report artifacts: JSON object/array signature.
- Safety checks:
  - run-relative path only.
  - no absolute paths.
  - no path traversal.
  - file exists and is a file.
  - non-empty bytes.
  - declared byte size matches actual size.
  - declared SHA-256 matches actual checksum.
  - known media type matches artifact kind.
  - bundled placeholder content is rejected.
  - stale source fingerprint is rejected.
- Build runtime now validates artifact manifest before writing render result v2.
- `build status` revalidates artifact manifest against disk, so corrupted files change status to `invalid`.
- Run-state build summary now exposes artifact validation and marks build status `invalid` when artifact validation fails.

| Command | Result | Notes |
|---|---|---|
| `python3 -m json.tool docs/contracts/artifact-validation.v1.schema.json` | pass | Artifact validation contract parses |
| `python3 -m unittest tests.test_artifact_validator tests.test_build_runtime tests.test_run_state_resolver` | pass | 31 artifact/build/run-state tests passed |
| `python3 -m compileall scripts/runtime tests/test_artifact_validator.py tests/test_build_runtime.py` | pass | Runtime validator and related tests compile |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | Full scripts/tests compile check passed |
| `python3 scripts/deck_master.py setup-status --include-suite --output json` | pass | Setup status `ready`; suite status `degraded_ready` |
| `python3 -m unittest discover -s tests` | pass | 766 tests passed |

New B1 test cases cover:

- HTML/PDF/PNG/JPEG/SVG/PPTX signatures validate successfully.
- Path traversal is blocked.
- Empty artifacts are blocked.
- Checksum mismatch is blocked.
- Magic-byte mismatch is blocked.
- Placeholder content is blocked.
- Stale source fingerprint is blocked.
- Artifact manifest embeds validation output.
- Corrupt build artifacts make `build status` return `invalid`.

Validation note:

- A first full-test attempt failed after a temporary Stack A E2E setup changed Deck Master's global active workspace to a deleted temp directory. The setup config was restored to `/Users/dingcheng/Workspace/_internal/迈富时PPT工作坊`, then full tests passed.

## Stack A E2E Evidence — Dispatch / Bridge / Import / Build / Render

Verified on 2026-06-22 across:

- Deck Master: `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`
- PPT-Deck-Pro-Max bridge: `/Users/dingcheng/Coding-Project/02-key-project/PPT-Deck-Pro-Max-deck-master-bridge`

Flow verified:

1. Create a production Deck Master run with two generation tasks.
2. `run-generation --no-execute` writes `generation_dispatch/dispatch_package.json`.
3. PPT-Deck-Pro-Max `deck-master-import` imports the dispatch package.
4. PPT-Deck-Pro-Max `deck-master-export` copies existing assembled HTML and page screenshots into the Deck Master run and writes two canonical `deck_generation_result.v2` JSON files.
5. Deck Master `generation-session import-results` imports the result directory and refreshes preview paths.
6. Run-state reports `needs_build` after review and draft gate are satisfied.
7. `deck-master build prepare` writes build manifest, then run-state reports `needs_render`.
8. `deck-master build run` writes HTML, PDF, PNG, PPTX, artifact manifest, and canonical render result.
9. Run-state reports `ready_for_client_export`.

Observed smoke result:

| Check | Result |
|---|---|
| Dispatch package exists | pass |
| Generation result JSON count | `2` |
| Import status | `batch_imported` |
| Preview paths refreshed | `generation_results/artifacts/slide_01/preview.png`, `generation_results/artifacts/slide_02/preview.png` |
| Stage before build | `needs_build` |
| Stage after build prepare | `needs_render` |
| Stage after build run | `ready_for_client_export` |
| Build status | `completed` |
| Build page count | `2` |
| Artifact manifest | present |
| Render result v2 | present |
| Final artifacts | `deck.html`, `deck.pdf`, `deck.pptx`, page PNGs |
| Runtime build formats | `deck_html`, `deck_pdf`, `deck_pptx`, `page_png` |
| Runtime editability | `flat_image`, `native` |
| Invalid artifacts | `[]` |

Accepted smoke constraint:

- The smoke uses a temporary Deck Master workspace and manually provided PPT-side assembled HTML/screenshots to avoid relying on Playwright availability. This still exercises the real cross-repository import/export contract, Deck Master generation import, build runtime, render result v2, and A5 run-state transitions.

## A2 Evidence — PPT-Deck-Pro-Max Bridge

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/PPT-Deck-Pro-Max-deck-master-bridge`.

Coverage added:

- CLI commands:
  - `python3 scripts/run_deck_pipeline.py deck-master-import --input <run>/generation_dispatch/dispatch_package.json --project-dir <project>`
  - `python3 scripts/run_deck_pipeline.py deck-master-export --project-dir <project>`
- Bridge manifest: `deck_master_bridge.json`.
- Dispatch schema copy: `references/deck_master_dispatch_package.v1.schema.json`.
- Result schema copy: `references/deck_master_generation_result.v2.schema.json`.
- Import preserves `run_id`, `session_id`, `source_fingerprint`, task id, page id, beat id, source decision, expected outputs, quality requirements, and workspace refs.
- Export writes one `deck_generation_result.v2` JSON per task into the originating Deck Master run's `generation_results/`.
- Export copies existing PPT-side assembled HTML and screenshots into run-relative artifact paths.
- Export writes SHA-256, byte size, media type, validation status, editability, `artifact_path`, and `preview_path`.
- Safety checks block unsupported schema, missing run/session/hash, invalid source fingerprint, path-like task/page ids, output outside the Deck Master run, missing assembled HTML, and missing screenshot.

| Command | Result | Notes |
|---|---|---|
| `python3 -m json.tool references/deck_master_dispatch_package.v1.schema.json` | pass | Dispatch package schema parses |
| `python3 -m json.tool references/deck_master_generation_result.v2.schema.json` | pass | Generation result v2 schema parses |
| `python3 -m unittest tests.test_deck_master_bridge` | pass | 6 bridge tests passed |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | System Python compile check passed |
| `python3 -m unittest discover -s tests` | blocked by environment | System Python lacks `python-pptx`; existing `test_extract_layout_from_pptx` cannot import `pptx` |
| `/Users/dingcheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m compileall scripts tests` | pass | Bundled Python compile check passed |
| `/Users/dingcheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests` | pass | 150 PPT-Deck-Pro-Max tests passed |

New A2 test cases cover:

- Dispatch import preserves contract fields and writes project state.
- Export writes canonical v2 results from existing assembled HTML and screenshots.
- Missing assembled artifacts block export.
- Output outside the Deck Master run blocks export.
- Path-like task ids block import.
- CLI import and export work through `run_deck_pipeline.py`.

## A5 Evidence — Runtime & Review Workspace Integration

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Run state now exposes `awaiting_agent_execution`, `needs_build`, and `needs_render` as distinct runtime stages.
- `next-step` now carries `runtime_stage` while preserving legacy `status` values for compatibility.
- Workspace API now exposes `runtime.production_flow` with generation, build, render, artifact count, formats, editability, source fingerprint, and next command.
- Delivery preview API now exposes render v2 artifact metadata including `artifact_manifest`, `artifact_count`, `formats`, `editability`, and `source_mode`.
- Review Workspace stage selection now uses run-state for Agent, Build, and Render blockers while keeping old readiness fields available.
- UI stage workspace now shows production stage, build status, render status, formats, and editability.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_run_state_resolver tests.test_next_step tests.test_preview_server` | pass | 64 A5 runtime/workspace tests passed |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 -m unittest discover -s tests` | pass | 759 tests passed |

New A5 test cases cover:

- `awaiting_agent_execution` is surfaced as its own run-state stage.
- Fresh generation results with no build manifest return `needs_build`.
- Existing build manifest with no render result returns `needs_render`.
- `next-step` exposes `needs_build`, `needs_render`, and `runtime_stage`.
- Workspace API exposes build/render artifact metadata from render result v2.

## A4 Evidence — Build / Render Artifacts

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Runtime truth contracts:
  - `docs/contracts/build-manifest.v1.schema.json`
  - `docs/contracts/artifact-manifest.v1.schema.json`
  - `docs/contracts/render-result.v2.schema.json`
- Build runtime: `scripts/runtime/build.py`.
- CLI entry: `deck-master build prepare|run|status`.
- Production `deck-master render` now runs the A4 build path; `render --fixture-safe` keeps the legacy fixture renderer.
- Required outputs are checked for existence and non-empty bytes before a build is marked completed.
- Artifact manifest records path, media type, SHA-256, byte size, validation status, and `editability`.
- Canonical render handoff writes `render_results/render_result.json` using `deck_render_result.v2`.
- `ppt-master` capability metadata now declares both `deck_render_result.v1` and `deck_render_result.v2`.
- Render UAT accepts v1 legacy fixture results and v2 production build results.

| Command | Result | Notes |
|---|---|---|
| `python3 -m json.tool docs/contracts/build-manifest.v1.schema.json` | pass | Build manifest contract parses |
| `python3 -m json.tool docs/contracts/artifact-manifest.v1.schema.json` | pass | Artifact manifest contract parses |
| `python3 -m json.tool docs/contracts/render-result.v2.schema.json` | pass | Render result v2 contract parses |
| `python3 -m json.tool product_capabilities/ppt-master/contracts/render-result.v2.schema.json` | pass | Capability release copy parses |
| `python3 -m unittest tests.test_build_runtime tests.test_render_runtime tests.test_uat_render_tool tests.test_companion_tool_validators` | pass | 38 A4 render/build/UAT/validator tests passed |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 scripts/deck_master.py validate-product-capability-manifest` | pass | Product capability manifest remains valid |
| `python3 scripts/deck_master.py setup-status --include-suite --output json` | pass | Setup status remains `ready`; suite status remains `degraded_ready` |
| `python3 scripts/deck_master.py suite-status --output json` | pass | Suite version remains `0.9.13`; `full_suite_ready=false` |
| `python3 -m unittest discover -s tests` | pass | 755 tests passed |

New A4 test cases cover:

- `prepare_build` writes `deck_build_manifest.v1` with source fingerprint and stable page order.
- `run_build` writes HTML, PDF, page PNG, PPTX, artifact manifest, and render result v2.
- Artifact metadata includes checksum, byte size, media type, validation status, and editability.
- Render result v2 passes the shared companion validator.
- Production `render` uses the build runtime.
- Fixture-safe `render` keeps legacy v1 behavior.
- 12-page and 60-page decks build successfully.
- Missing source assets create warnings.
- Path traversal in preview assets is blocked.
- Render UAT accepts v2.
- Render validator rejects v2 results without artifacts.

Accepted A4 constraints:

- Current A4 output closes contract and lineage first. Native visual-fidelity rendering remains a later adapter task because the A0 dependency inventory showed missing Playwright/PPTX rendering libraries.

## A3 Evidence — Agent Dispatch & Handback

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Production `run-generation` writes `generation_dispatch/dispatch_package.json` and `generation_dispatch/agent_instructions.md`.
- Production bundled placeholder execution is disabled; session enters `awaiting_agent_execution`.
- Explicit `generation-session dispatch` CLI entry uses the same dispatch path.
- Fixture/dev runs can still use the bundled adapter for test-only placeholder generation.
- `generation-session import-results` accepts a single result file or a result directory.
- Every successful import writes `generation_import_receipts/*.json`.
- Duplicate imports are idempotent and marked with `duplicate_import=true`.
- Batch import can return `partial` when at least one result imports and at least one result is rejected.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_generation_session_bridge tests.test_generation_handback tests.test_run_state_resolver tests.test_uat_generation_tool tests.test_companion_tool_validators` | pass | 86 generation dispatch/handback/run-state/UAT tests passed |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 -m unittest discover -s tests` | pass | 745 tests passed |
| `git diff --check` | pass | No whitespace or patch formatting issues |

New A3 test cases cover:

- Production bundled generation dispatches without subprocess execution.
- Dispatch writes an Agent package and instruction file.
- Dry-run and no-execute paths enter `awaiting_agent_execution`.
- Fixture mode can still execute the bundled fixture adapter.
- Fixture dry-run writes an Agent dispatch package.
- Awaiting Agent state resolves as generation running.
- Successful import writes a receipt.
- Duplicate import writes a new receipt and marks the import as duplicate.
- Batch import reports partial success when one result is rejected.

## A1 Evidence — Generation Result v2

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Runtime truth contract: `docs/contracts/generation-result.v2.schema.json`.
- Canonical handback schema: `deck_generation_result.v2`.
- Legacy imports: `deck_generation_result.v1` and `ppt_deck_pro_max_generation_result.v1` normalize into v2.
- Import validation: run id, session id, run-relative paths, file existence, SHA-256 checksum, byte size, source fingerprint.
- Production guard: bundled placeholder handback content is rejected in production and benchmark modes.
- Session migration: `result_files_present`, `results_imported`, `ready_for_build`, and `awaiting_agent_execution` are readable by runtime state logic.
- CLI/UAT alignment: `validate-generation-result`, `import-generation-result`, and generation UAT use the same run-aware validator when a run directory is available.

| Command | Result | Notes |
|---|---|---|
| `python3 -m json.tool docs/contracts/generation-result.v2.schema.json` | pass | v2 runtime contract parses |
| `python3 -m unittest tests.test_generation_handback tests.test_generation_session_bridge` | pass | 39 generation handback/session tests passed |
| `python3 -m unittest tests.test_generation_handback tests.test_generation_session_bridge tests.test_companion_tool_validators tests.test_uat_generation_tool` | pass | 65 validator/UAT related tests passed |
| `python3 scripts/deck_master.py validate-product-capability-manifest` | pass | Product capability manifest remains valid |
| `python3 scripts/deck_master.py setup-status --include-suite --output json` | pass | Setup status remains `ready`; suite status remains `degraded_ready` |
| `python3 scripts/deck_master.py suite-status --output json` | pass | Suite version remains `0.9.13`; `full_suite_ready=false` |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m json.tool docs/specs/real-production-closure/implementation/baseline-lock.json` | pass | JSON parses |
| `python3 -m json.tool docs/specs/real-production-closure/implementation/implementation-spec.json` | pass | JSON parses |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 -m unittest discover -s tests` | pass | 739 tests passed |

New A1 test cases cover:

- v2 completed result imports successfully.
- v2 failed result validates successfully when it carries errors.
- run id mismatch is blocked.
- session id missing or mismatch is blocked.
- absolute/path traversal style preview paths are blocked.
- missing artifact file is blocked.
- checksum mismatch is blocked.
- stale source fingerprint is blocked.
- production placeholder content is blocked.
- legacy v1 result migrates into canonical v2.
- legacy v1 result with stale source fingerprint is blocked.
- Deck-Pro-Max v1 handback migrates into canonical v2 and refreshes preview.

## Baseline Commands

| Command | Result | Notes |
|---|---|---|
| `python3 scripts/deck_master.py validate-product-capability-manifest` | pass | Product capability manifest is valid |
| `python3 scripts/deck_master.py setup-status --include-suite --output json` | pass | Setup status is `ready`; suite status is `degraded_ready` |
| `python3 scripts/deck_master.py suite-status --output json` | pass | Suite version is `0.9.13`; `full_suite_ready=false` |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m json.tool docs/specs/real-production-closure/implementation/baseline-lock.json` | pass | JSON parses |
| `python3 -m json.tool docs/specs/real-production-closure/implementation/implementation-spec.json` | pass | JSON parses |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 -m unittest discover -s tests` | pass | 733 tests passed |

## Dependency Snapshot

| Dependency | Result |
|---|---|
| Python | `3.14.5` |
| Node | `v22.22.3` |
| npm | `10.9.8` |
| soffice | `/opt/homebrew/bin/soffice` |
| python module `pptx` | missing |
| python module `jsonschema` | missing |
| node module `playwright` | missing |
| node module `pptxgenjs` | missing |

## Repository Normalization

The imported planning pack had trailing whitespace in:

- `docs/deck-master-real-production-closure-spec-pack/README.md`
- `docs/deck-master-real-production-closure-spec-pack/combined-spec.md`

The repository copy removed those trailing spaces so `git diff --check` can pass. The source zip remains available at `/Users/dingcheng/Downloads/deck-master-real-production-closure-spec-pack.zip`.

## Re-run Commands

```bash
git diff --check
python3 -m json.tool docs/contracts/build-manifest.v1.schema.json
python3 -m json.tool docs/contracts/artifact-manifest.v1.schema.json
python3 -m json.tool docs/contracts/artifact-validation.v1.schema.json
python3 -m json.tool docs/contracts/render-result.v2.schema.json
python3 -m json.tool product_capabilities/ppt-master/contracts/render-result.v2.schema.json
python3 -m json.tool docs/specs/real-production-closure/implementation/baseline-lock.json
python3 -m json.tool docs/specs/real-production-closure/implementation/implementation-spec.json
python3 -m compileall scripts tests
python3 -m unittest discover -s tests
```

All commands above passed on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

## B2 Evidence — Delivery Validation & Lineage

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Delivery validation now validates the final artifact through the shared artifact validator.
- Final artifacts must stay inside the run directory.
- Missing, invalid, corrupted, unparsable, and empty artifacts block delivery.
- PPTX page count mismatches block delivery.
- Blocking quality gates block delivery.
- Build artifact manifest failures block delivery.
- Stale source fingerprints across build manifest, artifact manifest, and render result block delivery.
- Every successful validation writes `delivery/final_version_lineage.json`.
- Runtime contract added: `docs/contracts/final-version-lineage.v1.schema.json`.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_delivery_validation` | pass | 11 B2 delivery validation tests passed |
| `python3 -m json.tool docs/contracts/final-version-lineage.v1.schema.json` | pass | Final version lineage contract parses |

New B2 test cases cover:

- Missing final artifact returns P0.
- Page count mismatch returns P1.
- Valid final HTML passes without expected page count.
- Lineage file is written with artifact validation.
- Quality gate reports are read into lineage.
- Invalid PPTX is rejected by artifact validation and parse validation.
- Artifact outside the run directory is rejected.
- Invalid build artifact manifest blocks delivery.
- Stale source fingerprint blocks delivery.

## B3 Evidence — Final Readiness

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Runtime readiness module added at `scripts/runtime/final_readiness.py`.
- Canonical readiness output added at `delivery/final_readiness.json`.
- Runtime contract added: `docs/contracts/final-readiness.v1.schema.json`.
- CLI entry added: `deck-master final-readiness`.
- Final readiness consumes run-state, render result, delivery validation, lineage, quality gates, and page-count consistency.
- `ready=true` is only emitted when no blocker remains.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_final_readiness` | pass | 6 B3 final readiness tests passed |
| `python3 -m json.tool docs/contracts/final-readiness.v1.schema.json` | pass | Final readiness contract parses |

New B3 test cases cover:

- Ready run writes `delivery/final_readiness.json`.
- Missing render blocks readiness.
- Blocking quality gate blocks readiness.
- Approved page count mismatch blocks readiness.
- No-write mode returns readiness without writing `final_readiness.json`.
- Schema version stays stable.

## B4 Evidence — Export & Workbench Readiness Enforcement

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- Client export now enforces `delivery/final_readiness.json`.
- Missing or blocked final readiness moves matching client export pages to `blocked_pages`.
- Internal export remains available and is marked as degraded when final readiness is missing or blocked.
- `deck-master export` refreshes final readiness before client export.
- Workspace delivery preview reads final readiness before marking artifacts ready.
- Workspace stage, production flow, delivery preview API, and preview UI surface final readiness status and reason.
- Benchmark reports include final readiness status in the readiness section.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_export_quality_blocking tests.test_review_cockpit tests.test_review_workbench tests.test_orchestration tests.test_final_readiness tests.test_benchmark_report tests.test_preview_server tests.test_workspace_audit_scenarios` | pass | 112 B4 related tests passed |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 -m unittest discover -s tests` | pass | 778 tests passed |

New B4 test cases cover:

- Missing final readiness blocks client export.
- Internal export marks degraded when final readiness is missing.
- Existing quality blocking tests pass only when final readiness fixture is ready.

## B5 Evidence — Fixture/Dev/Production Isolation

Implemented on 2026-06-22 in `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master-real-production-closure`.

Coverage added:

- PPT Library fixture fallback is blocked for production and benchmark runs, including explicit fallback flags.
- `import-sourcing` rejects `manual_placeholder` decisions for production and benchmark runs.
- Preview build rejects production/benchmark sourcing plans that contain `manual_placeholder`.
- `render --fixture-safe` is blocked for production and benchmark runs.
- Fixture/dev paths retain fixture rendering and manual placeholder import behavior for tests and demos.

| Command | Result | Notes |
|---|---|---|
| `python3 -m unittest tests.test_ppt_library_client tests.test_planner_sourcing_controls tests.test_build_runtime tests.test_generation_session_bridge` | pass | 42 B5 strict-mode tests passed |
| `python3 -m unittest tests.test_end_to_end_autoplan tests.test_sourcing_decider tests.test_orchestration tests.test_preview_server` | pass | 38 adjacent fixture/preview tests passed |
| `git diff --check` | pass | No whitespace or patch formatting issues |
| `python3 -m compileall scripts tests` | pass | Python files compile |
| `python3 -m unittest discover -s tests` | pass | 783 tests passed |

New B5 test cases cover:

- Production mode blocks explicit PPT Library fixture fallback.
- Benchmark mode blocks fixture library mode.
- Production import-sourcing blocks `manual_placeholder`.
- Fixture import-sourcing allows `manual_placeholder`.
- Production preview build blocks `manual_placeholder`.
- Production render blocks `--fixture-safe`.
