# Method refresh: bounded root-cause investigation

Read-only follow-up on report candidate129ad2c729f07e3c2342d295cf5622a53c1dae4e, runtimeb66cec184e20bbfb34a133980e9ca92bbeb7e9bf. No runtime/test edits, new test execution, artificial delay, retry, timeout relaxation, renderer installation or Frozen A reconstruction. This supplement follows the existing archive snapshot; it does not replace or mutate that archive.

## What the original failure proves

At dbd7133b, `test_ui_method_scope_browser.py::test_speech_preparation_real_clipboard_reader_and_draft_restore[1280]` failed after reload at the original5000ms `to_have_value('speech')` assertion. Its call-phase duration was14.329544449s (the entire test call, not reload latency). Earlier assertions had observed saved state and a disabled save button. The failure snapshot contained both the static initial shell and the live status `正在读取工作面`; no method field was present. This proves neither draft loss nor a successful eventual mount.

The initial studio HTML has an empty route-status. Its observed message is set by project.js loadRoute through dom.js announce. On the ordinary initial reload path, reaching it requires app.js health validation and Project.start's first Promise.all (project control, summary and UI state) to have completed. Consequently this was not a failure to load/execute app.js, nor a stall solely in the first health request. This narrows the observed phase beyond the previous generic “bootstrap shell” description.

After this announcement, loadRoute still awaits fresh project control and summary, possibly a fixed-revision summary, then content-plan and inputs for this content route before render replaces the initial root. A stalled request/body read, browser scheduling pause, or a superseded navigation still fits the snapshot. No original request identifiers, response/body timings, route generation events or JS execution trace survive to distinguish them. The snapshot does not establish which of these occurred. Error handlers ordinarily replace the initial shell on a settled read failure; absence of that replacement at the assertion is consistent with pending work, not proof of an HTTP error.

WorkbenchServer uses local_runtime._LoopbackServer, a ThreadingHTTPServer. Its handler suppresses default access logging. Therefore single-threaded HTTP serving is not supported as an explanation, and original per-request service timing cannot be recovered from these logs. No causal conclusion follows from the separately observed PID1-owned browser zombies. The original pytest-62 project directory is no longer present; the failure text and event/JUnit records remain in the preserved archive.

## What the later diagnostic can and cannot show

The unchanged four-case module previously passed with532 requests and532 response events, no recorded requestfailed/pageerror. In its second browser context (consistent with parametrization order1280, but the recorder did not independently tag widths), reload health headers arrived at0.253s, first project/summary/UI-state headers by0.278s, second project/summary by0.305s, content-plan by0.309s, and inputs by0.315s. Subsequent method preview headers arrived by0.389s. The derived timeline and input hashes are in method-reload-investigation.json.

**The recorder captured response events (headers), not requestfinished/body completion.** Previously reported fastest/slowest response intervals must not be interpreted as complete body latency, server execution time, DOM mount timing or a measurement of the original failure. Repeated URLs also lacked explicit request IDs. This passing trace shows the expected route sequence can complete; it does not diagnose the earlier5s stall. The subsequent77-case affected-module and708-case full passes remain valid evidence without resolving its cause.

## Missing evidence and next capture

No further blind rerun is justified by the available evidence. Preserve this risk and stop this investigation subitem until a naturally recurring failure or a specific discriminating hypothesis is available. For the next bounded reproduction, use the unchanged complete method-scope module at the same wheel/runtime, real Chromium and1280x900 case; retain1440/390 controls. Keep the original5000ms assertion and no automatic retries. Do not impose artificial service delays or change production behavior to manufacture the old symptom.

Before navigation, attach observation-only capture with per-test, per-page, per-request IDs and monotonic timestamps: navigation/reload, request/requestfinished/requestfailed/response, console/pageerror, page crash/close and browser disconnect. Retain a Playwright trace with snapshots and network information. Collect resource/navigation timing and optional long-task entries without wrapping fetch or changing its results. Record the exact reload URL/hash and viewport; compare the previous and new document identities so old events cannot be attributed to the new page.

Correlate existing test server handler entry/exit and response-write completion timestamps by request path/ID in the temporary diagnostic harness, preserving handler behavior and timeouts. On failure, retain the original assertion first, then collect DOM/ARIA, screenshot, pending request inventory, Python server thread stacks and browser/process status before teardown; post-failure observation does not turn a failed assertion into a pass. Copy the synthetic project and personal draft/UI-state files before pytest retention cleanup. Do not collect unrelated user data or install persistent monitoring.

Interpret the captured split explicitly: late handler entry suggests connection/thread scheduling; late handler exit suggests server work/lock contention; early headers but late requestfinished suggests body transfer; completed requests with a lingering shell suggests browser execution/navigation-generation behavior. Each remains a hypothesis until correlated at the actual failure. A deterministic product defect, if found, requires a targeted repair plus the full affected modules; no defect is currently established and no code fix is claimed.

## Status

Root cause remains **UNRESOLVED / NOT REPRODUCED**. No new permission is needed for this completed read-only analysis, and no further action is pending in this subitem. Missing rsvg-convert authorization remains separate and untouched. Existing full-suite evidence and wheel identity remain applicable because this follow-up changes reports only.
