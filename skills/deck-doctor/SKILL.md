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
