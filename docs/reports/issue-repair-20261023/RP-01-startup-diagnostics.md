# RP-01 / X4 — Native startup failure visibility

Base: `2e1c5ce4`. Local repair only; no push or PR update.

## Reproduction

A synthetic installed/logged-in client returned `prerequisites_ready`; its
app-server process launch then raised an OS error. `CodexReviewSession.__enter__`
failed before dispatch, leaving the Document unchanged and no Task history.
`review channels --project` had no way to expose that failure. The added regression
failed before repair (`KeyError: native_startup_failures`, 1 failed in 0.47s).
This reproduces the visibility defect, not the environment's SQLite root cause.

## Change and guarantees

The owned transport tracks fixed startup phases and categories. It captures an
observed child exit code before cleanup; null means not observed, rather than a
successful exit. OS/protocol setup failures receive a fixed safe diagnostic.
The operation records a timestamp/revision/attempt-ID plus those whitelisted
fields in an atomic `.deckmaster/native-review-startup-history.json` sidecar.
This local diagnostic never creates a Task, checkpoint, receipt, review or new
business revision. It is not authenticated evidence or execution permission.

Discovery returns separate `native_startup_failures` and
`native_startup_history.status`; existing `native_executions` retains actual Task
history. Current login prerequisites remain explicitly unverified as a session.
Historical failures survive later successful synthetic execution without turning
that execution or the live prerequisites observation into a failure. Unreadable
history is unavailable, not empty success. Write failure preserves the original
startup error and exposes `startup_history_saved=false`.

Both persistence and public error details use the same whitelist. No raw stderr,
login output, exception text or config is stored. Symlink diagnostics are not
followed or overwritten. The permanent `implemented=True` branch in channel
mapping was removed; exact stage/channel support is covered by a capability-table
test. No native support was added for original images, SVG or final delivery.

## Validation

Synthetic unit/protocol/integration checks, no real native model call:

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /workspace/Deck-Master/.venv/bin/python \
  -m pytest -q -p no:cacheprovider \
  tests/rebuild/test_native_review_startup.py \
  tests/rebuild/test_native_review_transport.py \
  tests/rebuild/test_review_channel_discovery.py \
  tests/rebuild/test_native_review_recovery.py \
  tests/rebuild/test_content_preproduction_review.py \
  tests/rebuild/test_native_review.py \
  -k 'not normal_runner_receipt_survives_native_process_and_replay_is_no_call'
```

72 passed, 1 deselected (9.77s). The deselected cross-process installed-core test
belongs to the parent's separate matching-build validation; this checkout does
not claim the root environment's installed runtime matches this source. No tests
were skipped or assertions weakened. New cases cover launch failure; login
missing/error/rejection; initialize/config/thread child exits; provider rejection;
no Task mutation; subsequent synthetic completion; corrupt/symlink history;
write failure; public and stored secret-marker exclusion; exact capability table.

Logs: `/tmp/rp01-startup-before.log`, `/tmp/rp01-startup-final.log`.
Actual native review, SQLite repair, paid model execution, customer acceptance,
and installed-package verification are NOT RUN in this task. No credential,
security policy, HOME or customer project was changed.
