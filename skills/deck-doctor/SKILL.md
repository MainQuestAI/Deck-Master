---
name: deck-doctor
description: Deck Master diagnostics entry for setup, suite readiness, run state, workspace validity, and blocked production actions.
triggers:
  - diagnose deck master
  - deck master doctor
  - why is deck blocked
  - check deck master health
---

# Deck Doctor

Use this skill when the user asks why Deck Master is blocked or degraded.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master doctor --workspace <workspace>
~/.deck-master/bin/deck-master doctor --run-dir <run_dir>
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master next-step --run-dir <run_dir>
```

## Output Rule

Explain the blocker in business terms first, then provide the repair command.


<!-- skill-os-contract:v1 -->

## Use When
Diagnostics for setup, suite readiness, workspace validity, and run blockers.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- n/a (operations/orchestrator lane)

## Forcing Questions
- n/a (no production forcing questions)

## Runtime Ownership
Skill OS operations/orchestrator; not a production stage. Reads workflow state and routes to the responsible production skill.

## Allowed Commands
```bash
deck-master doctor --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
doctor_report, setup_status, run_state

## Next Skill
(see workflow runtime)

## Stop Conditions
- user-initiated stop

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
