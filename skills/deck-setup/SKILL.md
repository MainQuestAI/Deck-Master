---
name: deck-setup
description: Deck Master setup entry for first-run installation, suite install, workspace binding, and readiness repair. Use when Deck Master is missing setup, suite links, active workspace, or local release activation.
triggers:
  - setup deck master
  - install deck master suite
  - repair deck master
  - first run deck master
---

# Deck Setup

Use this skill when the user needs Deck Master installed, repaired, or connected
to an active workspace.

## First Checks

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master suite-status --target codex --output json
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master setup --workspace <workspace> --repair-workspace --target codex --install-suite
~/.deck-master/bin/deck-master suite-install --target codex
~/.deck-master/bin/deck-master suite-repair --target codex
```

## Output Rule

Finish only when setup status and suite status are ready, or return the exact
blocking item and repair command.


<!-- skill-os-contract:v1 -->

## Use When
First-run setup, suite install, workspace binding, and readiness repair.

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
deck-master setup --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
setup_status, suite_status

## Next Skill
(see workflow runtime)

## Stop Conditions
- user-initiated stop

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
