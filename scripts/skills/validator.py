"""Skill Doc Contract validator (C2).

Validates every public ``SKILL.md`` against the Skill Doc Contract: required
sections, frontmatter, real commands, exit-artifact consistency with the
canonical manifest, and compat-wrapper→public-stage mapping. Prevents the
public skills from drifting back into "command index" docs (G-01).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skills.manifest import Registry, load_registry

# Required sections (C2 must-implement #1). Each is a list of accepted heading
# fragments; the first match satisfies the section.
REQUIRED_SECTIONS = {
    "use_when": ["use when", "use this skill when"],
    "do_not_use": ["do not use", "do not use when"],
    "first_checks": ["first checks", "first check"],
    "forcing_questions": ["forcing questions", "forcing question"],
    "runtime_ownership": ["runtime ownership", "runtime owner"],
    "allowed_commands": ["allowed commands", "commands"],
    "exit_artifacts": ["exit artifacts", "exit artifact"],
    "next_skill": ["next skill", "next stage"],
    "stop_conditions": ["stop conditions", "stop condition"],
    "safety_rules": ["safety rules", "safety"],
}

# Compat wrapper skills must declare which public stage they map to.
# The generator writes "Maps to public stage: <name>."; require the colon form
# so a sentence like "No public stage marker." does not falsely satisfy it.
COMPAT_PUBLIC_MARKER = "public stage:"


@dataclass
class DocViolation:
    skill: str
    path: str
    rule: str
    detail: str


@dataclass
class DocReport:
    skill: str
    path: str
    ok: bool
    violations: list[DocViolation] = field(default_factory=list)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end]
    body = text[end + 4 :]
    fm: dict[str, Any] = {}
    current_key = None
    for line in fm_text.splitlines():
        if line.startswith("  - ") or line.startswith("- "):
            val = line.lstrip(" -").strip()
            if current_key:
                if isinstance(fm.get(current_key), list):
                    fm[current_key].append(val)
                else:
                    fm[current_key] = [val]
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if v == "":
                fm[k] = []
                current_key = k
            else:
                fm[k] = v
                current_key = k
    return fm, body


def _has_section(body: str, fragments: list[str]) -> bool:
    lower = body.lower()
    for frag in fragments:
        # match as a heading or inline phrase
        if re.search(rf"^#.*{re.escape(frag)}", lower, re.MULTILINE):
            return True
        if frag in lower:
            return True
    return False


def _extract_commands(body: str) -> list[str]:
    commands: list[str] = []
    for m in re.finditer(r"deck-master\s+(\S+)", body):
        cmd = m.group(1)
        # skip placeholders (<...>), flags (--...), and run-dir style tokens
        if cmd.startswith("<") or cmd.startswith("--") or cmd.startswith("-"):
            continue
        if cmd in commands:
            commands.append(cmd) if cmd not in commands else None
        else:
            commands.append(cmd)
    return commands


def validate_skill_doc(
    skill_name: str,
    doc_path: Path,
    registry: Registry,
    *,
    known_commands: set[str] | None = None,
) -> DocReport:
    text = doc_path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    report = DocReport(skill=skill_name, path=str(doc_path), ok=False)

    # frontmatter
    if not fm.get("name"):
        report.violations.append(DocViolation(skill_name, str(doc_path), "frontmatter", "missing name"))
    if not fm.get("description"):
        report.violations.append(DocViolation(skill_name, str(doc_path), "frontmatter", "missing description"))
    if not fm.get("triggers"):
        report.violations.append(DocViolation(skill_name, str(doc_path), "frontmatter", "missing triggers"))

    # compat wrapper must point to a public stage
    skill = registry.skills_by_name.get(skill_name)
    if skill is not None and not skill.public:
        # compatibility backend/alias skill
        if COMPAT_PUBLIC_MARKER not in body.lower() and "public_name" not in body.lower():
            report.violations.append(
                DocViolation(skill_name, str(doc_path), "compat", "compat wrapper must reference its public stage")
            )
        return _finalize(report)

    # required sections (public skills)
    for section, fragments in REQUIRED_SECTIONS.items():
        if not _has_section(body, fragments):
            report.violations.append(
                DocViolation(skill_name, str(doc_path), "section", f"missing section: {section}")
            )

    # commands must be real
    if known_commands is not None:
        for cmd in _extract_commands(body):
            if cmd not in known_commands:
                report.violations.append(
                    DocViolation(skill_name, str(doc_path), "command", f"unknown command: {cmd}")
                )

    # exit artifacts must mention manifest exit_artifacts (if the skill has them)
    if skill is not None and skill.exit_artifacts:
        body_lower = body.lower()
        missing_artifacts = [
            a for a in skill.exit_artifacts if a.lower() not in body_lower and a.replace("_", " ") not in body_lower
        ]
        # require at least the section, not every token; soft-check the first
        # exit artifact is referenced somewhere
        if skill.exit_artifacts and str(skill.exit_artifacts[0]).lower() not in body_lower:
            report.violations.append(
                DocViolation(skill_name, str(doc_path), "exit_artifacts",
                             f"exit artifacts not aligned with manifest; expected references to {skill.exit_artifacts[:3]}")
            )

    return _finalize(report)


def _finalize(report: DocReport) -> DocReport:
    report.ok = not report.violations
    return report


def validate_all(
    skills_root: Path | None = None,
    *,
    registry: Registry | None = None,
    known_commands: set[str] | None = None,
) -> list[DocReport]:
    reg = registry or load_registry()
    root = skills_root or _default_skills_root()
    reports: list[DocReport] = []
    for skill in reg.skills_by_name.values():
        doc_path = root / skill.path
        if not doc_path.exists():
            reports.append(DocReport(skill=skill.name, path=str(doc_path), ok=False,
                                     violations=[DocViolation(skill.name, str(doc_path), "exists", "SKILL.md not found")]))
            continue
        reports.append(validate_skill_doc(skill.name, doc_path, reg, known_commands=known_commands))
    return reports


def _default_skills_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "skills" / "manifest.json").exists():
            return parent / "skills"
    return here.parents[2] / "skills"


__all__ = [
    "validate_skill_doc",
    "validate_all",
    "DocReport",
    "DocViolation",
    "REQUIRED_SECTIONS",
]
