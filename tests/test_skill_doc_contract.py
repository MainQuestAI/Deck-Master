"""Tests for Skill Doc Contract conformance (C2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import load_registry  # noqa: E402
from skills.validator import (  # noqa: E402
    REQUIRED_SECTIONS,
    validate_all,
    validate_skill_doc,
)

REGISTRY = load_registry()
KNOWN_COMMANDS = {
    "run-state", "next-step", "route-skill", "workflow", "workflow-autopilot",
    "build-brief", "build-claim-map", "autoplan", "decide-sourcing",
    "build-preview", "export", "final-readiness", "quality-gate", "init-project",
    "init-workspace", "import-context-pack", "start", "start-conversation",
    "plan", "doctor", "setup", "setup-status", "suite-status",
    "create-generation-tasks", "refresh-preview-from-generation",
    "generation-session", "build", "orchestration-check",
}


GOOD_DOC = """---
name: deck-brief
description: Briefing entry.
triggers:
  - create deck brief
---

# Deck Brief

## Use When
When the user provides source material.

## Do Not Use
Do not use for final export.

## First Checks
- context manifest present

## Forcing Questions
- decision object
- success criteria

## Runtime Ownership
Owned by the Skill OS workflow runtime; stage deck-brief.

## Allowed Commands
```bash
deck-master build-brief --run-dir <run_dir>
deck-master build-claim-map --run-dir <run_dir>
```

## Exit Artifacts
deck_brief, claim_map_seed

## Next Skill
deck-planner

## Stop Conditions
- blocking question
- fatal evidence gap

## Safety Rules
Keep internal production notes out of customer-visible content.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_good_doc_passes(tmp_path):
    doc = tmp_path / "deck-brief" / "SKILL.md"
    _write(doc, GOOD_DOC)
    rep = validate_skill_doc("deck-brief", doc, REGISTRY, known_commands=KNOWN_COMMANDS)
    assert rep.ok, [v.detail for v in rep.violations]


def test_missing_section_fails(tmp_path):
    bad = GOOD_DOC.replace("## Stop Conditions\n- blocking question\n- fatal evidence gap\n", "")
    doc = tmp_path / "deck-brief" / "SKILL.md"
    _write(doc, bad)
    rep = validate_skill_doc("deck-brief", doc, REGISTRY, known_commands=KNOWN_COMMANDS)
    assert not rep.ok
    assert any(v.rule == "section" and "stop_conditions" in v.detail for v in rep.violations)


def test_missing_frontmatter_fails(tmp_path):
    doc = tmp_path / "deck-brief" / "SKILL.md"
    _write(doc, "# Deck Brief\n## Use When\nx\n")
    rep = validate_skill_doc("deck-brief", doc, REGISTRY, known_commands=KNOWN_COMMANDS)
    assert not rep.ok
    assert any(v.rule == "frontmatter" for v in rep.violations)


def test_unknown_command_fails(tmp_path):
    bad = GOOD_DOC.replace("deck-master build-brief", "deck-master totally-fake-command")
    doc = tmp_path / "deck-brief" / "SKILL.md"
    _write(doc, bad)
    rep = validate_skill_doc("deck-brief", doc, REGISTRY, known_commands=KNOWN_COMMANDS)
    assert not rep.ok
    assert any(v.rule == "command" for v in rep.violations)


def test_invalid_command_arguments_fail(tmp_path):
    bad = GOOD_DOC.replace(
        "deck-master build-brief --run-dir <run_dir>",
        "deck-master setup --run-dir <run_dir>",
    )
    doc = tmp_path / "deck-brief" / "SKILL.md"
    _write(doc, bad)
    rep = validate_skill_doc(
        "deck-brief",
        doc,
        REGISTRY,
        known_commands=_real_commands(),
        command_parser=_real_parser(),
    )
    assert not rep.ok
    assert any(v.rule == "command_args" for v in rep.violations)


def test_compat_wrapper_must_reference_public_stage(tmp_path):
    # ppt-library is a compat backend (public=False); its doc must reference public stage
    skill = REGISTRY.skill("ppt-library")  # private
    doc = tmp_path / "ppt-library" / "SKILL.md"
    _write(doc, "---\nname: ppt-library\ndescription: x\ntriggers:\n  - a\n---\n# ppt-library\nNo public stage marker.\n")
    rep = validate_skill_doc("ppt-library", doc, REGISTRY, known_commands=KNOWN_COMMANDS)
    assert not rep.ok
    assert any(v.rule == "compat" for v in rep.violations)


def test_all_required_sections_enforced():
    # sanity: the validator knows all 10 required sections
    assert set(REQUIRED_SECTIONS) == {
        "use_when", "do_not_use", "first_checks", "forcing_questions",
        "runtime_ownership", "allowed_commands", "exit_artifacts",
        "next_skill", "stop_conditions", "safety_rules",
    }


def test_real_public_skill_docs_conform():
    """Every real public SKILL.md must satisfy the Skill Doc Contract."""
    known = _real_commands()
    reports = validate_all(registry=REGISTRY, known_commands=known, command_parser=_real_parser())
    public_reports = [r for r in reports if REGISTRY.skill(r.skill).public]
    failures = [r for r in public_reports if not r.ok]
    assert not failures, "\n".join(
        f"{r.skill}: {[v.detail for v in r.violations]}" for r in failures
    )


def test_real_compat_docs_reference_public_stage():
    known = _real_commands()
    reports = validate_all(registry=REGISTRY, known_commands=known, command_parser=_real_parser())
    compat_reports = [r for r in reports if not REGISTRY.skill(r.skill).public]
    failures = [r for r in compat_reports if not r.ok]
    assert not failures, "\n".join(
        f"{r.skill}: {[v.detail for v in r.violations]}" for r in failures
    )


def _real_commands() -> set[str]:
    """Derive the real deck-master subcommand set from the CLI parser."""
    try:
        import deck_master  # noqa: F401

        parser = deck_master.build_parser()
        # top-level subcommands
        cmds: set[str] = set()
        for action in parser._actions:
            if isinstance(action, type(None)):  # placeholder
                continue
        # subparsers action holds the dest=command choices
        for action in parser._subparsers._group_actions if hasattr(parser, "_subparsers") else []:
            pass
        # robust: walk the subparsers mapping
        sub_action = None
        for a in parser._actions:
            if hasattr(a, "choices") and isinstance(a.choices, dict):
                sub_action = a
                break
        if sub_action is not None:
            for name, sub in sub_action.choices.items():
                cmds.add(name)
                # one level deeper (e.g., workflow handoff)
                for a in getattr(sub, "_actions", []):
                    if hasattr(a, "choices") and isinstance(a.choices, dict):
                        cmds.update(a.choices.keys())
        return cmds
    except Exception:
        return KNOWN_COMMANDS


def _real_parser():
    import deck_master

    return deck_master.build_parser()
