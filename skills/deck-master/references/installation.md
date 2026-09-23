# Installation

The rebuilt core installs as a normal Python package; the `deck-master`
console entry and `python -m deck_master` are the same CLI. There is no
suite-linking step and no first-run setup.

## Editable Install (development)

```bash
python -m pip install -e ".[dev]"
deck-master --version
deck-master doctor --step compose   # content inputs
deck-master doctor --step render    # renderer toolchain
```

Renderer or font gaps are reported per step as `needs_tool` with the real
reason — nothing silently falls back to fixtures.

## Candidate Releases (staging → activate → rollback)

Release candidates are built with `tools/build_release.py` and installed into
an isolated prefix. Activation creates per-release virtual environments; no
`.agents/skills` link maintenance is required — activated candidates expose
the `deck-master` entry from their own venv.

```bash
python tools/build_release.py --out /path/to/release        # wheel + release.json
python -m deck_master.cli install candidate \
  --prefix ~/.deck-master-candidates --manifest /path/to/release/release.json
python -m deck_master.cli install activate \
  --prefix ~/.deck-master-candidates --release-id <release_id>
# doctor proves the activated candidate serves its own copy:
~/.deck-master-candidates/.deck-master/current/venv/bin/python \
  -I -m deck_master doctor --step view
python -m deck_master.cli install rollback --prefix ~/.deck-master-candidates
```

Rollback restores the previous activated release; activation failures leave
`current` untouched (covered by `tests/rebuild/test_install.py`).

## Old Commands

Pre-rebuild commands are retired or mapped — the full table (do not reuse the
old names in new material):

```bash
deck-master legacy-map
```

Old run directories are recognised and refused (`legacy_run_format`); convert
a full draft with `deck-master import legacy --input <old-run> --out <new>`
(read-only). See `docs/migration-to-rebuilt-core.md`.
