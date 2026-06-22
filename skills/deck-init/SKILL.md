---
name: deck-init
description: Deck Master project workspace initialization entry for creating customer material, reference material, AI process, delivery, quality, and .deck-master metadata directories.
triggers:
  - init deck project
  - initialize deck workspace
  - create deck workspace folders
  - deck init
---

# Deck Init

Use this skill when the user starts a new deck project from raw material,
research reports, meeting notes, or an empty workspace.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master init-project --workspace <workspace> --name <project_name>
~/.deck-master/bin/deck-master validate-workspace --workspace <workspace>
```

## Output Rule

Do not overwrite user files. A successful init creates project folders,
`.deck-master/deck_project.json`, `material_inventory.json`,
`workspace_policy.json`, and `run_bindings.json`.
