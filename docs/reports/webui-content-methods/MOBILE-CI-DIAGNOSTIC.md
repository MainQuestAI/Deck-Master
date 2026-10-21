# Mobile installed-CI diagnostic

The original push run [39468219371](https://github.com/MainQuestAI/Deck-Master/actions/runs/39468219371), head `86750e78c1b429c759ffc92b1077591debd77fd4`, remains failed: source browser 555 passed; offline checks 9 verified; installed recovery 243 passed / 1 failed. The mobile gallery click timed out during scrolling into view after visible/enabled/stable. Its original scroll position and geometry are unknown. The parallel successful PR run does not resolve that failure.

This change adds evidence only, with no product change. The existing installed recovery step enables `STUDIO_MOBILE_CLICK_DIAGNOSTICS` for the single synthetic mobile-gallery case. Suite order, click, default 30-second timeout and every business assertion remain unchanged. There are no retries or force clicks. Existing push/PR triggers may create separate normal runs; no manual rerun is requested.

The helper logs browser/Playwright/package identity, wheel SHA256, route, viewport, scroll positions and ancestor geometry. Trace snapshots/screenshots are enabled around the click. An additional screenshot is attempted only after failure. Evidence exceptions are reported by type and cannot replace the original click exception. No environment dump, credentials or external project data are collected. Files use the existing `/tmp/workbench-browser` artifact directory and existing Actions permissions. No new dependency or download source is introduced.

Local validation of this instrumentation:

- Unchanged business case, source, diagnostics disabled: 1 passed in 3.45s.
- Retained installed product, diagnostics enabled: 1 passed in 3.57s; JSON and trace produced.
- Injected evidence setup/geometry/screenshot errors preserved the exact original TimeoutError object.
- Ruff and diff checks passed.

Local Chromium is 151; CI previously downloaded 156. All 267 retained installed product files match the prior head, but its wheel archive is not the original CI archive. Local passes mean only timeout not reproduced, not root cause resolved. The original artifact download and matching-browser download remain denied; neither is retried or bypassed. The next normal Actions run supplies new diagnostic evidence; even a pass does not close the unexplained failure. No new full local suite or package build is claimed for this test-only instrumentation. Host, professional and human acceptance remain outside this diagnostic.
