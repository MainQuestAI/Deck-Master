# RC3-04 R1 installed Studio independent review

**REQUEST_CHANGES — F5.** Fixed HEAD `7a8578baa210a92b92ae98922ff3236edf4d5975`, tree `4b7c5a931998ced2de624ee0ec29ff4a9e023139`. Twelve bounded software checks pass. This is actual installed HTTP/Chromium evidence with explicitly synthetic instructions and manuscript, not actual content/model/human acceptance.

The installed interpreter is `/workspace/work/rc3/candidate-04-7a8578b/prefix/.deck-master/releases/7a8578baa210-8d52fd31f7d7/venv/bin/python`. Direct imports resolve to that release's `site-packages`, as recorded in [installed-origin.json](evidence/installed-origin.json). The actual launcher was started by this interpreter with `-I -B -m deck_master workbench --registry <this directory>/registry.json --no-open`; launcher PID 435937 was observed running that installed interpreter's `deck_master.view_server` with this exact private registry. Its public response contains version `1.0.0rc3` and the runtime build identity. A separate tool-only interpreter runs Playwright 1.63 / Chromium `151.0.7922.173`. Neither scripts nor server insert source paths or import test fixtures. All three local services were stopped through their explicitly selected public workbench stop commands.

Inputs are the two files in `external/`. All created projects, registries, reports and UI runtime state are private to this review directory. There are no model/image calls, broad grants, native/human review contexts, edits to product tests or product files. The fixed snapshot's 3,610 tracked-file hashes, HEAD/tree and clean status match before/after; the installed package's complete 380-entry inventory also matches, including bytes, modes and mtimes. These before inventories were captured after the initial new/read-only/import-negative steps and before the later CAS/recovery steps; this timing is explicit, not an invented pre-start inventory. Root's preceding strict installed-byte audit is separate admission evidence. The entire enclosing external-source directory matches before/after a repeated actual browser read, including both files and all entry metadata.

## F5 — no complete Studio route for an existing confirmed manuscript

1. Open the fresh isolated Studio launcher and choose **新建项目**. The form has purpose/audience/output/mode/path/page-limit fields, but no manuscript input.
2. Create the default empty project. It correctly has 0 pages, one `compose.v2` framing/proposal-only Task, no authorization and no call allowance.
3. Open **查看本次工作与范围 → 导入确认稿**, choose `external/confirmed.json`, inspect the two-page real-text comparison and enter the explicit synthetic instruction to adopt that manuscript, preserve its mainline and refrain from production.
4. **确认导入确认稿** returns HTTP 409 `scope_exceeded`: target `p01/p02`, current request has `page_ids=[]`. Exact original document, manuscript source and local instruction text survive. This safety refusal is correct.
5. **开始新的明确请求** offers only existing-page checkboxes; the empty project has no options, future-ID input or manuscript-bound scope input. The launcher also has no `--draft` equivalent. Consequently this reasonable task has no complete public Studio path. A public installed CLI `create --draft` succeeds on the same source and shows both pages in Studio.

Fix the complete route using explicit manuscript/source/request/scope facts. Do not reinterpret an empty page set as implicit authority over future pages. Re-review must prove actual successful Studio creation/import, correct source/mapping and atomic rollback on invalid/stale/narrow scope.

Actual HTTP payload and response: [browser-events.json](evidence/browser-events.json). The unsuccessful import's [before](evidence/state-01-default.json) and [after](evidence/state-02-import.json) state files have the same SHA256 `fc148385e9b1955aabc309dfbc7c5c6ad85c3e8886f732517a8f18827ad96451`.

## Captured steps and observed health

Every screenshot listed below was opened and visually inspected in this review. The initial loading screenshot `03-default-project.png` is retained but rejected; `03b` is its stable replacement. Duplicate `07b` is retained as raw evidence of the repeated source-integrity check and is not additional visual coverage.

1. **Launcher — healthy.** Clear local-project entry, readable controls and white/gray/black OpenDesign visual language. [Screenshot](evidence/01-launcher.png).
2. **New-project form — F5 missing manuscript route.** Purpose/audience/location/output choices are readable; ordinary vertical scrolling handles the tall form. [Screenshot](evidence/02-create-form.png).
3. **Default project — healthy bounded initialization.** Shared installed CLI/SDK/UI revision, no pages/grants/calls, one framing Task. [Screenshot](evidence/03b-default-project-stable.png).
4. **Current work/scope — healthy factual projection.** Displays 0 pages, no confirmed decision and no authorization. Internal IDs remain in details. [Screenshot](evidence/04-default-scope.png).
5. **Manuscript comparison — healthy preview, overall route blocked by F5.** Shows source text before any mutation. [Screenshot](evidence/05-confirmed-import-compare.png).
6. **Import refusal — healthy gate, incomplete task recovery route.** Explicit scope gap and retained instruction; document unchanged. [Screenshot](evidence/06-import-result.png).
7. **Strict external review — readable limited report.** Actual text is displayed, source integrity preserved, professional review remains missing. Existing HTTP 200 mapping is the independently reported code finding F4; this is not evidence that corrected HTTP 409 still displays the report. [Screenshot](evidence/07-strict-readonly-report.png).
8. **Empty-project request scope — F5 confirmed.** No selectable pages or source/future-ID control. [Screenshot](evidence/08-empty-project-new-request-scope.png).
9. **CLI-created confirmed manuscript in Studio — healthy alternate route.** Actual two source titles/content and imported mapping, no production grant or Task. [Screenshot](evidence/09-cli-manuscript-studio.png).
10. **Two-window CAS — healthy.** Window C's real pause commits first; stale window B receives `conflict`, retains its own original text, and cannot overwrite the accepted pause or either Page Ref. [Screenshot](evidence/10-two-window-cas-reject-keeps-input.png).
11. **Lost response — healthy recoverable pending state.** Only the transport response is deliberately dropped after an actual successful server pause. The original path, CAS revision, operation ID and payload remain frozen. [Screenshot](evidence/11-lost-response-pending.png).
12. **Reload/replay — healthy.** Recovery resubmits the exact operation/payload, returns `already_applied`, and preserves the complete committed document and revision. [Screenshot](evidence/12-recovered-same-operation.png).
13. **Narrow scope and keyboard — healthy bounded check.** At 390×844, document width stays 390; text wraps, modal has ordinary vertical scrolling. Enter opens the focused scope button; Escape closes and returns focus to that button. This is not full accessibility compliance. [Screenshot](evidence/13-narrow-current-control.png).
14. **Historical reading/current delivery control — healthy bounded projection.** Historical artifact `0833c069…` remains fixed while current control `a226ab43…` shows the real pause and engineering/authority gaps. No actual PPT exists in this synthetic project. [Screenshot](evidence/14-narrow-delivery-current-control.png).
15. **Formal delivery refusal — healthy.** The real public export action rejects under current pause, preserves readable contents and displays the responsible role/gap instead of reporting a generated file. [Screenshot](evidence/15-formal-delivery-refused.png).

The visual checks cover the actual 1440×900 and 390×844 states above. Text, geometry, visible focus and functional controls are inspected; no screen-reader, full keyboard traversal, contrast certification or all-original-viewport-matrix claim is made. No browser `pageerror` was captured. HTTP/session/UI writes were made only inside the private projects; external evaluate never changes their business document.

## Evidence limits and next review

[review.json](review.json) records the machine-checked assertions and all NOT_RUN boundaries. Actual completed-content normal-stop, grant/revoke, sequential two-export variants, an old actual PPT selected under current control, external project/fileset review, four-Skill Host paths and broad browser CI are outside this focused run. No original evidence is relabelled as execution of those paths.

R2 must re-review F5's legal Studio path and F4's actual HTTP 409 readable-report retention, plus affected source-integrity/draft/scope behavior, against the new fixed installed identity. Actual human Owner/audience trials and target PowerPoint desktop editing remain deferred by the user, with no professional PASS invented.

Private helper mistakes are preserved in the execution record: the first shell attempted a not-yet-created workdir and never started; the read-state helper initially passed a relative path to the absolute-path-only public reader and was corrected locally; the initial default-page screenshot captured loading and was rejected. `state-05-lost-pause.json` was captured after successful resume and before the subsequent lost-response pause; its historical filename is not treated as a paused state. None of these are product fixes or hidden successful retries.
