# Installation

The rebuilt Python package exposes one CLI: `deck-master` or `python -m deck_master`.
For development, use Python 3.11 or 3.12 and `python -m pip install -e '.[dev]'`.
A release used from Codex also needs its managed Skill registration.

## Candidate, activation and rollback

Build and check the candidate first. `install candidate` creates an isolated
virtual environment, extracts `skill/deck-master/` from the wheel, and runs
compile/render/compose/view checks. It does not activate or register the Skill.

```bash
python tools/build_release.py --out /path/to/new-release
python -m deck_master install candidate \
  --prefix /path/to/prefix --manifest /path/to/new-release/release.json
python -m deck_master install activate \
  --prefix /path/to/prefix --release-id <release_id>
/path/to/prefix/.deck-master/bin/deck-master doctor --step compose
/path/to/prefix/.deck-master/bin/deck-master install rollback --prefix /path/to/prefix
```

For the normal personal installation, `--prefix "$HOME"` produces
`~/.deck-master/bin/deck-master`. Use the chosen prefix's launcher when using
another prefix. Activation manages exactly one link:
`$CODEX_HOME/skills/deck-master` (default `~/.codex/skills/deck-master`) to
`<prefix>/.deck-master/current/skill/deck-master`.
A real directory/file or a foreign link at that path is a `host_skill_conflict`
(exit 5); resolve the named conflict before retrying. `--no-host-registration`
skips registration for CI and reports CLI and Host status separately.
No config.toml changes, other Host registrations or third-party Skill changes occur.

Rollback follows `previous` and keeps method and CLI releases aligned. If the
previous release predates the Skill, the managed link is removed and the result
reports `host_skill_unregistered`. Project data and recorded calls are not rolled back.

## Legacy companion layout

Activation recognizes a real `current/` containing only
`companion-manifest.json` with schema `deck_master_companion_manifest.v3` and
`bundled_symlink_only` on its Deck Skill rows. The policy is nested in `skills[]`;
it is not a top-level manifest field. Other directory contents are refused.
The old directory moves to `legacy-companion-<timestamp>` and remains available.
Only `deck-*` symlinks targeting the exact old `current/skills/` subtree are
removed, with each move, removal and skipped entry reported. Retry is idempotent.

Run migration tests with an isolated HOME and CODEX_HOME. Actual installation
migration and the seven-step new Codex session are user-run acceptance checks;
passing package tests is not evidence that either was completed.

## Tools and old runs

```bash
deck-master doctor --step compose
deck-master doctor --step render
deck-master legacy-map
```

Missing renderers/fonts report `needs_tool`. Old run directories report
`legacy_run_format`; use `deck-master import legacy --input <old-run> --out <new>`
or pin a compatible old release. Never initialize or migrate an old run in place.
