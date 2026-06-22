# Deck Master

Deck Master is a local-first Solution Deck Run OS. It turns a brief, source context, narrative plan, generation handoff, build/render artifacts, review status, and final delivery readiness into one traceable workflow.

## Current Production Closure

This branch contains the Real Production Closure iteration:

- Production generation handoff uses `deck_generation_result.v2`.
- Production generation dispatch waits for an external Agent result instead of writing bundled placeholder output.
- Build/render writes contract-checked HTML, PDF-signature, PNG-signature, PPTX package, artifact manifest, and render result v2.
- Final delivery uses one readiness gate: `delivery/final_readiness.json`.
- Client export is blocked unless final readiness is ready.
- Release trees are self-contained and can be installed through staging, verification, activation, and rollback.
- RC gate produces one report covering schema parse, artifact validator, release smoke, fixture E2E, optional browser smoke, and benchmark aggregate readiness.

## Start Here

- [Quick Start](docs/quick-start.md)
- [Agent Guide](docs/agent-guide.md)
- [Migration Guide](docs/migration/real-production-closure.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Release Notes](docs/releases/v0.9.14-real-production-closure.md)

## Core Commands

```bash
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py suite-status --output json
python3 scripts/deck_master.py release-build --output /tmp/deck-master-release --force
python3 scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
```

## Current Boundaries

- Private benchmark source documents are not committed. Only sanitized metadata and local source paths are stored.
- Browser smoke is optional unless `--require-browser-smoke` is used.
- Native visual-fidelity rendering remains adapter work. The current runtime closes artifact contracts, lineage, readiness, and release validation.
