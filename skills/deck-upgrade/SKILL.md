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
~/.deck-master/bin/deck-master release-build --output <release_dir> --force
~/.deck-master/bin/deck-master release-smoke --release-root <release_dir>
~/.deck-master/bin/deck-master release-rollback
~/.deck-master/bin/deck-master rc-gate --output-dir <output_dir> --force
```

## Output Rule

An upgrade is complete only after the release tree verifies, activates, and the
current suite status is ready.


<!-- skill-os-contract:v1 -->

## Use When
Self-contained release tree upgrade, verification, activation, and rollback.

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
deck-master suite-status --target codex --output json
deck-master release-build --output <release_dir> --force
deck-master release-smoke --release-root <release_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
release_manifest, capability_lock, sha256sums

## Next Skill
(see workflow runtime)

## Stop Conditions
- user-initiated stop

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
