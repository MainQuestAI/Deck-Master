# PPT Master Integration

PPT Master is the production build/render backend for Deck Master. The public
Technical Preview does not claim production readiness until this backend is
configured and verified.

## Backend Binding

Inspect current backend state:

```bash
python3 scripts/deck_master.py backend status
```

Bind a local PPT Master backend repository:

```bash
python3 scripts/deck_master.py backend bind ppt-master --repo <ppt-master-backend>
```

Re-run certification:

```bash
python3 scripts/deck_master.py backend verify ppt-master
```

If backend status is `unbound`, `not_configured`, or `blocked`, do not report
production build/export readiness. Use fixture/demo mode or repair the blocker.

## Build And Render Path

After preview review and quality gates, use the Deck Builder flow:

```bash
python3 scripts/deck_master.py build prepare --run-dir <run_dir>
python3 scripts/deck_master.py build run --run-dir <run_dir>
python3 scripts/deck_master.py build status --run-dir <run_dir>
```

PPT Master handback results must be imported through Deck Master:

```bash
python3 scripts/deck_master.py import-render-result \
  --run-dir <run_dir> \
  --input <render_result.json>
```

## Verification

```bash
python3 scripts/deck_master.py agent-doctor --mode production --output json
python3 scripts/deck_master.py final-readiness --run-dir <run_dir> --no-write
python3 scripts/deck_master.py release-build --output /tmp/deck-master-release --force
python3 scripts/deck_master.py release-smoke --release-root /tmp/deck-master-release
```

Production delivery requires `agent-doctor --mode production` and
`final-readiness` to report no blockers.
