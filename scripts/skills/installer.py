"""Deck Master skill installer.

Manages symlinks from external Agent skill directories to the
installed Deck Master skill package under ``~/.deck-master/current``.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_NAME = "deck-master"
SUITE_NAME = "deck-master"
SUITE_VERSION = "0.9.12"
COMPANION_MANIFEST_SCHEMA_VERSION = "deck_master_companion_manifest.v2"

SUPPORTED_TARGETS = {"codex", "claude-code", "hermes", "custom"}

DEFAULT_AGENT_SKILL_DIRS = {
    "codex": "~/.codex/skills",
    "claude-code": "~/.claude/skills",
    "hermes": "~/.hermes/skills",
}

INSTALL_LOG_DIR = Path.home() / ".deck-master"
INSTALL_LOG_NAME = "install_log.jsonl"
INSTALLED_SKILL_DIR = INSTALL_LOG_DIR / "current" / "skills" / SKILL_NAME
COMPANION_MANIFEST_NAME = "companion-manifest.json"

SUITE_SKILLS: list[dict[str, Any]] = [
    {
        "name": "deck-master",
        "required": True,
        "required_for": ["full_deck_workflow", "setup", "run_orchestration"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.run.v1", "deck_master.setup.v1"],
        "optional_capabilities": [],
        "schema_versions": {"setup_status": "deck_master_setup_status.v2"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "ppt-library",
        "required": True,
        "required_for": ["library_sourcing", "asset_feedback"],
        "install_source": "external_adopted_or_release_bundle",
        "cli": "ppt-lib",
        "required_capabilities": [
            "ppt_library.doctor.v1",
            "ppt_library.search.v1",
            "ppt_library.selection.v1",
        ],
        "optional_capabilities": ["ppt_library.feedback.v1"],
        "schema_versions": {
            "selection_output": "deck_master_ppt_library_selection.v1",
            "feedback_input": "deck_master_ppt_library_feedback.v1",
        },
        "adoption_policy": "adopt_valid_external_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "ppt-deck-pro-max",
        "required": True,
        "required_for": ["new_generation", "adapt_generation"],
        "install_source": "external_adopted_or_release_bundle",
        "cli": "ppt-deck-pro-max",
        "required_capabilities": [
            "ppt_deck_pro_max.generate.v1",
            "ppt_deck_pro_max.handback.v1",
        ],
        "optional_capabilities": [],
        "schema_versions": {
            "generation_result_input": "ppt_deck_pro_max_generation_result.v1",
            "generation_result_canonical": "deck_generation_result.v1",
        },
        "adoption_policy": "adopt_valid_external_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "ppt-quality-gate",
        "required": True,
        "required_for": ["standalone_audit", "quality_findings_import"],
        "install_source": "external_adopted_or_release_bundle",
        "cli": "ppt-quality-gate",
        "required_capabilities": [
            "ppt_quality_gate.audit.v1",
            "ppt_quality_gate.findings.v1",
        ],
        "optional_capabilities": [],
        "schema_versions": {
            "quality_findings_input": "deck_master_quality_findings.v1",
            "quality_report_canonical": "deck_quality_report.v1",
        },
        "adoption_policy": "adopt_valid_external_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "ppt-master",
        "required": False,
        "required_for": ["render_export_optional"],
        "install_source": "optional_external_adopted_or_release_bundle",
        "cli": "ppt-master",
        "required_capabilities": ["ppt_master.render.v1", "ppt_master.handback.v1"],
        "optional_capabilities": [],
        "schema_versions": {"render_result": "deck_master_render_result.v1"},
        "adoption_policy": "adopt_valid_external_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
]


class SkillInstallError(Exception):
    """Raised when a skill installation operation fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_skill_dir(skill_name: str = SKILL_NAME) -> Path:
    """Return the absolute path to a skill package in this repo."""
    return Path(__file__).resolve().parents[2] / "skills" / skill_name


def _installed_skill_dir(skill_name: str = SKILL_NAME) -> Path:
    if skill_name == SKILL_NAME:
        dynamic_installed = INSTALL_LOG_DIR / "current" / "skills" / SKILL_NAME
        if dynamic_installed.exists():
            return dynamic_installed
        return INSTALLED_SKILL_DIR
    return INSTALL_LOG_DIR / "current" / "skills" / skill_name


def _resolve_source_dir(source_skill_dir: str | None = None, *, skill_name: str = SKILL_NAME) -> Path:
    if source_skill_dir:
        return Path(source_skill_dir).expanduser()
    installed = _installed_skill_dir(skill_name)
    if installed.exists():
        return installed
    return _repo_skill_dir(skill_name)


def _resolve_target_dir(target: str, agent_skill_dir: str | None) -> Path:
    if agent_skill_dir:
        return Path(agent_skill_dir).expanduser().resolve()
    if target == "custom":
        raise SkillInstallError(
            "Target 'custom' requires --agent-skill-dir to be set explicitly."
        )
    default = DEFAULT_AGENT_SKILL_DIRS.get(target)
    if not default:
        raise SkillInstallError(
            f"Unknown target '{target}'. Supported targets: "
            + ", ".join(sorted(SUPPORTED_TARGETS))
        )
    return Path(default).expanduser().resolve()


def _link_path(target_dir: Path, skill_name: str = SKILL_NAME) -> Path:
    return target_dir / skill_name


def _append_install_log(action: str, **fields: Any) -> None:
    INSTALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": _utc_now(), "action": action, **fields}
    log_path = INSTALL_LOG_DIR / INSTALL_LOG_NAME
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _skill_package_error(source: Path, *, expected_name: str = SKILL_NAME) -> str | None:
    skill_md = source / "SKILL.md"
    if not source.exists():
        return (
            f"Skill source not found: {source}. "
            "Run setup first or pass --source-skill-dir explicitly."
        )
    if not source.is_dir():
        return f"Skill source is not a directory: {source}."
    if not skill_md.exists():
        return f"SKILL.md not found in {source}."

    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return f"SKILL.md at {skill_md} is missing YAML frontmatter."
    parts = text.split("---", 2)
    if len(parts) < 3:
        return f"SKILL.md at {skill_md} has incomplete YAML frontmatter."
    frontmatter = parts[1]
    if f"name: {expected_name}" not in frontmatter:
        return f"SKILL.md at {skill_md} is missing 'name: {expected_name}'."
    if "description:" not in frontmatter:
        return f"SKILL.md at {skill_md} is missing 'description'."
    return None


def _install_named_skill(
    skill_name: str,
    target: str,
    agent_skill_dir: str | None = None,
    *,
    force: bool = False,
    source_skill_dir: str | None = None,
) -> dict[str, Any]:
    if target not in SUPPORTED_TARGETS:
        raise SkillInstallError(
            f"Unsupported target '{target}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_TARGETS))}"
        )

    source = _resolve_source_dir(source_skill_dir, skill_name=skill_name)
    if not source.exists():
        raise SkillInstallError(f"Skill source not found: {source}.")
    canonical_source = source.resolve()
    package_error = _skill_package_error(source, expected_name=skill_name)
    if package_error:
        raise SkillInstallError(package_error)

    target_dir = _resolve_target_dir(target, agent_skill_dir)
    link = _link_path(target_dir, skill_name)

    if link.is_symlink():
        existing_target = link.resolve()
        if existing_target == canonical_source:
            _append_install_log(
                "install_skill",
                target=target,
                skill=skill_name,
                status="already_installed",
                link=str(link),
                source=str(source),
            )
            return {
                "status": "already_installed",
                "skill": skill_name,
                "link": str(link),
                "source": str(source),
                "target_dir": str(target_dir),
            }
        if not force:
            raise SkillInstallError(
                f"Symlink already exists at {link} pointing to {existing_target}. "
                "Use --force to replace it."
            )
        link.unlink()

    elif link.exists():
        if not force:
            raise SkillInstallError(
                f"A real file or directory already exists at {link}. "
                "Deck Master will not overwrite it. "
                "Remove it manually or use --force to replace a symlink."
            )
        raise SkillInstallError(
            f"A real directory exists at {link}. "
            "--force only replaces symlinks, not real directories. "
            "Remove it manually first."
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    link.symlink_to(source)

    _append_install_log(
        "install_skill",
        target=target,
        skill=skill_name,
        status="installed",
        link=str(link),
        source=str(source),
    )

    return {
        "status": "installed",
        "skill": skill_name,
        "link": str(link),
        "source": str(source),
        "target_dir": str(target_dir),
    }


def inspect_skill_link(
    target: str,
    agent_skill_dir: str | None = None,
    source_skill_dir: str | None = None,
    *,
    skill_name: str = SKILL_NAME,
    required: bool = True,
) -> dict[str, Any]:
    """Pure-read skill link inspection. Does not write install logs."""
    if target not in SUPPORTED_TARGETS:
        return {
            "valid": False,
            "skill": skill_name,
            "status": "capability_missing",
            "error": (
                f"Unsupported target '{target}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_TARGETS))}"
            ),
        }

    target_dir = _resolve_target_dir(target, agent_skill_dir)
    link = _link_path(target_dir, skill_name)
    source = _resolve_source_dir(source_skill_dir, skill_name=skill_name)
    canonical_source = source.resolve() if source.exists() else source
    optional_status = "missing" if required else "optional_missing"

    result: dict[str, Any] = {
        "valid": False,
        "skill": skill_name,
        "target": target,
        "link": str(link),
        "expected_source": str(source),
        "status": optional_status,
        "skill_md_exists": False,
    }

    if not link.exists() and not link.is_symlink():
        result["error"] = "Symlink does not exist. Run install-skill first."
        if source.exists():
            result["status"] = "external_adoptable"
            result["source_available"] = True
        return result

    if not link.is_symlink():
        result["status"] = "real_dir_conflict"
        result["error"] = "Path exists but is not a symlink."
        return result

    try:
        resolved = link.resolve()
    except OSError as exc:
        result["status"] = "wrong_symlink"
        result["error"] = f"Broken symlink: {exc}"
        return result

    result["resolved"] = str(resolved)
    result["skill_md_exists"] = (resolved / "SKILL.md").exists()

    if skill_name == SKILL_NAME and resolved != canonical_source:
        result["status"] = "wrong_symlink"
        result["error"] = f"Symlink points to {resolved}, expected {source}."
        return result

    package_error = _skill_package_error(resolved, expected_name=skill_name)
    if package_error:
        result["status"] = "schema_incompatible"
        result["error"] = package_error
        return result

    result["valid"] = True
    result["status"] = "ready"
    if resolved != canonical_source:
        result["source_type"] = "external_adopted"
    else:
        result["source_type"] = "bundled"
    return result


def install_skill(
    target: str,
    agent_skill_dir: str | None = None,
    *,
    force: bool = False,
    source_skill_dir: str | None = None,
) -> dict[str, Any]:
    """Create a symlink from ``agent_skill_dir/deck-master`` to the installed skill.

    Returns a result dict with ``status``, ``link_path`` and ``target_dir``.
    Raises ``SkillInstallError`` on failure.
    """
    return _install_named_skill(
        SKILL_NAME,
        target,
        agent_skill_dir,
        force=force,
        source_skill_dir=source_skill_dir,
    )


def validate_skill(
    target: str,
    agent_skill_dir: str | None = None,
    source_skill_dir: str | None = None,
    *,
    write_log: bool = True,
) -> dict[str, Any]:
    """Check whether the skill symlink is valid and points to the installed skill.

    Returns a result dict with ``valid``, ``link_path`` and diagnostic details.
    """
    result = inspect_skill_link(
        target,
        agent_skill_dir,
        source_skill_dir,
        skill_name=SKILL_NAME,
        required=True,
    )
    if write_log:
        _append_install_log(
            "validate_skill",
            target=target,
            valid=bool(result.get("valid")),
            link=str(result.get("link", "")),
        )
    return result


def companion_manifest() -> dict[str, Any]:
    skills: list[dict[str, Any]] = []
    for spec in SUITE_SKILLS:
        item = {
            "name": spec["name"],
            "required_for": spec["required_for"],
            "install_source": spec["install_source"],
            "min_cli_version": "0.1.0" if spec["name"] != SKILL_NAME else SUITE_VERSION,
            "cli": spec["cli"],
            "required_capabilities": spec["required_capabilities"],
            "optional_capabilities": spec["optional_capabilities"],
            "schema_versions": spec["schema_versions"],
            "agent_targets": {
                "codex": f"~/.codex/skills/{spec['name']}",
                "claude-code": f"~/.claude/skills/{spec['name']}",
            },
            "adoption_policy": spec["adoption_policy"],
            "conflict_policy": spec["conflict_policy"],
        }
        if spec["name"] == SKILL_NAME:
            item["source_path"] = str(_resolve_source_dir(skill_name=SKILL_NAME))
        skills.append(item)
    return {
        "schema_version": COMPANION_MANIFEST_SCHEMA_VERSION,
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "skills": skills,
    }


def companion_manifest_path() -> Path:
    return INSTALL_LOG_DIR / "current" / COMPANION_MANIFEST_NAME


def write_companion_manifest() -> Path:
    path = companion_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(companion_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _suite_specs(include_optional: bool = False) -> list[dict[str, Any]]:
    return [
        spec for spec in SUITE_SKILLS
        if include_optional or spec.get("required", True)
    ]


def _cli_status(command: str) -> str:
    if command == "deck-master":
        return "ready"
    return "ready" if shutil.which(command) else "cli_missing"


def inspect_suite_status(
    *,
    targets: list[str] | None = None,
    include_optional: bool = True,
    agent_skill_dir: str | None = None,
) -> dict[str, Any]:
    """Pure-read suite readiness inspection."""
    resolved_targets = targets or ["codex"]
    skills: list[dict[str, Any]] = []
    capabilities: dict[str, str] = {}
    target_reports: dict[str, list[dict[str, Any]]] = {}

    for target in resolved_targets:
        reports: list[dict[str, Any]] = []
        for spec in _suite_specs(include_optional=include_optional):
            report = inspect_skill_link(
                target,
                agent_skill_dir,
                skill_name=str(spec["name"]),
                required=bool(spec.get("required", True)),
            )
            cli_state = _cli_status(str(spec.get("cli") or spec["name"]))
            if report.get("status") == "ready" and cli_state == "cli_missing" and spec["name"] != SKILL_NAME:
                report["status"] = "blocked_cli_missing"
                report["valid"] = False
            report["cli_status"] = cli_state
            report["required_for"] = spec["required_for"]
            report["required"] = bool(spec.get("required", True))
            reports.append(report)
            skills.append({**report, "target": target})
            for capability in spec.get("required_capabilities", []):
                capabilities[str(capability)] = str(report.get("status") or "missing")
        target_reports[target] = reports

    by_name: dict[str, str] = {}
    for item in skills:
        name = str(item["skill"])
        current = by_name.get(name)
        status = str(item.get("status") or "missing")
        if current == "ready" or status == "ready":
            by_name[name] = "ready"
        elif current is None:
            by_name[name] = status

    deck_ready = by_name.get(SKILL_NAME) == "ready"
    required_ready = all(
        by_name.get(str(spec["name"])) == "ready"
        for spec in _suite_specs(include_optional=False)
    )
    full_suite_ready = required_ready and by_name.get("ppt-master", "optional_missing") == "ready"

    task_readiness = {
        "full_deck_workflow": "ready" if required_ready else ("blocked" if not deck_ready else "degraded_ready"),
        "library_sourcing": "ready" if by_name.get("ppt-library") == "ready" else "blocked",
        "new_generation": "ready" if by_name.get("ppt-deck-pro-max") == "ready" else "blocked",
        "standalone_audit": "ready" if by_name.get("ppt-quality-gate") == "ready" else "blocked",
        "render_export": "ready" if by_name.get("ppt-master") == "ready" else "optional_missing",
    }

    status = "ready" if full_suite_ready else "degraded_ready"
    if not deck_ready:
        status = "blocked"

    next_command = ""
    next_agent_action = "Suite ready."
    if status == "blocked":
        next_command = "deck-master suite-repair --target codex"
        next_agent_action = "Repair Deck Master skill installation before creating or modifying production runs."
    elif not full_suite_ready:
        next_command = "deck-master suite-repair --target codex"
        next_agent_action = "Proceed only with tasks whose required companion capabilities are ready; repair missing companions when needed."

    return {
        "schema_version": COMPANION_MANIFEST_SCHEMA_VERSION,
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "status": status,
        "full_suite_ready": full_suite_ready,
        "skills": skills,
        "targets": target_reports,
        "capabilities": capabilities,
        "task_readiness": task_readiness,
        "manifest_path": str(companion_manifest_path()),
        "next_command": next_command,
        "next_agent_action": next_agent_action,
    }


def suite_install(
    *,
    targets: list[str] | None = None,
    include_optional: bool = False,
    repair: bool = False,
    agent_skill_dir: str | None = None,
) -> dict[str, Any]:
    resolved_targets = targets or ["codex"]
    manifest_path = write_companion_manifest()
    results: list[dict[str, Any]] = []
    for target in resolved_targets:
        for spec in _suite_specs(include_optional=include_optional):
            name = str(spec["name"])
            source = _resolve_source_dir(skill_name=name)
            if not source.exists():
                results.append({
                    "target": target,
                    "skill": name,
                    "status": "source_missing",
                    "required": bool(spec.get("required", True)),
                    "source": str(source),
                })
                continue
            try:
                result = _install_named_skill(name, target, agent_skill_dir, force=repair, source_skill_dir=str(source))
            except SkillInstallError as exc:
                results.append({
                    "target": target,
                    "skill": name,
                    "status": "blocked",
                    "error": str(exc),
                })
            else:
                result["target"] = target
                results.append(result)
    status = "installed"
    if any(item.get("status") == "blocked" for item in results):
        status = "blocked"
    elif any(item.get("status") == "source_missing" and item.get("required") for item in results):
        status = "degraded_installed"
    return {
        "schema_version": "deck_master_suite_install.v1",
        "status": status,
        "manifest_path": str(manifest_path),
        "results": results,
        "suite_status": inspect_suite_status(
            targets=resolved_targets,
            include_optional=True,
            agent_skill_dir=agent_skill_dir,
        ),
    }


def suite_repair(
    *,
    targets: list[str] | None = None,
    include_optional: bool = False,
    agent_skill_dir: str | None = None,
) -> dict[str, Any]:
    return suite_install(
        targets=targets,
        include_optional=include_optional,
        repair=True,
        agent_skill_dir=agent_skill_dir,
    )


def uninstall_skill(
    target: str,
    agent_skill_dir: str | None = None,
    source_skill_dir: str | None = None,
) -> dict[str, Any]:
    """Remove the symlink created by Deck Master.

    Only removes symlinks pointing to the expected Deck Master skill directory.
    Raises ``SkillInstallError`` if the path is not a Deck Master symlink.
    """
    if target not in SUPPORTED_TARGETS:
        raise SkillInstallError(
            f"Unsupported target '{target}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_TARGETS))}"
        )

    target_dir = _resolve_target_dir(target, agent_skill_dir)
    link = _link_path(target_dir)
    source = _resolve_source_dir(source_skill_dir)
    canonical_source = source.resolve() if source.exists() else source

    if not link.exists() and not link.is_symlink():
        _append_install_log(
            "uninstall_skill",
            target=target,
            status="not_installed",
            link=str(link),
        )
        return {
            "status": "not_installed",
            "link": str(link),
            "message": "No symlink found. Skill is not installed.",
        }

    if not link.is_symlink():
        raise SkillInstallError(
            f"Path {link} exists but is not a symlink. "
            "Deck Master will not remove real files or directories."
        )

    try:
        resolved = link.resolve()
    except OSError:
        resolved = None

    if resolved != canonical_source:
        raise SkillInstallError(
            f"Symlink at {link} points to {resolved}, not the Deck Master "
            f"skill ({source}). Refusing to remove a symlink we did not create."
        )

    link.unlink()

    _append_install_log(
        "uninstall_skill",
        target=target,
        status="uninstalled",
        link=str(link),
    )

    return {
        "status": "uninstalled",
        "link": str(link),
    }
