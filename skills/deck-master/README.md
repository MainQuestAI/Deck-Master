# Deck Master Skill

Agent-facing skill package for [Deck Master](../../README.md) — a professional
Solution Deck Run OS.

## Installation

```bash
python3 scripts/deck_master.py install-skill \
  --target codex \
  --agent-skill-dir ~/.codex/skills
```

Verify:

```bash
python3 scripts/deck_master.py validate-skill --target codex
```

Remove:

```bash
python3 scripts/deck_master.py uninstall-skill --target codex
```

Supported targets: `codex`, `claude-code`, `hermes`, `custom`.

## Directory Layout

```text
skills/deck-master/
├── SKILL.md          # Agent discovery entry point
├── AGENTS.md         # Agent execution instructions
├── README.md         # This file
├── playbooks/        # Codex/Claude Code execution playbooks
├── schemas/          # JSON schemas for all handoff artifacts
└── prompts/          # Prompt templates for Agent tasks
```

## Playbooks

| File | Purpose |
|---|---|
| `codex-run-solution-deck.md` | End-to-end Solution Deck production run |
| `codex-review-and-repair.md` | Quality review and repair loop |
| `ppt-library-handoff.md` | PPT Library candidate selection handoff |
| `ppt-deck-pro-max-handoff.md` | Page generation handoff to Deck Pro Max |
| `external-quality-review.md` | External semantic/visual review task |
| `workspace-learning.md` | Workspace learning pack build |

## Version

v0.9 — Agentic Integration & Review Maturity release.
