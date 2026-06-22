# Deck Master Agent Guide

This guide is for Codex, Claude Code, and other local coding agents working on Deck Master runs.

## Operating Rules

- Treat `docs/contracts/` as the runtime contract source of truth.
- Treat `product_capabilities/*/contracts/` as capability release copies.
- Treat `skills/deck-master/schemas/` as Agent task schemas.
- Do not write production placeholder artifacts.
- Do not use fixture fallback in production or benchmark mode.
- Do not commit private benchmark source documents, generated runs, generated reports, caches, tokens, or local env files.

## Skill Routing

Use public `deck-*` names for new workflows:

- `deck-init`: project workspace and material directories.
- `deck-brief`: raw material to brief and claim inputs.
- `deck-planner`: narrative, sections, page tasks.
- `deck-sourcing`: reuse/adapt/generate decisions.
- `deck-producer`: generation session and result import.
- `deck-builder`: build artifacts through the PPT Master backend.
- `deck-quality`: quality gates and customer-visible safety.
- `deck-review`: final readiness, repair queue, and export.
- `deck-autopilot`: continuous workflow until a safe stop condition.

Use these commands to route instead of guessing:

```bash
python3 scripts/deck_master.py route-skill --input-type raw_materials
python3 scripts/deck_master.py next-step --run-dir <run_dir>
```

Legacy `ppt-*` entries remain valid compatibility names. Prefer `deck-builder` in user-facing text; mention `ppt-master` only as the full backend dependency.

## Generation Handoff

Production generation uses this state flow:

```text
generation_session created
-> awaiting_agent_execution
-> external Agent writes deck_generation_result.v2
-> Deck Master imports result
-> needs_build
```

The external Agent result must provide:

- `schema_version: deck_generation_result.v2`
- matching `run_id`
- matching `session_id`
- matching source fingerprint
- run-relative artifact paths
- SHA-256 and byte size for artifacts

Deck Master rejects absolute paths, path traversal, checksum mismatch, stale source fingerprint, and bundled placeholder content.

## Build And Render

Use:

```bash
python3 scripts/deck_master.py build prepare --run-dir <run_dir>
python3 scripts/deck_master.py build run --run-dir <run_dir>
```

The build path writes:

- `build/build_manifest.json`
- `artifacts/artifact_manifest.json`
- `render_results/render_result.json`

Every artifact is checked by the shared artifact validator.

## Final Readiness

Use:

```bash
python3 scripts/deck_master.py final-readiness --run-dir <run_dir>
```

Final readiness is the single client-export gate. It combines render result, delivery validation, lineage, artifact validity, page count, and quality blockers.

## Release Work

Use:

```bash
python3 scripts/deck_master.py release-build --output <release_dir> --force
python3 scripts/deck_master.py release-smoke --release-root <release_dir>
python3 scripts/deck_master.py suite-install --target codex
```

`suite-install` uses staged activation. If verification fails before activation, the existing current release remains untouched. If activation fails, Deck Master attempts to restore the previous release.

## RC Work

Use:

```bash
python3 scripts/deck_master.py rc-gate --output-dir <out_dir> --benchmark-dir benchmarks --skip-browser-smoke --force
```

RC gate checks:

- JSON contract and case parsing.
- Artifact validator smoke.
- Self-contained release smoke.
- Fixture autoplan E2E.
- Optional browser smoke.
- Benchmark aggregate readiness.

For environments with Playwright available:

```bash
python3 scripts/deck_master.py rc-gate --output-dir <out_dir> --benchmark-dir benchmarks --require-browser-smoke --force
```
