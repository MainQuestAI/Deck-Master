# Deck Master Quick Start

This guide covers the implemented Real Production Closure path.

## 1. Check Local Readiness

```bash
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py suite-status --output json
```

Expected result:

- setup status JSON parses.
- suite status returns a readable readiness result.
- missing companion skill links can be repaired with `suite-install`.

## 2. Install Or Repair The Suite

```bash
python3 scripts/deck_master.py suite-install --target codex
```

The install path now builds a staged release, verifies it, activates it as `~/.deck-master/current`, and keeps the prior release as `~/.deck-master/previous`.

Rollback:

```bash
python3 scripts/deck_master.py release-rollback
```

Smoke check:

```bash
python3 scripts/deck_master.py release-smoke
```

## 3. Build A Self-Contained Release Tree

```bash
python3 scripts/deck_master.py release-build --output /tmp/deck-master-release --force
/tmp/deck-master-release/bin/deck-master --help
```

The release tree includes:

- `bin/deck-master`
- `scripts/`
- `skills/`
- `capabilities/`
- `contracts/`
- `release-manifest.json`
- `deck_capability_lock.json`
- `SHA256SUMS`

## 4. Initialize A Project Workspace

```bash
python3 scripts/deck_master.py init-project --workspace <workspace> --name <project>
python3 scripts/deck_master.py route-skill --input-type raw_materials
```

`init-project` creates customer material, meeting, AI process, reference, delivery, quality, and `.deck-master` metadata directories. It is idempotent and keeps existing user files.

## 5. Use The v1 Skill Route

```bash
python3 scripts/deck_master.py next-step --run-dir <run_dir>
python3 scripts/deck_master.py route-skill --run-dir <run_dir>
python3 scripts/deck_master.py workflow-autopilot --mode quick --run-dir <run_dir>
```

`next-step` and `route-skill` now return `recommended_skill`, `skill_stage`, and `skill_route`. Build stages route to `deck-builder`; raw material routes to `deck-brief`; final delivery routes to `deck-review`.

## 6. Production Generation Handoff

Production generation creates an Agent dispatch package and waits for an external result.

```bash
python3 scripts/deck_master.py run-generation --run-dir <run_dir> --no-execute
```

Expected output inside the run:

- `generation_dispatch/dispatch_package.json`
- `generation_dispatch/agent_instructions.md`

Import a result:

```bash
python3 scripts/deck_master.py generation-session import-results --run-dir <run_dir> --input <result_or_dir>
```

The imported result must match `deck_generation_result.v2`, run/session ids, checksum, and run-relative artifact paths.

## 7. Build, Render, Readiness, Export

```bash
python3 scripts/deck_master.py build prepare --run-dir <run_dir>
python3 scripts/deck_master.py build run --run-dir <run_dir>
python3 scripts/deck_master.py final-readiness --run-dir <run_dir>
python3 scripts/deck_master.py export --run-dir <run_dir>
```

Client export requires final readiness to be ready. Internal export can continue with degraded marking when needed.

## 8. RC Gate

```bash
python3 scripts/deck_master.py rc-gate \
  --output-dir /tmp/deck-master-rc \
  --benchmark-dir benchmarks \
  --skip-browser-smoke \
  --force
```

The RC gate writes:

- `rc_gate_report.json`
- `rc_gate_report.md`

Use `--require-browser-smoke` only when Playwright/browser runtime is available and must be enforced.
