# Normal installed native content review

This follow-up fixes the release-blocking gap on main `0d11a5da`: a native
independent review could be observed by the experiment controller, but a normal
installation had no execution entry that could commit its authenticated receipt.
It does not change the RC4 70-item iteration ledger or claim a 1.0.0 release.

## Result and boundary

`deck-master review native --project <dir> [--task-id <id>]` and the normal
Studio work-scope action now share one packaged runner. It starts the existing
ChatGPT-authenticated Codex client, creates a fresh ephemeral read-only thread,
claims the review Task with the actual returned native thread identity, sends
the complete fixed packet and frozen methods, and directly observes the matching
successful turn/final output. Model judgments supply statuses, observations,
findings and replacements; Runtime supplies only immutable metadata/bindings.

Only that owned execution temporarily binds a protected-transport provider.
The existing receiver verifies project, request, Task, packet, manuscript,
author provenance, scope, result and actual independent executor. Its standard
committed Review/Task/receipt facts survive a new ordinary CLI process. The
default registry stays empty outside the operation. No import/signing endpoint,
credential, external model provider, permanent issuer, policy downgrade or
production grant is added. Human/professional requirements remain separate.

The operation lock prevents duplicate native calls. Running executions require
inspection/cancellation before retry; failed executions require a new explicit
run. Changed inputs, methods, cancellation and current-control checks retain the
existing refusal rules. HTTP uses the existing token/Origin/Host boundary and
accepts only an optional Task ID.

## Verification

- Synthetic L1 regressions cover CLI/real HTTP entry, complete packet/method
  transmission, exact receipt persistence, a fresh ordinary CLI continuation,
  non-pass judgments, malformed output, failure/retry, cancellation, concurrent
  starts and an unavailable client. These are transport/receiver tests, not
  model-quality evidence.
- Synthetic protocol sequences verify fresh restricted native thread settings,
  exact thread/turn completion, tool/approval refusal, incomplete executions,
  API-login refusal and custom-provider refusal.
- Real Chromium tests at 1440×900 and 390×844 pass through the actual Studio
  button and HTTP action with the labeled L1 transport, then reload the current
  state. No browser model response is intercepted or treated as real review.
- An independent read-only agent found no reproducible P1/P2 defect. Its
  separate mock completion followed by a fresh CLI `continue` returned
  `awaiting_host` without `needs_reviewer`. It made no model/API call.

## Remaining actual-Host verification

The cloud environment's original `CODEX_HOME` is read-only, so a second native
app-server cannot initialize there. An isolated temporary validation home reused
the existing auth file without activating HOME or changing authorization. The
real client created a read-only, network-disabled native thread and advertised
`gpt-6-astra`; this is client-reported model identity, not proof of serving ID.

The real native review of a retained neutral six-page Host-authored manuscript
then failed. A separate minimal structured-output diagnostic returned native
`codexErrorInfo=unauthorized`, confirming an upstream native authentication gap.
The review Task is failed, no authenticated completion was adopted, and no
successful model judgment or delivery is claimed. The validation request was
review-only and did not change the earlier content-only run into production.
No credentials/permissions were changed and no external API provider was called.

Before release, a usable existing Codex Host must complete this installed entry,
accept the actual native findings/receipt, and continue its real full-deck task
through delivery. This is an unresolved actual-execution check, not an added
product policy or a reason to fabricate a pass. No tag, Release, merge,
deployment or real-HOME activation is performed by this fix.
