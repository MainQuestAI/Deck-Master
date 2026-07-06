# Contributing

Deck Master is currently a public Technical Preview. Contributions are welcome when they keep the local-first workflow reliable, verifiable, and clear for outside users.

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Before Opening A Pull Request

Run the focused checks for your change:

```bash
python -m unittest discover -s tests
python -m pytest tests/test_skill_manifest.py tests/test_workflow_cli.py tests/test_skill_doc_contract.py tests/test_skill_os_release_contract.py -q
```

For open-source readiness changes, also run:

```bash
python scripts/deck_master.py preview-gate --run-dir /tmp/deck-master-demo/oss-demo --expect-unconfigured-backend-ok
```

## DCO

This project uses Developer Certificate of Origin sign-off. Add a sign-off to each commit:

```bash
git commit -s -m "type: concise summary"
```

The sign-off means you have the right to submit the contribution under the project license.

## Pull Request Expectations

Every PR should include:

1. What changed.
2. Why it matters to the user.
3. Verification commands and results.
4. Known limitations or follow-up work.

Do not include private customer data, local absolute paths, credentials, logs, build outputs, or internal agent scratch files.

