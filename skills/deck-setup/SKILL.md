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
