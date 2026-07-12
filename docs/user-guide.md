# Deck Master User Guide

This guide walks through the full user path: install, run the public demo,
use the Review Desk, and understand production configuration. For command
routing and agent usage, see `AGENTS.md`; for current boundaries, see
`docs/known-limitations.md`.

Deck Master is a **Technical Preview** (agent-operable). Production readiness
is not claimed. The fixture demo and Review Desk preview are the supported
first-run paths.

## 1. Install

Use Python 3.12 by default. Preview commands are tested on 3.11 and 3.12;
real PPT Library v2 integration requires 3.12+. Python 3.14 is not supported
(the PPTX dependency chain may lack compatible wheels).

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

uv equivalent (if local Python cannot bootstrap pip):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Install Playwright Chromium for the Review Desk browser smoke (optional but
recommended):

```bash
python -m playwright install --with-deps chromium
```

After install, `deck-master ...` is equivalent to `python3 scripts/deck_master.py ...`.

A `Makefile` wraps the common targets: `make install-dev`, `make test`,
`make smoke`, `make release-smoke`, `make rc-gate-ci`, `make preview`.

## 2. Run the public demo

The demo uses fixture mode with synthetic retail transformation content. It is
the default first-run path and needs no configured production backend.

```bash
bash scripts/demo.sh
python3 scripts/deck_master.py preview-gate \
  --run-dir /tmp/deck-master-demo/oss-demo \
  --expect-unconfigured-backend-ok
```

`preview-gate --expect-unconfigured-backend-ok` confirms the fixture demo is
reviewable without a production backend. It is the M1 public-demo gate.

## 3. Use the Review Desk

The Review Desk is the local browser interface for inspecting the page queue,
reviewing pages, and approving work before export. It binds to `127.0.0.1` by
default.

```bash
python3 scripts/preview/server.py /tmp/deck-master-demo/oss-demo
# or, for the bundled fixture run:
python3 scripts/preview/server.py examples/preview-run --port 5050
```

Open `http://127.0.0.1:5050/`. The left rail is the task directory (page
queue); the center column is the current page preview; the right rail is the
decision panel (approve / reject / request evidence / escalate). The bottom
drawer holds run-level readiness, claim coverage, activity, build skill,
artifact, and export panels.

What the Review Desk shows:

- **Page queue and status** — which pages are pending, approved, or blocked.
- **Stage and next step** — the current Skill OS stage and the next agent
  action (or a clear blocked reason).
- **Quality and risk** — blocker cards when quality gates or final-readiness
  block delivery.
- **Delivery readiness** — whether the run is exportable, and why not if it
  is not.

Write operations (approve, reject, submit) require the per-server local write
token, injected into the page. Non-loopback hosts require
`--allow-remote-preview` and are for trusted local-network demos only; the
write token is not a network authentication boundary.

## 4. Understand the production path

The fixture demo does not exercise the production backend. Production deck
production requires companion backends to be configured and verified.

Check backend and suite state (these never claim ready unless the JSON says so):

```bash
python3 scripts/deck_master.py setup-status
python3 scripts/deck_master.py suite-status --output json
python3 scripts/deck_master.py backend status
python3 scripts/deck_master.py agent-doctor --mode production --output json
```

To bind and verify the PPT Master production backend, see
`docs/integration/ppt-master.md`. A missing or unverified `ppt-master` backend
must not be reported as `bound_verified`.

The full production workflow is:

```text
brief / context intake
  -> deck brief / claim map
  -> narrative plan / page tasks
  -> PPT Library sourcing
  -> generation / production
  -> PPT Master build / render
  -> quality gates
  -> Review Desk approval
  -> final-readiness pass
  -> export / delivery package
```

Each stage has a runtime contract under `docs/contracts/` and a Skill task
schema under `skills/deck-master/schemas/`. Prefer the machine-readable
commands in `AGENTS.md` over inferring state from prose.

## 5. Release-candidate gates

Two tiers of `rc-gate` exist:

- **Full tier** (default): runs all checks, including `benchmark_aggregate`
  and `external_dependency_closure`, which require local-only benchmark
  results and a bound production backend. Use locally / at release.
- **CI tier** (`--tier ci`): runs only the reproducible subset and skips the
  local-only checks, so a fresh clone can go green. Use in PR/CI.

```bash
python3 scripts/deck_master.py rc-gate --tier ci --skip-browser-smoke --force
python3 scripts/deck_master.py rc-gate --require-browser-smoke --force   # full, local
```

Release tree build and smoke:

```bash
python3 scripts/deck_master.py release-build --output /tmp/deck-master-release --force
python3 scripts/deck_master.py release-smoke --release-root /tmp/deck-master-release
python3 scripts/deck_master.py release-install      # staged install + smoke
python3 scripts/deck_master.py release-rollback     # restore previous release
```

## 6. Where to look next

- `AGENTS.md` — task routing, safety boundaries, machine-readable commands.
- `docs/known-limitations.md` — current M1/M2 boundaries.
- `docs/integration/ppt-master.md` — production backend bind/verify.
- `docs/releases/2026-07-09-1.0.0-iteration-plan.md` — 1.0.0 roadmap.
- `docs/releases/v1.0.0-rc.1.md` — evidence classification (tracked / CI /
  local-only).
- `ROADMAP.md` — milestones.
