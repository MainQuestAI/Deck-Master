# Deck Master

Deck Master is a local-first Solution Deck Run OS. It turns a brief, source context, page plan, generation handoff, Review Desk decisions, build artifacts, and final readiness into one traceable workflow.

**Status:** v0.9.14-preview.1 / Technical Preview (agent-operable).
**License:** Apache-2.0.
**Support:** best-effort during preview.

## Who It Is For

Deck Master is built for solution architects and proposal builders who need a repeatable way to decide which pages should be generated, which pages should be reused, and which pages are ready for review or delivery.

## Install

Use Python 3.11 or 3.12 for the Technical Preview. Python 3.14 is not a
supported test environment because the PPTX dependency chain may not have
compatible wheels yet.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If local Python cannot bootstrap pip in a venv, use the equivalent uv path:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Source checkout commands use `python3 scripts/deck_master.py ...`. After the
editable install above, the equivalent installed command is `deck-master ...`.

## Run The Public Demo

```bash
bash scripts/demo.sh
python3 scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
python3 scripts/preview/server.py /tmp/deck-master-demo/oss-demo
```

The demo uses fixture mode and synthetic retail transformation content. It is the default first-run path for v0.9.14-preview.1.

## Review Desk

Review Desk is the local browser interface for inspecting the generated page queue, checking page status, and approving work before export. M1 focuses on a public fixture demo and Review Desk preview. M2 will close the full production backend and release-candidate gates.

## Capability Boundaries

Current M1 guarantees:

1. Fixture demo from a public brief.
2. Review Desk preview for that demo.
3. Backend readiness transparency through `setup-status`, `suite-status`, and `backend status`.
4. `preview-gate` that works without a configured production backend.

Current M1 limits:

1. Production backend companions must be configured and verified before production commands can be treated as ready.
2. A missing `ppt-master` production backend must not be reported as `bound_verified`.
3. `ppt-deck-pro-max` is a Deck Master suite Skill for page production, not a separately bound production backend.
4. Browser smoke depends on local Playwright/browser availability.

See [Known Limitations](docs/known-limitations.md).

## Core Commands

```bash
python3 scripts/deck_master.py --help
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py suite-status --output json
python3 scripts/deck_master.py autoplan --brief-file examples/briefs/retail_digital_transformation.txt --industry retail --library-mode fixture --run-mode fixture --dev-allow-unsetup --runs-dir /tmp/deck-master-demo --run-id oss-demo
python3 scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

After install, `deck-master --help` is equivalent to the source checkout help command.

## Release Gates

M1 uses `preview-gate` for v0.9.14-preview.1.
M2 uses `rc-gate` for formal release-candidate validation.

```bash
python3 scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
```

## Project Docs

- [Quick Start](docs/quick-start.md)
- [Known Limitations](docs/known-limitations.md)
- [Release Checklist](docs/releases/2026-07-06-release-checklist.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
