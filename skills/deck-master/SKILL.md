# Deck Master — Agent Skill

## Identity

- **Name:** Deck Master
- **Version:** 0.9
- **Repo:** `MainQuestAI/Deck-Master`
- **Entry:** `scripts/deck_master.py`

## What Deck Master Does

Deck Master is a **professional Solution Deck Run OS**. It manages the state,
artifacts, events, quality gates and review workflow for building client-facing
solution decks.

Deck Master does **not** perform LLM reasoning, document parsing, or PPT
generation itself. It defines the contracts, runtimes and review surfaces that
external Agents (Codex, Claude Code, Hermes) and companion tools (PPT Library,
PPT Deck Pro Max, PPT Master) plug into.

## When to Use This Skill

Use this skill when:

- Creating or resuming a Deck run from customer context.
- Planning narrative structure, sourcing decisions or page tasks.
- Running quality gates (draft, evidence, brand, confidentiality, render, delivery).
- Reviewing deck readiness, claim coverage and next actions.
- Importing Context Packs, Narrative Advice, External Quality Reviews or Generation Results.
- Exporting an approved page queue.
- Managing workspace learning and skill installation.

## CLI Entry Point

```bash
python3 scripts/deck_master.py <command> [options]
```

Run `python3 scripts/deck_master.py --help` to list all commands.

## Key Commands

| Command | Purpose |
|---|---|
| `start-conversation` | Create a guided conversation run from local context |
| `build-brief` | Compile deck brief from context and conversation |
| `build-claim-map` | Build claim map from brief |
| `autoplan` | Run full brief-to-preview pipeline |
| `search-library` | Run PPT Library candidate selection |
| `decide-sourcing` | Create sourcing plan from library results |
| `create-generation-tasks` | Create Deck Pro Max generation task packages |
| `build-preview` | Build preview manifest from sourcing decisions |
| `quality-gate <gate>` | Run a quality gate |
| `export` | Export approved page queue |
| `next-step` | Resolve the recommended next action for a run |
| `import-context-pack` | Import an Agent-generated context pack |
| `prepare-narrative-advice` | Generate a narrative advice task for an Agent |
| `import-narrative-advice` | Import Agent narrative advice result |
| `apply-narrative-advice` | Apply narrative advice to run artifacts |
| `prepare-quality-review` | Generate an external quality review task |
| `import-quality-review` | Import external quality review result |
| `prepare-generation-handoff` | Generate handoff package for build tools |
| `import-generation-result` | Import generation result from build tools |
| `build-learning-pack` | Aggregate workspace learning for next Agent run |
| `install-skill` | Install Deck Master skill into Agent skill directory |
| `validate-skill` | Validate skill symlink |
| `uninstall-skill` | Remove skill symlink |

## Playbooks

| Playbook | When |
|---|---|
| `playbooks/codex-run-solution-deck.md` | End-to-end Solution Deck run |
| `playbooks/codex-review-and-repair.md` | Quality repair loop |
| `playbooks/ppt-library-handoff.md` | PPT Library selection handoff |
| `playbooks/ppt-deck-pro-max-handoff.md` | Page generation handoff |
| `playbooks/external-quality-review.md` | External quality review task |
| `playbooks/workspace-learning.md` | Workspace learning pack |

## Schemas

All schemas are in `schemas/`. Every artifact carries a `schema_version` field.

## Constraints

- Deck Master never calls an LLM API directly.
- Deck Master never stores API keys.
- All external reasoning is done by the calling Agent.
- Bad JSON input never overwrites existing artifacts.
- All import/apply operations write typed events.
