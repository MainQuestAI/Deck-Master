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


<!-- skill-os-contract:v1 -->

## Use When
Project workspace initialization with material, reference, process, delivery, and metadata directories.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- workspace root exists and is writable
- raw material roots are reachable
- workspace policy available

## Forcing Questions
- init.scan_scope: 本轮要扫描和纳入的材料范围是什么？
- init.privacy_boundary: 哪些内容属于客户隐私边界，不得进入产出？
- init.customer_visible_forbidden: 是否存在客户可见禁词或禁用主张清单？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-init`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master init-project --workspace <workspace> --name <project_name>
deck-master validate-workspace --workspace <workspace>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
deck_project, material_inventory, workspace_policy, run_bindings

## Next Skill
deck-brief

## Stop Conditions
- missing_material_roots
- workspace_not_writable
- unresolvable_privacy_boundary

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
