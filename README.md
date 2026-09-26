# Deck Master

Deck Master is a local-first, agent-operable solution-deck workbench: from a
brief and real source material it drives content composition, blueprint
generation, editable SVG/PPT production, review and repair — all through one
CLI and a loopback review workbench.

**Status:** rebuilt core (spec pack v1.1), Python package `1.0.0.dev2`.
**License:** Apache-2.0.

Flow Quality v1.1 adds complete task context, directory sources and input
revision updates that preserve unaffected pages. The development input and
acceptance checklist are in [the specification pack](docs/specs/deck-master-flow-quality-v1.1/README.md).
Engineering checks and the user-run Codex scenario are reported separately.

The rebuilt core does not require a PPT Master backend binding, a slide
library installation, or any first-run workspace setup: a plain material
directory is enough to start. Legacy v0.9.x material and runs are handled by
the migration notes in [docs/migration-to-rebuilt-core.md](docs/migration-to-rebuilt-core.md);
the old command surface maps onto the new CLI per
[spec 09.6](docs/specs/deck-master-rebuild-v1/specs/09-cli-and-host-protocol.md)
(`deck-master legacy-map` lists every mapping).

## Who It Is For

Deck Master is built for solution architects and proposal builders who need a repeatable way to decide which pages should be generated, which pages should be reused, and which pages are ready for review or delivery.

## Install

Python 3.11 and 3.12 are supported (`requires-python >=3.11,<3.14`); use
either as the default. Python 3.14 is not a supported test environment because
the PPTX dependency chain may not have compatible wheels yet.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If local Python cannot bootstrap pip in a venv, use the equivalent uv path:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

The only command surface is the rebuilt CLI: `deck-master ...` after install,
or `python -m deck_master ...` from a source checkout. Release activation also
registers the single Codex Skill; see [installation](skills/deck-master/references/installation.md).

## Quick Start

```bash
# 1. Create a project from a brief and real source material (no library,
#    workspace, or backend binding required).
deck-master create --brief "Quarterly operations review"   --source path/to/material.txt --out ./my-deck

# 2. Hand the pending Host task to your agent, then submit the result envelope.
deck-master continue --project ./my-deck
deck-master task accept --project ./my-deck --task-id <id>   --operation-id <op> --produced-against <hash> --result result.json

# 3. Open the loopback review workbench (four real views: content, blueprint,
#    SVG, PPT). It reuses one service per project.
deck-master view --open --project ./my-deck

# 4. Edit copy, review, and export — review purpose allows unfinished decks
#    with an honest unresolved list; delivery requires passing checks.
deck-master export --project ./my-deck --out ./out --purpose review

# 5. Persist changed requirements or materials before continuing the same deck.
deck-master inputs show --project ./my-deck
deck-master inputs update --project ./my-deck --patch update.json \
  --base-revision <revision_id> --operation-id <unique_id>
```

## Review Workbench

The review workbench is the local browser interface for the rebuilt core:
page list, editable content, blueprint/SVG/PPT comparison slots, findings and
feedback, history and restore. `deck-master view --open --project <dir>`
starts (or reuses) one loopback service per project.

![Review Desk](docs/assets/review-desk.png)

Workbench writes require a per-server session token and same-origin origin
check; reads are open on loopback. The server binds to `127.0.0.1` only.

## Capability Boundaries

The rebuilt core guarantees:

1. Real editable shapes and text in the produced PPTX (`editability=editable_shapes_and_text`); tables and charts are shape/text compositions, not Office-native data objects.
2. Honest status at every step: pending Host tasks show `awaiting_host` (never fake running); export `review` purpose ships unfinished decks with the real unresolved list; `delivery` requires passing current checks.
3. Renderer and font gaps surface as `needs_tool` with the actual reason.
4. The review workbench serves the four real views (content / blueprint / SVG / PPT) from project-relative objects only.

Professional human review and desktop-editing evidence stay `not_evaluated` until actually performed.

## Diagnostics

```bash
deck-master doctor --step compose   # content inputs
deck-master doctor --step render    # renderer toolchain (soffice/pdftoppm/rsvg-convert)
deck-master doctor --step export    # delivery-time checks
```

Renderer or font gaps are reported per step as `needs_tool` with the real
reason; nothing silently falls back to fixtures.

## Project Docs

- [Agent Entry](AGENTS.md)
- [Agent Task Index](docs/agent-task-index.md)
- [Agent Recovery Playbook](docs/agent-recovery-playbook.md)
- [Migration to the Rebuilt Core](docs/migration-to-rebuilt-core.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
