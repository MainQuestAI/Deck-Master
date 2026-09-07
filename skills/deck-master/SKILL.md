---
name: deck-master
description: Route Deck Master tasks for new decks, selected-page edits, read-only diagnostics, and approved delivery.
---

# Deck Master

## Use When
Operate a Deck Master run. Choose the task before loading production instructions.

| Task | Route | Read when needed |
| --- | --- | --- |
| New deck from material | deck-brief, then deck-planner | [New deck](playbooks/codex-run-solution-deck.md) |
| Change selected pages with confirmed direction | deck-producer or the existing build profile | [Local edits](playbooks/local-edits.md) |
| Explain a blocker or inspect readiness | deck-doctor | The reported error in [recovery](../../docs/agent-recovery-playbook.md) |
| Check or perform client delivery | deck-review | Current final-readiness and approval |
| Install or upgrade the software | deck-setup or deck-upgrade | [Installation](references/installation.md) |

## Do Not Use
Standalone document edits and unrelated code work do not require a Deck Master run.

## First Checks
Use the installed launcher `~/.deck-master/bin/deck-master`, or the source checkout CLI `python3 scripts/deck_master.py`. Run one relevant status command when current state is unknown; reuse its result until inputs change.

## Forcing Questions
Reuse the user's brief, selected style, page scope, and prior authorization. Ask only for an unresolved content, design, or external delivery decision that affects this task. Record applicable answers through the runtime instead of interviewing again.

## Runtime Ownership
Deck Master owns run_state, artifact bindings, quality findings, and approvals. Import generated or edited results through its commands. Keep factual sources and user decisions traceable.

## Allowed Commands
```bash
deck-master route-skill --input-type new_deck
deck-master route-skill --input-type local_edit --run-dir <run_dir>
deck-master route-skill --input-type diagnosis --run-dir <run_dir>
deck-master next-step --run-dir <run_dir>
deck-master final-readiness --run-dir <run_dir> --no-write
```

## Exit Artifacts
The requested change and its run_state, next_step, or review_workspace evidence. Finish after relevant rendering and checks pass; do not wait for another "continue".

## Next Skill
Follow the task route above. For an active build, keep its selected standard or high-density profile.

## Stop Conditions
A required input or tool is unavailable, a real unresolved decision needs the user, or the user stops. Agent-owned work may continue with available tools and existing authorization.

## Safety Rules
Preserve unaffected pages and approved design. Keep private/internal material out of customer-visible output. Do not fabricate evidence, bypass current artifact gates, directly edit events.jsonl, or export without applicable approval. Validation follows the changed inputs; repeat it when a new change or failure requires it.

Detailed handback schemas and command examples are in [agent instructions](references/agent-instructions.md). Load only the section needed by the current handoff.
