# RP-22 deep-quality browser compatibility follow-up

Base `a7fc409d`; completed 2026-10-22 18:52 UTC. Parent's two suspected CI
failures were reproduced locally using the real WorkbenchServer and system
Chromium, not inferred from the CI progress-dot positions.

Before changes:

```sh
PYTHONPATH=/tmp:src:tests/rebuild /workspace/Deck-Master/.venv/bin/python -m pytest \
  -p rp09_chromium -q \
  tests/rebuild/test_deep_quality_browser.py::test_old_revision_draft_never_locks_a_new_opinion \
  tests/rebuild/test_deep_quality_browser.py::test_private_note_stays_out_of_opinions_and_repeat_saves
# 2 failed in 40.84s; /tmp/deep-quality-before.log
```

The first failed filling an absent accessible textbox; the second failed checking
that textbox's empty value. RP-22 commit `5e472de8` intentionally moved the opinion
body/save controls under initially closed `details.opinion-composer` (the card
requires opinion forms to expand on demand). Neither initial failure reached
saving, authorization or draft restoration. Tests now explicitly click the visible
“撰写意见” disclosure before accessing its visible field.

The first targeted rerun passed the private-note test and revealed a second test
navigation issue: `page.goto(goto())` navigated twice, because fixture `goto()`
already navigates. The intermediate composer could be opened before the following
route remount. The test now navigates once and waits for the active work surface
before opening the disclosure. No production code or original business assertion
was changed. Draft isolation, old-text recovery, current-version new opinions,
empty-body refusal, duplicate suppression and distinct legal scopes remain tested.

Full-file validation:

```sh
PYTHONPATH=/tmp:src:tests/rebuild /workspace/Deck-Master/.venv/bin/python -m pytest \
  -p rp09_chromium -q tests/rebuild/test_deep_quality_browser.py
# 19 passed in 67.07s; /tmp/deep-quality-full.log
```

This includes existing cloned-window offline-draft cases at 1280×800, 1440×900
and 390×844. The two repaired opinion cases use their existing 1440×900 viewport.
No full visual acceptance or other CI suites are claimed. This uses the existing
system-browser test fixture/plugin, with no new browser flags, installation,
model call, credentials change, remote write or project permission change.
