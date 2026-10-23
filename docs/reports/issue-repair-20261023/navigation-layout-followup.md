# Navigation and initial-design layout follow-up

Base `3b809d3e`; real system Chromium + WorkbenchServer checks, completed
2026-10-22 19:39 UTC. No model call, release, customer project, or remote write.

## Reproduction and fixes

The five suspected CI failures reproduced exactly: **5 failed, 16 deselected in
38.83s**, `/tmp/nav-before.log`.

- Opinion editor at 1280×800, 1440×900 and 390×844: RP-22 intentionally collapsed
  the composer. The test now uses the visible writing disclosure before editing.
  All original editability, saved-opinion, artwork/editor geometry, trial-tool and
  overflow assertions remain unchanged.
- Selected internal style: actual layout regression. RP-21 added an expanded
  initial-design form above the existing reference workflow whenever even one
  page lacked an original. In the mixed 24-page fixture this pushed the action
  below 800px and the requirements field below 900px. Before screenshots:
  `/tmp/nav-original-1280.png`, `/tmp/nav-original-1440.png`.

The initial-design form is now a labeled native disclosure, initially collapsed
when the fixed summary contains existing originals, and initially open when no
page has an original. Source choice, saved-recipe browsing and this disclosure
share a wrapping toolbar. Expanded initial design occupies a full row. The user's
open state is not updated by polls/resizing; no permission, CAS, preview identity
or response-retirement rules changed. This is not a hidden/removed entry.

A visually observed literal `null` from an absent optional original-review row
was also removed by a boolean child guard; a browser assertion checks the absent
row does not produce a literal null text node. No underlying status changes.

## Evidence

```sh
PYTHONPATH=/tmp:src:tests/rebuild STUDIO_NAVIGATION_EVIDENCE=/tmp/nav-final-evidence \
 /workspace/Deck-Master/.venv/bin/python -m pytest -p rp09_chromium -q \
 tests/rebuild/test_navigation_usability_browser.py \
 tests/rebuild/test_design_entry_browser.py tests/rebuild/test_design_entry_poll_browser.py
# 27 passed in 133.28s; /tmp/nav-final.log
```

Final added expanded-width and open-state assertions were independently run:
`test_design_entry_browser.py test_design_entry_poll_browser.py`, **6 passed in
20.92s**, `/tmp/nav-initial-final.log`, artifacts `/tmp/nav-initial-final`.
They retain real one-page handoff, mixed-deck user expansion, no-original direct
entry, same-snapshot polling/late responses, changed-input/revision retirement,
1440/1280/390 no-overflow, full-row expanded width, and retained basis/open state.

The final null-text guard was then checked with `test_design_entry_browser.py`
using `--basetemp=/tmp/nav-initial-clean`: **2 passed in 6.12s**;
see `/tmp/nav-initial-clean.log`.

| Viewport | Check-action bottom | Requirement-field bottom | Required limit |
| --- | ---: | ---: | ---: |
| 1280×800 | 465.83px | 761.69px | <800px |
| 1440×900 | 465.83px | 761.69px | <900px |

Screenshots and exact bbox JSON:
`/tmp/nav-final-evidence/style-selected-{1280,1440}.{png,json}`. The 1280 screenshot
was visually inspected. Narrow expanded-basis screenshot was also inspected at
`/tmp/nav-initial-final/test_no_reference_initial_basi0/initial-basis-390.png`;
regenerated final screenshots without the null artifact are in the equivalent
`/tmp/nav-initial-clean/` path. These are synthetic UI/behavior evidence, not
actual model or professional image-quality acceptance. Full integrated CI remains
with the parent thread.
