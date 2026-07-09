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

## Clean-Environment Reproducible Bind

For a 1.0.0 release, the PPT Master backend must be bindable and verifiable
from a clean environment (a fresh clone, no machine-specific paths). The
canonical public source is the PPT Master repository; pin to a tagged
release or the default branch plus a recorded commit SHA rather than a
local worktree path.

Reproducible bind path for an external user:

```bash
# 1. Clone the PPT Master backend at a pinned ref.
git clone https://github.com/hugohe3/ppt-master.git /opt/ppt-master
cd /opt/ppt-master && git checkout <pinned-tag-or-sha>

# 2. Bind it into Deck Master (records repo_path + git_sha + verified flag).
python3 scripts/deck_master.py backend bind ppt-master --repo /opt/ppt-master

# 3. Re-run certification (render / smoke / writeback capabilities).
python3 scripts/deck_master.py backend verify ppt-master

# 4. Confirm the suite reports production_backend_ready.
python3 scripts/deck_master.py suite-status --output json
python3 scripts/deck_master.py agent-doctor --mode production --output json
```

After bind + verify, `suite-status` must report `production_backend_ready: true`
with `ppt-master` `binding_status: bound_verified`, a non-empty `git_sha`, and
`verified: true`. The rc-gate `external_dependency_closure` check (full tier)
then compares the live binding against the release tree's
`deck_capability_lock.json` snapshot; they must match.

Note: the local development binding on a maintainer machine may point at a
worktree on a feature branch (e.g. `codex/deck-master-backend-certification`).
That is a maintainer convenience and is not reproducible for external users.
For release, replace the worktree path with a clone of the public repository
at a pinned tag/SHA, and record that SHA in the release manifest. Live
clean-environment verification of the public repo is performed out-of-tree
(the PPT Master repository is a separate project); this section documents the
reproducible path Deck Master expects.
