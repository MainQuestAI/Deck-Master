# Native dispatch and exact output bytes

This is a technical dispatch supplement to [README.md](README.md). It describes
the existing recorders and public Runtime contracts; it changes no schema,
budget, provider, controller, registration or admission boundary. Dispatch its
applicable instructions before the actual execution. A later document cannot
retroactively change what an earlier Writer received.

Every `<placeholder>` below must come from the actual selected run, public
Runtime response or native tool observation. Templates contain no execution
results. Never copy another run's IDs, completion, reviewer verdict or business
content into a new observation.

## Choose the output protocol before dispatch

| Boundary | SDK workflow: `controller.py` | Native C: `native_only.py` |
| --- | --- | --- |
| Author output | Complete formal envelope for the actual Task and its own installed contract | Original native text; no Deck Master envelope or object schema |
| Result file | Writer's unchanged formal envelope file | Exact bytes of the entire actual native FINAL |
| FINAL | May contain completion metadata identifying the formal output file | Only the entire native output, with no completion metadata or added wrapper |
| Binding | Pins raw envelope bytes and the complete Root completion observation separately | Also requires `completion.raw_final_message.encode('utf-8') == raw_result_bytes` |
| Methods | `claim-read`; actually read the entire returned installed methods/work order | `read-methods`; actually read all five full pinned references and the allowed packet |
| Result consumption | Own SDK `accept`, or protected `review-accept` for the applicable review | Native recorder observations/snapshots; no DM Task, Store, SDK acceptance or central gate |

The two FINAL formats are not interchangeable. Both recorders freeze the
supplied result and Root observation before validating them. Both require the
actual executor's full FINAL, a real `collaboration.list_agents` completed
observation, exact method-read binding and fresh Root observation. A filename,
hash or Writer's assertion alone does not establish these facts.

For the SDK path, `controller.observe` does **not** require the FINAL message to
equal the envelope file. Root must retain both originals and accurately bind the
file hash; metadata in FINAL does not become an envelope field. For applicable
`input_revision` outputs, retain the Writer's original proposal sidecars and
their declared Refs as described in the README and
[layer supplement](input-revision-layer-rules.v1.json). Root must not complete,
restructure or repair an envelope after refusal.

For native C, the equality check includes every heading, code fence, prefix,
suffix, space, CR/LF and terminal newline. Put any headings or formatting that
belong to the manuscript in both the file and FINAL. Do not add an outer code
fence, “completed” sentence, file path, hash or method-read statement to FINAL.
Native questions, partial manuscripts and review text use the same exact-byte
rule; Root records their actual `native_output_kind` rather than calling every
response a complete manuscript.

## Native C metadata and FINAL sequence

1. Root prepares the allowed packet, invokes the actual fresh Writer with
   `fork_turns="none"`, records the returned identity through `begin-native`,
   and supplies the actual ordinal. Followups must be real recorded followups
   permitted by that workflow's role policy.
2. Writer runs `read-methods` for its actual canonical identity and ordinal,
   then reads the complete returned method bytes and allowed inputs. Returned
   bytes and actual reading/application remain distinct observations.
3. Writer saves the intended native output as a new UTF-8 file with an explicit
   terminal-newline choice. It sends metadata to Root using
   `collaboration.send_message` **before** FINAL: original file path, byte count,
   SHA-256, terminal LF count, actual method-read record and an honest statement
   of which full bytes it read. This message is separate from the manuscript.
4. Writer's FINAL contains only the exact native output in that file. Root
   captures the actual full FINAL and completed-agent observation without
   trimming, newline normalization, JSON pretty-printing or semantic editing.
5. Before `observe`, Root compares the actual FINAL's UTF-8 bytes with the
   supplied file, including the end. Use byte-preserving serialization; avoid
   `echo`, text-mode newline conversion and shell command substitution, which
   can alter trailing newlines. Hash the bytes actually supplied to `observe`.

If the transport and Writer file differ only in trailing LF bytes, preserve the
original file and actual FINAL first. At most record a separate lossless
terminal-LF correspondence: both paths/hashes, exact suffix difference and the
fact that the non-LF prefix is identical. A separate faithful byte copy of the
actual FINAL may be supplied before observation, with that provenance retained.
Do not overwrite the original, trim the observation, normalize other whitespace
or describe an edited manuscript as the original. Any other difference requires
preserving the mismatch and resolving it through a real permitted execution.

If `observe` already refused, its frozen originals and error stay in place.
Do not overwrite its files or rewrite `raw_final_message` to make the old
ordinal pass. Any additional Writer submission must come from a real
spawn/followup with its own recorded invocation and ordinal.

## Rejections, resubmissions and budget

The initial real invocation counts even when its output or observation is
refused. Each additional real Writer spawn/followup counts again under its
actual role. A “format-only retry” label does not remove either execution from
the budget. Retain first drafts, malformed envelopes, exact native FINALs,
errors, later submissions and any terminal-LF correspondence separately.

The shared registered limits remain five initial Writer executions, one
substantive feedback, one autonomous repair cycle and at most three necessary
repair Writer layers. Verification and production remain separate work. Record
over-budget executions honestly; do not consume them as equal-budget results,
reset counters through a new directory, or rename extra writing as verification.
A read-only byte comparison/copy is not an additional model execution and must
not be represented as one.

Freeze the first actually observed complete native manuscript at the applicable
original timepoint. Keep SDK acceptance and comparison/qualification timepoints
distinct. A formatting refusal is not a reason to select a later preferred
draft as the first original.

## Independent review after content completion

A content-only workflow can close its request when the complete result is
adopted; an actual `continue_project` can then report completion with that
request already closed. Read the real current request and returned pending work before
dispatching review. A completed content request does not authorize reopening its
phases or manually changing `closed`, `closed_reason`, request IDs or Tasks.

When the authorized workflow calls for an independent in-project review after
that completion, start an actual new `review_only` request through
`collaboration.start_request`. Bind it to the real review instruction, limit
`scope.layers` to `["review"]`, disable page membership/order changes, and use
the current `base_revision` with the public operation ID/CAS rules. This is a
management transition: preserve the original Narrative, ContentPlan, Page and
source Refs. Review-only permission authorizes review records/evidence; it does
not authorize manuscript repair or production. If the user requested strict
no-persistence review, use the contract's external read-only path instead of
creating an in-project request.

The following is an arguments-file template for the existing controller
`public-operation --operation collaboration.start_request`. Replace every
placeholder, including the entire page ID array, with actual authorized values;
it is not ready-to-submit JSON. An empty `page_ids` array never means all pages.
Use the Runtime's actual deck/page scope and the dispatched Task's exact
`scope_pages` rather than inferring coverage from an empty array.

```json
{
  "base_revision": "<fresh-current-revision-id>",
  "operation_id": "<actual-unique-review-request-operation-id>",
  "input": {
    "intent": "review_only",
    "content_intent": null,
    "scope": {
      "subject": "deck",
      "page_ids": ["<actual-authorized-page-id>"],
      "page_manifest_ref": null,
      "external_artifact_ref": null,
      "layers": ["review"],
      "allow_page_membership_change": false,
      "allow_page_order_change": false,
      "purpose": "review"
    },
    "instruction_evidence": {
      "kind": "host_attested_instruction",
      "actor_id": "<actual-instruction-transcriber-id>",
      "source_locator": "<actual-authorized-review-instruction-locator>",
      "source_ref": {
        "path": ".deckmaster/objects/<actual-sha-prefix>/<actual-source-sha256>.txt",
        "sha256": "<actual-source-sha256>"
      },
      "presentation_ref": null,
      "transport_receipt_ref": null
    }
  }
}
```

The source Ref must already contain the exact authorized instruction through an
allowed public evidence operation. Do not invent a message, Ref, actor or human
receipt. Host transcription remains `host_attested`; stricter authority policies
still need their actual protected channel. If an active request exists, follow
the public explicit replacement/background rules; do not silently supersede it.
A new review request does not reset the experiment's feedback or Writer budget.

If an earlier dispatch failed on a closed request, retain its original intent,
exception and actual Runtime observations. A failed dispatch can leave an
immutable packet object without a committed review Task. Inspect current
Document/Tasks and the actual operation query before reconciling; do not infer
successful dispatch from an object file. `reconcile` records observed
`committed`/`not_found`/`unknown` facts and does not retry. Unknown remains
unresolved. A later permitted dispatch is a separately recorded operation after
the real new request; do not replay a completed content phase.

Then follow `review-prepare` → real independent begin/claim/read/observe →
protected `review-accept` for installations that actually provide that bridge.
Use the actual required units, subjects, dependencies, author provenance and
reviewer's identity. Ordinary JSON `verified` flags do not provide an opaque
receipt. Preserve any original Runtime blocker when the selected installation
lacks that bridge. Record the actual gate result; neither a successful process
exit nor a reviewer's textual verdict substitutes for it.

Deliver only the actual single feedback. If it identifies no defect, do not
manufacture findings, a repair Task or a repair cycle. If real findings require
repair, use their IDs and necessary authorized layers, then obtain the separate
read-only verification required by the registered workflow. Review-only scope
itself does not permit that repair.

## Reusable dispatch templates

These are instructions, not observations. Replace IDs only after the actual
tool/Runtime returns them. Do not include answer banks, private oracles, other
arms, historical FINALs or business-answer examples in a Writer packet.

**Root → SDK Writer/reviewer**

```text
Protocol: SDK formal envelope, controller.py.
Allowed packet: <actual-stage-packet>; run: <actual-run>; stage: <actual-stage>.
Task: <actual-pending-task-id>; role: <actual-recorded-role>.
Wait for Root's actual launch-ready path and ordinal before claim-read.
Use <own-installed-absolute-python> -I -B; claim with your actual canonical ID.
Read the entire returned methods/work order and permitted source bytes.
Write one complete unchanged formal envelope to <new-output-file> under the
allowed stage. Follow the actual Task/schema and any dispatched sidecar rules.
FINAL may identify the envelope path/hash and actual method-read record;
Root retains the full FINAL separately. Do not fabricate Root completion,
review receipts, acceptance, missing fields or a passing gate. No delegation.
```

**Root → native C Writer/reviewer**

```text
Protocol: native_only.py, native-text-no-dm-schema.
Allowed packet: <actual-packet.json>; run: <actual-native-run>.
Wait for Root's actual begin-native ordinal: <actual-ordinal>.
Run read-methods with your actual canonical ID; read every full method/input.
Write original native output to <new-utf8-output-file>, choosing its terminal
LF bytes explicitly. Do not create a DM envelope, Task, receipt or SDK gate.
Before FINAL, send Root separate metadata using collaboration.send_message:
path, byte count, SHA-256, terminal LF count, actual method-read record and an
honest full-read report. Then FINAL ONLY the complete native output, exactly
matching the file's UTF-8 bytes. Add no metadata, prefix, suffix or outer fence.
No delegation or additional model/image execution.
```

**Writer → Root metadata, sent before native C FINAL**

```text
Actual executor: <actual-canonical-id>; ordinal: <actual-recorded-ordinal>.
Original file: <actual-new-file>; bytes: <measured-count>;
SHA-256: <measured-sha256>; terminal LF count: <measured-count>.
Method-read record: <actual-record-path-and-sha256>.
Full bytes actually read: <truthful-list-of-allowed-method/input-files>.
Unresolved reading/output limits, if any: <actual-limits>.
FINAL follows as native output only; this message is not part of the output.
```

**Root completion handling, either protocol**

```text
Preserve the actual FULL FINAL and actual completed roster observation.
Record the real executor, invocation ordinal, method record and output hashes.
For native C, verify full UTF-8 byte equality, including terminal LF bytes.
Freeze originals through the selected recorder before consumption.
Retain any refusal and count every actual invocation. Do not patch content,
invent completion, infer acceptance or remove an earlier failure.
```

## Scope of this document

This document makes no execution/admission/result claim. Neutral GENTRY/native C
engineering is not an E1 effect, a benchmark workflow credit, content-quality
evidence or human/professional acceptance. Frozen registrations and prior
observations remain unchanged. Any future admitted execution still requires its
own authorized packet, real native tool chain and actual Runtime evidence.

Code/contract references: [SDK observe and review flow](controller.py),
[native-only observe](native_only.py),
[collaboration contracts](../../docs/specs/deck-master-content-collaboration-v1.2/CONTRACTS.md),
[active collaboration schema](../../src/deck_master/resources/contracts/collaboration.v1.schema.json),
[recovery playbook](../../docs/agent-recovery-playbook.md).
