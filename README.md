# Deck Master

Deck Master is a local-first Solution Deck Run OS. It turns a brief, source context, page plan, generation handoff, Review Desk decisions, build artifacts, and final readiness into one traceable workflow.

**Status:** v0.9.14-preview.4 / Technical Preview (agent-operable).
**License:** Apache-2.0.
**Support:** best-effort during preview.

Version mapping for this preview:

- GitHub release label: `v0.9.14-preview.4`
- Python package version: `0.9.14a4`
- Release notes: [v0.9.14-preview.4](docs/releases/v0.9.14-preview.4-release-notes.md)
- Release stage: Technical Preview / agent-operable
- Production readiness: not claimed

## Who It Is For

Deck Master is built for solution architects and proposal builders who need a repeatable way to decide which pages should be generated, which pages should be reused, and which pages are ready for review or delivery.

## SC-1.1: Built-in Native Deck Core

As of SC-1.1, the default production build engine is the **built-in `deck_native`
compiler** (SVG subset -> native PPTX with real traces and readback) —
no external PPT Master install, binding or repository is required for
default production. Legacy `legacy-ppt-master` is an explicit
compatibility route only. Runs without an image-generation host tool
report `awaiting_agent_imagegen` honestly; the built-in kernel and the
default route are probed for real capability evidence, never from env
flags.

Real rendering uses LibreOffice → PDF → `pdftoppm` PNG with an isolated LibreOffice
profile. Compiler, renderer, fonts and host tools have separate readiness evidence.
A completed build is not final approval. SC-1.1 engineering acceptance remains
`in_progress` until the required evidence and human visual review are complete.

For page repair, use `build retry --run-dir <run> --page-id P001 --stage svg`.
The host returns both SVG and Scene with the issued action identity; default
budgets allow three attempts per page/action kind, including failures and cancelled
issued work. `build cancel --run-dir <run> --action-id <issued-action> --reason
"<reason>"` stops that action; polling and `build run` cannot silently restart it.
Only an explicit page/stage retry resumes within the remaining budget.
Unprofiled fixture/dev previews retain their `fixture_html` route. They cannot
be relabeled production by changing the request mode.

Published runtime installation uses exact wheel hashes in `requirements/`;
compiler, rendering and font probes still execute against the actual host.
Source extraction must retain file hashes and read/unread ranges. A critical
unread range blocks the Brief and continuation until a complete, version-bound
Context Pack is imported. Business goals alone produce pending professional
analysis tasks, not completed causal judgments.
Migration is explicit: `build migrate --dry-run --output <plan.json>`, then
`--apply --plan <plan.json>`, `--verify --migration-id <id>` or
`--rollback --migration-id <id>` (all with `--run-dir <run>`).

## The Full SC-1 Chain

Provide raw material + business goal + authorized host tools; Deck Master
carries the rest of the chain in one workflow — you do not write page drafts,
invoke external named skills, or know backend paths:

1. `start-conversation` ingests your raw material (full-text reading with
   coverage registration; PDF/DOCX/PPTX/images via host extraction tasks).
2. `build-brief` + research tasks: gaps are either filled from the material
   itself, turned into bounded research tasks (redaction-guarded), or surfaced
   as precise decisions — the material's tail constraints are never truncated
   away.
3. `autoplan` builds the solution model and narrative from the material, with
   candidate storylines and an explicit recommendation (or a truthful
   single-viable-path note).
4. The producer writes complete Page Packages (conclusion, business
   implication, evidence bindings) — production instructions never enter page
   text; pages without evidence or design basis stay draft.
5. New builds consume approved Page Packages through `deck_native`. The default
   `image_blueprint` path requests actual host images and SVG + Scene reconstruction;
   explicit `direct_svg` skips image generation. Existing legacy routes are preserved.
6. Semantic review v2 (six dimensions) is a required production gate; a
   content change stales its binding; P0 findings cannot be overridden.
7. Export requires current final readiness + hash-bound delivery approval.
   Hidden notes/metadata in the client PPTX are scanned and block delivery.

Status and honest limits: see [Known Limitations](docs/known-limitations.md).
Engineering evidence: `docs/specs/sc1-solution-core-independence/implementation/`.

## Install

Use Python 3.12 by default for the Technical Preview. Deck Master preview
commands are tested on Python 3.11 and 3.12, but real PPT Library v2
integration requires Python 3.12+. Python 3.14 is not a supported test
environment because the PPTX dependency chain may not have compatible wheels
yet.

```bash
python3.12 -m venv .venv
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

The demo uses fixture mode and synthetic retail transformation content. It is the default first-run path for v0.9.14-preview.4.

## Review Desk

Review Desk is the local browser interface for inspecting the generated page queue, checking page status, and approving work before export. M1 focuses on a public fixture demo and Review Desk preview. M2 will close the full production backend and release-candidate gates.

![Review Desk](docs/assets/review-desk.png)

Review Desk write operations use a per-server local write token and same-origin guard. The server binds to `127.0.0.1` by default; non-loopback hosts require `--allow-remote-preview` and are only for trusted local-network demos. The write token is not a network authentication boundary because any browser that can load the page can read it.

For the full user path (install, demo, Review Desk, production configuration), see the [User Guide](docs/user-guide.md).

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

## Before Real Production Use

The preview demo is fixture-safe. Before using real customer material or
production deck assets, confirm these items explicitly:

1. Use Python 3.12 when integrating PPT Library v2.
2. Register and validate an active workspace; do not index Downloads, caches,
   raw customer folders, or private benchmark sources unless the user confirms
   that scope.
3. Confirm source authorization before indexing PPT files, screenshots,
   historical proposals, or customer context.
4. Check Agent and suite readiness:

```bash
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py suite-status --target codex --output json
python3 scripts/deck_master.py agent-doctor --mode production --output json
```

5. Use the persisted build route. New runs default to the native engine and
   `image_blueprint`; `direct_svg` shares the native compile/render chain.
   Verify real compiler, renderer and font capabilities before production:

```bash
python3 scripts/deck_master.py agent-doctor --mode production --run-dir <run_dir> --output json
python3 scripts/deck_master.py build status --run-dir <run_dir>
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
```

Only an explicitly selected `legacy-ppt-master` run needs `backend bind` and
`backend verify ppt-master`. The former global PPT Master prerequisite is
superseded by [SC-1.1 routing](docs/specs/sc1.1-native-deck-core/DEVELOPMENT_SPEC.md).
If production readiness is blocked, repair the reported blocker. A production
run cannot be relabelled fixture/dev to bypass its original delivery policy.

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

M1 uses `preview-gate` for v0.9.14-preview.4.
M2 uses `rc-gate` for formal release-candidate validation.

```bash
python3 scripts/deck_master.py rc-gate --output-dir /tmp/deck-master-rc --benchmark-dir benchmarks --skip-browser-smoke --force
```

## Project Docs

- [Quick Start](docs/quick-start.md)
- [Agent Entry](AGENTS.md)
- [Agent Task Index](docs/agent-task-index.md)
- [Known Limitations](docs/known-limitations.md)
- [PPT Library v2 Integration](docs/integration/ppt-library-v2.md)
- [PPT Master Integration](docs/integration/ppt-master.md)
- [Release Checklist](docs/releases/2026-07-06-release-checklist.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
