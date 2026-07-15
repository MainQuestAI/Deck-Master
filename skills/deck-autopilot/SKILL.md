---
name: deck-autopilot
description: Deck Master workflow autopilot for advancing a run across init, brief, planning, sourcing, production, build, quality, review, and delivery checkpoints.
triggers:
  - run deck autopilot
  - continue deck workflow
  - make ppt from materials
  - deck autopilot
---

# Deck Autopilot

Use this skill when the user wants Deck Master to keep advancing the workflow
until a real blocker appears.

<!-- skill-os-contract:v1 -->

## Use When
Continuous workflow advancement across setup, planning, sourcing, production, build, quality, review, and delivery checkpoints.

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
deck-master workflow autopilot --mode quick --run-dir <run_dir>
deck-master workflow autopilot --mode repair --run-dir <run_dir>
deck-master workflow autopilot --mode review-only --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
workflow_report, run_state, next_step

## Next Skill
(see workflow runtime)

## Stop Conditions
- user-initiated stop
- material_missing
- setup_blocked
- awaiting_agent_execution
- approval_required
- final_export_requires_approval

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
