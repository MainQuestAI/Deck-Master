# Deck Master Quick Start

This guide runs v0.9.14-preview.1 / Technical Preview (agent-operable). It uses fixture mode, synthetic demo content, and the local Review Desk.

## 1. Install

Use Python 3.11 or 3.12 for this preview.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If local Python cannot bootstrap pip in a venv, use:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Check the CLI:

```bash
python3 scripts/deck_master.py --help
deck-master --help
```

## 2. Create The Fixture Demo

```bash
bash scripts/demo.sh
```

Equivalent explicit command:

```bash
python3 scripts/deck_master.py autoplan \
  --brief-file examples/briefs/retail_digital_transformation.txt \
  --industry retail \
  --library-mode fixture \
  --run-mode fixture \
  --dev-allow-unsetup \
  --runs-dir /tmp/deck-master-demo \
  --run-id oss-demo
```

Expected result:

1. A run directory at `/tmp/deck-master-demo/oss-demo`.
2. `preview_manifest.json` exists.
3. At least 10 preview pages are present.

## 3. Run The Preview Gate

```bash
python3 scripts/deck_master.py preview-gate \
  --run-dir /tmp/deck-master-demo/oss-demo \
  --expect-unconfigured-backend-ok
```

The preview gate checks fixture demo readiness and confirms that an unconfigured production backend does not get reported as ready.

## 4. Open Review Desk

```bash
python3 scripts/preview/server.py /tmp/deck-master-demo/oss-demo
```

Open the local URL printed by the server. Review Desk should show the page queue and the current run state. Local write operations use a per-server write token and same-origin guard.

The preview server binds to `127.0.0.1` by default. Non-loopback hosts require `--allow-remote-preview` and should only be used on trusted local networks because the write token is visible to browsers that can load the page.

## 5. Production Boundary

The Technical Preview first-run path is fixture/demo. Production backend commands require configured and verified companion capabilities. The production external backend is `ppt-master`; `ppt-deck-pro-max` is a suite Skill for page production. If `ppt-master` is missing, Deck Master should report `unbound` or `not_configured` and provide a fixture/demo path.

Use these commands to inspect readiness:

```bash
python3 scripts/deck_master.py setup-status --include-suite --output json
python3 scripts/deck_master.py suite-status --output json
python3 scripts/deck_master.py backend status
```

## 6. Formal RC Gate

Use this only for M2 release-candidate validation:

```bash
python3 scripts/deck_master.py rc-gate \
  --output-dir /tmp/deck-master-rc \
  --benchmark-dir benchmarks \
  --skip-browser-smoke \
  --force
```
