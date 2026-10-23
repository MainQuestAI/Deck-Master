# PR187 queued close and subsequent keyboard navigation

The parent's single ad4 fill timeout has no focus trace and remains uncertain.
It occurred while removal was held, before any server response; it cannot be
attributed to the already repaired late removal callback.

Finite probes against the exact ad4 wheel at 1280x800 found:
- original sequence, explicitly synchronized sequence and Tab-only navigation
  could open the new form;
- closing and programmatically focusing Create in one task deterministically
  lost that focus to the queued close handler, causing Enter to reopen removal;
- a separate real keyboard probe aligned to a browser frame confirmed a product
  defect without programmatic focus after Escape: native restoration at 686ms,
  Shift+Tab focused Open project at 688ms, queued close at 707ms moved focus back
  to Remove. The removal request was still held and never sent to the service.
  This establishes a reachable keyboard race, not the cause of the untraced
  historical timeout, and is not inferred from repeated green runs.

The shared modal's native close already restores a connected trigger. Its queued
handler now avoids a second focus operation. For a removed trigger it preserves
an existing external focused element; otherwise the original fallback remains.
Open-dialog guards, resource cleanup, queued-dialog removal, draft ownership,
keyboard assertions, CSP and time limits are unchanged. No new state machine.

Regression includes five deterministic browser cases for connected/removed
triggers and subsequent focus choices, plus Escape/Shift+Tab. The helper tests
load the real same-origin dom.js in an isolated static surface: an initial test
placed probes inside a polling project main and its redraw removed test nodes.
That fixture failure is retained. Full-launcher traces are separate evidence.
Existing removal/cancellation/late-response, navigation and dialog regressions
and exact-wheel identity checks are recorded against the final commit outside
this historical implementation note. No CI read was attempted, no real model or
customer batch ran, and the 52-issue matrix is not reclassified by this fix.
