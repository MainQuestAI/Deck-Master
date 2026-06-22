---
name: deck-upgrade
description: Deck Master upgrade and rollback entry for self-contained release trees, activation, verification, and previous-version restore.
triggers:
  - upgrade deck master
  - rollback deck master
  - build deck master release
  - verify deck master release
---

# Deck Upgrade

Use this skill for release-tree installation, upgrade, smoke verification, and
rollback.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master release-build
~/.deck-master/bin/deck-master release-smoke
~/.deck-master/bin/deck-master release-rollback
~/.deck-master/bin/deck-master rc-gate
```

## Output Rule

An upgrade is complete only after the release tree verifies, activates, and the
current suite status is ready.
