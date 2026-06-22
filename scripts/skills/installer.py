"""Deck Master skill installer.

Manages symlinks from external Agent skill directories to the
installed Deck Master skill package under ``~/.deck-master/current``.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_NAME = "deck-master"
SUITE_NAME = "deck-master"
SUITE_VERSION = "1.0.0"
COMPANION_MANIFEST_SCHEMA_VERSION = "deck_master_companion_manifest.v3"
PRODUCT_CAPABILITY_MANIFEST_SCHEMA_VERSION = "deck_master_product_capability_manifest.v1"
PRODUCT_CAPABILITY_MANIFEST_NAME = "product-capability-manifest.json"
RELEASE_MANIFEST_NAME = "release-manifest.json"
CAPABILITY_LOCK_NAME = "deck_capability_lock.json"
SHA256SUMS_NAME = "SHA256SUMS"
RELEASE_TREE_MARKER = ".release_tree_managed_by_deck_master"

SUPPORTED_TARGETS = {"codex", "claude-code", "hermes", "custom"}

DEFAULT_AGENT_SKILL_DIRS = {
    "codex": "~/.codex/skills",
    "claude-code": "~/.claude/skills",
    "hermes": "~/.hermes/skills",
}

INSTALL_LOG_DIR = Path.home() / ".deck-master"
INSTALL_LOG_NAME = "install_log.jsonl"
INSTALLED_SKILL_DIR = INSTALL_LOG_DIR / "current" / "skills" / SKILL_NAME
_DEFAULT_INSTALLED_SKILL_DIR = INSTALLED_SKILL_DIR
COMPANION_MANIFEST_NAME = "companion-manifest.json"

SUITE_SKILLS: list[dict[str, Any]] = [
    {
        "name": "deck-master",
        "required": True,
        "role": "orchestrator",
        "public_name": "deck-master",
        "compat_aliases": [],
        "input_types": ["deck_workflow", "run_state", "review_cockpit"],
        "exit_artifacts": ["run_state", "next_step", "review_workspace"],
        "backend_dependency": "",
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
        "name": "deck-setup",
        "required": True,
        "role": "setup",
        "public_name": "deck-setup",
        "compat_aliases": [],
        "input_types": ["first_run_setup", "suite_install"],
        "exit_artifacts": ["setup_status", "suite_status"],
        "backend_dependency": "",
        "required_for": ["setup", "suite_install"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.setup.v1"],
        "optional_capabilities": [],
        "schema_versions": {"setup_status": "deck_master_setup_status.v2"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-upgrade",
        "required": True,
        "role": "upgrade",
        "public_name": "deck-upgrade",
        "compat_aliases": [],
        "input_types": ["upgrade", "rollback", "release_tree"],
        "exit_artifacts": ["release_manifest", "capability_lock", "sha256sums"],
        "backend_dependency": "",
        "required_for": ["upgrade", "release_management"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.release.v1"],
        "optional_capabilities": [],
        "schema_versions": {"release_manifest": "deck_master_release_manifest.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-doctor",
        "required": True,
        "role": "diagnostics",
        "public_name": "deck-doctor",
        "compat_aliases": [],
        "input_types": ["setup_issue", "suite_issue", "run_issue"],
        "exit_artifacts": ["doctor_report", "setup_status", "run_state"],
        "backend_dependency": "",
        "required_for": ["diagnostics", "repair"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.doctor.v1"],
        "optional_capabilities": [],
        "schema_versions": {"doctor_report": "deck_master_doctor.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-init",
        "required": True,
        "role": "workspace_initialization",
        "public_name": "deck-init",
        "compat_aliases": ["init-workspace"],
        "input_types": ["new_workspace", "raw_materials_directory", "project_start"],
        "exit_artifacts": ["deck_project", "material_inventory", "workspace_policy", "run_bindings"],
        "backend_dependency": "",
        "required_for": ["deck_init", "workspace"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.workspace_init.v1"],
        "optional_capabilities": [],
        "schema_versions": {"deck_project": "deck_master_project.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-brief",
        "required": True,
        "role": "briefing",
        "public_name": "deck-brief",
        "compat_aliases": ["build-brief"],
        "input_types": ["raw_materials", "deep_research_report", "meeting_notes"],
        "exit_artifacts": ["deck_brief", "claim_map_seed"],
        "backend_dependency": "",
        "required_for": ["brief", "context"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.brief.v1"],
        "optional_capabilities": [],
        "schema_versions": {"deck_brief": "deck_brief.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-planner",
        "required": True,
        "role": "planning",
        "public_name": "deck-planner",
        "compat_aliases": ["autoplan"],
        "input_types": ["deck_brief", "claim_map", "narrative_request"],
        "exit_artifacts": ["narrative_plan", "page_tasks", "sourcing_intent"],
        "backend_dependency": "",
        "required_for": ["planning", "brief", "claim_map", "narrative_plan"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.planning.v1"],
        "optional_capabilities": [],
        "schema_versions": {"planning_state": "deck_planning_state.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-sourcing",
        "required": True,
        "role": "asset_sourcing",
        "public_name": "deck-sourcing",
        "compat_aliases": ["ppt-library"],
        "input_types": ["page_tasks", "asset_request", "historical_slide_search"],
        "exit_artifacts": ["library_selection", "sourcing_plan", "asset_feedback"],
        "backend_dependency": "ppt-library",
        "required_for": ["library_sourcing", "asset_feedback"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.sourcing.v1"],
        "optional_capabilities": ["ppt_library.feedback.v1"],
        "schema_versions": {"sourcing_plan": "deck_sourcing_plan.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-producer",
        "required": True,
        "role": "page_production",
        "public_name": "deck-producer",
        "compat_aliases": ["ppt-deck-pro-max"],
        "input_types": ["generation_session", "page_tasks", "dispatch_package"],
        "exit_artifacts": ["deck_generation_result.v2", "preview_refresh"],
        "backend_dependency": "ppt-deck-pro-max",
        "required_for": ["new_generation", "adapt_generation"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.generation.v1"],
        "optional_capabilities": [],
        "schema_versions": {
            "generation_result": "deck_generation_result.v2",
            "generation_result_legacy": "deck_generation_result.v1",
        },
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-builder",
        "required": True,
        "role": "build",
        "public_name": "deck-builder",
        "compat_aliases": ["ppt-master", "render"],
        "input_types": ["approved_preview", "build_manifest", "render_request"],
        "exit_artifacts": ["build_manifest", "artifact_manifest", "render_result.v2", "final_artifacts"],
        "backend_dependency": "ppt-master",
        "required_for": ["build", "render", "delivery", "benchmark_rc"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.build.v1"],
        "optional_capabilities": [],
        "schema_versions": {
            "build_manifest": "deck_build_manifest.v1",
            "render_result": "deck_render_result.v2",
        },
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-quality",
        "required": True,
        "role": "quality_gate",
        "public_name": "deck-quality",
        "compat_aliases": ["ppt-quality-gate"],
        "input_types": ["draft_review", "render_artifact", "delivery_artifact", "pptx_package"],
        "exit_artifacts": ["quality_report", "customer_visible_safety_gate", "delivery_gate"],
        "backend_dependency": "ppt-quality-gate",
        "required_for": ["quality", "standalone_audit", "quality_findings_import"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.quality.v1"],
        "optional_capabilities": [],
        "schema_versions": {
            "quality_report": "deck_quality_report.v1",
            "customer_visible_safety_gate": "deck_customer_visible_safety_gate.v1",
        },
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-review",
        "required": True,
        "role": "review_delivery",
        "public_name": "deck-review",
        "compat_aliases": ["export", "final-readiness"],
        "input_types": ["quality_report", "final_readiness", "review_workspace"],
        "exit_artifacts": ["export_queue", "final_readiness", "delivery_validation"],
        "backend_dependency": "",
        "required_for": ["review", "quality", "delivery"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.review.v1"],
        "optional_capabilities": [],
        "schema_versions": {"run_state": "deck_run_state.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-learn",
        "required": False,
        "role": "learning",
        "public_name": "deck-learn",
        "compat_aliases": ["build-learning-pack"],
        "input_types": ["delivery_outcome", "library_feedback", "benchmark_result"],
        "exit_artifacts": ["workspace_learning_pack", "feedback_queue"],
        "backend_dependency": "",
        "required_for": ["learning", "asset_feedback"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.learning.v1"],
        "optional_capabilities": [],
        "schema_versions": {"workspace_learning_pack": "deck_workspace_learning_pack.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "deck-autopilot",
        "required": True,
        "role": "workflow",
        "public_name": "deck-autopilot",
        "compat_aliases": ["autopilot-v1"],
        "input_types": ["raw_materials", "run_state", "repair_request", "review_request"],
        "exit_artifacts": ["workflow_report", "run_state", "next_step"],
        "backend_dependency": "",
        "required_for": ["workflow_autopilot", "full_deck_workflow"],
        "install_source": "bundled",
        "cli": "deck-master",
        "required_capabilities": ["deck_master.autopilot.v1"],
        "optional_capabilities": [],
        "schema_versions": {"workflow_report": "deck_master_autopilot.v1"},
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "ppt-master",
        "required": True,
        "role": "compatibility_backend",
        "public_name": "deck-builder",
        "compat_aliases": [],
        "input_types": ["render_request", "build_backend"],
        "exit_artifacts": ["render_result.v2", "final_artifacts"],
        "backend_dependency": "",
        "required_for": ["render", "delivery", "benchmark_rc"],
        "install_source": "release_bundle",
        "cli": "deck-master",
        "required_capabilities": ["ppt_master.render.v1", "ppt_master.handback.v1"],
        "optional_capabilities": [],
        "schema_versions": {
            "render_result": "deck_render_result.v2",
            "render_result_legacy": "deck_render_result.v1",
        },
        "adoption_policy": "preserve_full_external_or_bundled_symlink",
        "conflict_policy": "never_overwrite_full_external_directory",
    },
    {
        "name": "ppt-library",
        "required": True,
        "role": "compatibility_alias",
        "public_name": "deck-sourcing",
        "compat_aliases": [],
        "input_types": ["historical_slide_search", "library_selection"],
        "exit_artifacts": ["library_selection", "asset_feedback"],
        "backend_dependency": "",
        "required_for": ["library_sourcing", "asset_feedback"],
        "install_source": "release_bundle",
        "cli": "deck-master",
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
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "ppt-deck-pro-max",
        "required": True,
        "role": "compatibility_alias",
        "public_name": "deck-producer",
        "compat_aliases": [],
        "input_types": ["generation_session", "page_production"],
        "exit_artifacts": ["deck_generation_result.v2"],
        "backend_dependency": "",
        "required_for": ["new_generation", "adapt_generation"],
        "install_source": "release_bundle",
        "cli": "deck-master",
        "required_capabilities": [
            "ppt_deck_pro_max.generate.v1",
            "ppt_deck_pro_max.handback.v1",
        ],
        "optional_capabilities": [],
        "schema_versions": {
            "generation_result_input": "ppt_deck_pro_max_generation_result.v1",
            "generation_result_canonical": "deck_generation_result.v1",
        },
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
    {
        "name": "ppt-quality-gate",
        "required": True,
        "role": "compatibility_alias",
        "public_name": "deck-quality",
        "compat_aliases": [],
        "input_types": ["quality_audit", "quality_findings"],
        "exit_artifacts": ["quality_report", "quality_findings"],
        "backend_dependency": "",
        "required_for": ["standalone_audit", "quality_findings_import"],
        "install_source": "release_bundle",
        "cli": "deck-master",
        "required_capabilities": [
            "ppt_quality_gate.audit.v1",
            "ppt_quality_gate.findings.v1",
        ],
        "optional_capabilities": [],
        "schema_versions": {
            "quality_findings_input": "deck_master_quality_findings.v1",
            "quality_report_canonical": "deck_quality_report.v1",
        },
        "adoption_policy": "bundled_symlink_only",
        "conflict_policy": "never_overwrite_real_directory",
    },
]


class SkillInstallError(Exception):
    """Raised when a skill installation operation fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_skill_dir(skill_name: str = SKILL_NAME) -> Path:
    """Return the absolute path to a skill package in this repo."""
    return _repo_root() / "skills" / skill_name


def _repo_capability_dir(name: str) -> Path:
    source = _repo_root() / "product_capabilities" / name
    if source.exists():
        return source
    return _repo_root() / "capabilities" / name


def _installed_capability_dir(name: str) -> Path:
    return INSTALL_LOG_DIR / "current" / "capabilities" / name


def _installed_skill_dir(skill_name: str = SKILL_NAME) -> Path:
    if skill_name == SKILL_NAME:
        if INSTALLED_SKILL_DIR != _DEFAULT_INSTALLED_SKILL_DIR:
            return INSTALLED_SKILL_DIR
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


def _is_full_external_skill_package(path: Path, skill_name: str) -> bool:
    """Detect high-value standalone skill packages that must not be replaced."""
    if skill_name != "ppt-master":
        return False
    if not path.exists() or path.is_symlink() or not path.is_dir():
        return False
    if _skill_package_error(path, expected_name=skill_name):
        return False
    required_dirs = ("references", "scripts", "templates")
    for dirname in required_dirs:
        child = path / dirname
        if not child.is_dir() or not any(child.iterdir()):
            return False
    return True


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
        if _is_full_external_skill_package(link, skill_name):
            _append_install_log(
                "install_skill",
                target=target,
                skill=skill_name,
                status="external_full_package_preserved",
                link=str(link),
                source=str(source),
            )
            return {
                "status": "external_full_package_preserved",
                "skill": skill_name,
                "link": str(link),
                "source": str(source),
                "target_dir": str(target_dir),
                "source_type": "external_full_package",
            }
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
        if _is_full_external_skill_package(link, skill_name):
            result.update({
                "valid": True,
                "status": "ready",
                "resolved": str(link.resolve()),
                "skill_md_exists": True,
                "source_type": "external_full_package",
            })
            return result
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

    if resolved != canonical_source:
        result["status"] = "foreign_symlink"
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
            "role": spec.get("role", ""),
            "public_name": spec.get("public_name", spec["name"]),
            "compat_aliases": list(spec.get("compat_aliases") or []),
            "input_types": list(spec.get("input_types") or []),
            "exit_artifacts": list(spec.get("exit_artifacts") or []),
            "backend_dependency": spec.get("backend_dependency", ""),
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


def product_capability_manifest() -> dict[str, Any]:
    core = [
        str(spec["name"])
        for spec in SUITE_SKILLS
        if str(spec["name"]).startswith("deck-") and str(spec.get("role") or "") != "compatibility_alias"
    ]
    product_capabilities = [str(spec["name"]) for spec in SUITE_SKILLS if str(spec["name"]).startswith("ppt-")]
    backend_dependencies = {
        str(spec["name"]): str(spec.get("backend_dependency") or "")
        for spec in SUITE_SKILLS
        if spec.get("backend_dependency")
    }
    public_routes = {
        str(spec["name"]): {
            "role": str(spec.get("role") or ""),
            "public_name": str(spec.get("public_name") or spec["name"]),
            "compat_aliases": list(spec.get("compat_aliases") or []),
            "input_types": list(spec.get("input_types") or []),
            "exit_artifacts": list(spec.get("exit_artifacts") or []),
            "backend_dependency": str(spec.get("backend_dependency") or ""),
        }
        for spec in SUITE_SKILLS
    }
    return {
        "schema_version": PRODUCT_CAPABILITY_MANIFEST_SCHEMA_VERSION,
        "product": "deck-master",
        "runtime_shape": "agent_facing_local_first",
        "provider_policy": "zero_builtin_llm_provider",
        "required_capabilities": [str(spec["name"]) for spec in _suite_specs(include_optional=False)],
        "optional_capabilities": ["deck-learn"],
        "core_skills": core,
        "public_skills": core,
        "product_capability_skills": product_capabilities,
        "compatibility_skills": product_capabilities,
        "backend_dependencies": backend_dependencies,
        "skill_routes": public_routes,
        "capability_policy": {
            "required_suite_must_be_full_ready": True,
            "outputs_must_write_back_to_run": True,
            "external_override_allowed": True,
            "legacy_real_dir_requires_migration_plan": True,
            "full_external_capability_directory_must_be_preserved": True,
        },
        "release_tree": {
            "skills_path": "skills",
            "capabilities_path": "capabilities",
            "contracts_path": "contracts",
            "reference_packs_path": "reference-packs",
        },
    }


def validate_product_capability_manifest(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = payload or product_capability_manifest()
    errors: list[str] = []
    if manifest.get("schema_version") != PRODUCT_CAPABILITY_MANIFEST_SCHEMA_VERSION:
        errors.append("schema_version")
    if manifest.get("runtime_shape") != "agent_facing_local_first":
        errors.append("runtime_shape")
    required = manifest.get("required_capabilities")
    if not isinstance(required, list) or not required:
        errors.append("required_capabilities")
    for skill in product_capability_manifest()["required_capabilities"]:
        if skill not in (required or []):
            errors.append(f"required_capability:{skill}")
    return {
        "schema_version": "deck_master_product_capability_manifest_validation.v1",
        "valid": not errors,
        "errors": errors,
        "manifest": manifest,
    }


def companion_manifest_path() -> Path:
    return INSTALL_LOG_DIR / "current" / COMPANION_MANIFEST_NAME


def product_capability_manifest_path() -> Path:
    return INSTALL_LOG_DIR / "current" / PRODUCT_CAPABILITY_MANIFEST_NAME


def write_companion_manifest() -> Path:
    path = companion_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(companion_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _copytree_replace(src: Path, dst: Path, *, ignore: Any | None = None) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True, ignore=ignore)


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    head = result.stdout.strip()
    return head or None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_files(release_root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in release_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel_path = path.relative_to(release_root)
        rel = rel_path.as_posix()
        if rel in {SHA256SUMS_NAME, "release-activation.json"}:
            continue
        if "__pycache__" in rel_path.parts or path.suffix == ".pyc":
            continue
        files.append((rel, path))
    return sorted(files, key=lambda item: item[0])


def _contract_lock_entries(release_root: Path) -> list[dict[str, Any]]:
    contracts_root = release_root / "contracts"
    if not contracts_root.exists():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(contracts_root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        entries.append({
            "path": path.relative_to(release_root).as_posix(),
            "sha256": _sha256_file(path),
        })
    return entries


def _write_sha256sums(release_root: Path) -> Path:
    lines = [f"{_sha256_file(path)}  {rel}\n" for rel, path in _release_files(release_root)]
    path = release_root / SHA256SUMS_NAME
    path.write_text("".join(lines), encoding="utf-8")
    return path


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _release_id() -> str:
    return _utc_now().replace(":", "").replace("+", "Z").replace(".", "")


def _safe_release_child(root: Path, rel: str) -> Path | None:
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        return None
    try:
        path = (root / rel_path).resolve()
        path.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return path


def verify_release_tree(
    release_root: str | Path | None = None,
    *,
    run_smoke: bool = True,
) -> dict[str, Any]:
    root = Path(release_root).expanduser().resolve() if release_root else INSTALL_LOG_DIR / "current"
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def add_error(code: str, path: str = "", detail: str = "") -> None:
        errors.append({"code": code, "path": path, "detail": detail})

    required_files = [
        RELEASE_TREE_MARKER,
        "bin/deck-master",
        "scripts/deck_master.py",
        PRODUCT_CAPABILITY_MANIFEST_NAME,
        COMPANION_MANIFEST_NAME,
        RELEASE_MANIFEST_NAME,
        CAPABILITY_LOCK_NAME,
        SHA256SUMS_NAME,
    ]
    for rel in required_files:
        path = root / rel
        if not path.exists():
            add_error("missing_required_file", rel)

    product_manifest: dict[str, Any] | None = None
    product_manifest_path = root / PRODUCT_CAPABILITY_MANIFEST_NAME
    if product_manifest_path.exists():
        try:
            product_manifest = json.loads(product_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            add_error("invalid_json", PRODUCT_CAPABILITY_MANIFEST_NAME, str(exc))
        else:
            validation = validate_product_capability_manifest(product_manifest)
            if not validation["valid"]:
                add_error(
                    "invalid_product_capability_manifest",
                    PRODUCT_CAPABILITY_MANIFEST_NAME,
                    ",".join(validation["errors"]),
                )

    for rel, schema_version in [
        (COMPANION_MANIFEST_NAME, COMPANION_MANIFEST_SCHEMA_VERSION),
        (RELEASE_MANIFEST_NAME, "deck_master_release_manifest.v1"),
        (CAPABILITY_LOCK_NAME, "deck_capability_lock.v1"),
    ]:
        path = root / rel
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            add_error("invalid_json", rel, str(exc))
            continue
        if payload.get("schema_version") != schema_version:
            add_error("invalid_schema_version", rel, str(payload.get("schema_version") or ""))
        if rel == RELEASE_MANIFEST_NAME and payload.get("self_contained") is not True:
            add_error("release_not_self_contained", rel)
        if rel == CAPABILITY_LOCK_NAME and not payload.get("contracts"):
            add_error("missing_contract_lock_entries", rel)

    for skill_name in product_capability_manifest()["required_capabilities"]:
        if not (root / "skills" / skill_name / "SKILL.md").exists():
            add_error("missing_skill_package", f"skills/{skill_name}/SKILL.md")
    for capability_name in [str(spec["name"]) for spec in SUITE_SKILLS if str(spec["name"]).startswith("ppt-")]:
        if not (root / "capabilities" / capability_name / "capability.json").exists():
            add_error("missing_capability_package", f"capabilities/{capability_name}/capability.json")

    bin_path = root / "bin" / "deck-master"
    if bin_path.exists():
        bin_text = bin_path.read_text(encoding="utf-8")
        source_script = str(_repo_root() / "scripts" / "deck_master.py")
        if source_script in bin_text:
            add_error("source_checkout_path_embedded", "bin/deck-master", source_script)
        if "RELEASE_ROOT" not in bin_text or "scripts/deck_master.py" not in bin_text:
            add_error("invalid_release_entrypoint", "bin/deck-master")

    sha_path = root / SHA256SUMS_NAME
    if sha_path.exists():
        declared: dict[str, str] = {}
        for line_no, raw_line in enumerate(sha_path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                add_error("invalid_sha256sums_line", SHA256SUMS_NAME, str(line_no))
                continue
            digest, rel = parts[0], parts[1].strip()
            target = _safe_release_child(root, rel)
            if target is None:
                add_error("unsafe_sha256_path", rel)
                continue
            if not target.exists() or not target.is_file():
                add_error("sha256_target_missing", rel)
                continue
            actual = _sha256_file(target)
            if actual != digest:
                add_error("sha256_mismatch", rel)
            declared[rel] = digest
        actual_files = {rel for rel, _path in _release_files(root)}
        for rel in sorted(actual_files - set(declared)):
            add_error("file_missing_from_sha256sums", rel)
        for rel in sorted(set(declared) - actual_files):
            add_error("sha256_entry_without_file", rel)

    smoke: dict[str, Any] = {"skipped": not run_smoke}
    if run_smoke and bin_path.exists():
        try:
            completed = subprocess.run(
                [str(bin_path), "--help"],
                cwd=root,
                check=False,
                capture_output=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            add_error("release_smoke_failed", "bin/deck-master", str(exc))
            smoke = {"skipped": False, "status": "failed", "error": str(exc)}
        else:
            smoke = {
                "skipped": False,
                "status": "passed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
            }
            if completed.returncode != 0:
                add_error("release_smoke_failed", "bin/deck-master", completed.stderr.strip())
    elif run_smoke:
        smoke = {"skipped": False, "status": "failed", "error": "missing bin/deck-master"}

    if product_manifest is None and product_manifest_path.exists():
        warnings.append({"code": "product_manifest_unavailable", "path": PRODUCT_CAPABILITY_MANIFEST_NAME})

    return {
        "schema_version": "deck_master_release_verification.v1",
        "release_root": str(root),
        "valid": not errors,
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "smoke": smoke,
    }


def _activate_staged_release(staged_release: Path) -> dict[str, Any]:
    current = INSTALL_LOG_DIR / "current"
    previous = INSTALL_LOG_DIR / "previous"
    failed_dir = INSTALL_LOG_DIR / "failed"
    previous_path = ""
    try:
        _remove_path(previous)
        if current.exists() or current.is_symlink():
            shutil.move(str(current), str(previous))
            previous_path = str(previous)
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_release), str(current))
    except Exception as exc:
        if current.exists() or current.is_symlink():
            failed_dir.mkdir(parents=True, exist_ok=True)
            failed_path = failed_dir / f"activation-{_release_id()}"
            shutil.move(str(current), str(failed_path))
        if previous.exists() and not current.exists():
            shutil.move(str(previous), str(current))
        raise SkillInstallError(f"Release activation failed and previous release was restored: {exc}") from exc

    activation = {
        "schema_version": "deck_master_release_activation.v1",
        "status": "activated",
        "activated_at": _utc_now(),
        "current": str(current),
        "previous": previous_path,
    }
    (current / "release-activation.json").write_text(
        json.dumps(activation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return activation


def install_release_tree(*, run_smoke: bool = True) -> dict[str, Any]:
    release_id = _release_id()
    staged_release = INSTALL_LOG_DIR / "staging" / f"release-{release_id}"
    if staged_release.exists():
        _remove_path(staged_release)
    build = build_release_tree(staged_release, force=True)
    verification = verify_release_tree(staged_release, run_smoke=run_smoke)
    if not verification["valid"]:
        return {
            "schema_version": "deck_master_release_install.v1",
            "status": "blocked",
            "release_id": release_id,
            "staged_release": str(staged_release),
            "build": build,
            "verification": verification,
            "activated": False,
        }
    activation = _activate_staged_release(staged_release)
    return {
        "schema_version": "deck_master_release_install.v1",
        "status": "installed",
        "release_id": release_id,
        "build": build,
        "verification": verification,
        "activation": activation,
        "activated": True,
    }


def rollback_release_tree() -> dict[str, Any]:
    current = INSTALL_LOG_DIR / "current"
    previous = INSTALL_LOG_DIR / "previous"
    if not previous.exists():
        raise SkillInstallError(f"Previous release not found: {previous}")
    failed_dir = INSTALL_LOG_DIR / "failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    archived_current = failed_dir / f"rollback-current-{_release_id()}"
    if current.exists() or current.is_symlink():
        shutil.move(str(current), str(archived_current))
    shutil.move(str(previous), str(current))
    verification = verify_release_tree(current, run_smoke=True)
    if not verification["valid"]:
        raise SkillInstallError("Rollback restored previous release, but verification failed.")
    return {
        "schema_version": "deck_master_release_rollback.v1",
        "status": "rolled_back",
        "current": str(current),
        "archived_current": str(archived_current),
        "verification": verification,
    }


def build_release_tree(
    output: str | Path | None = None,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    release_root = Path(output).expanduser().resolve() if output else INSTALL_LOG_DIR / "current"
    marker = release_root / RELEASE_TREE_MARKER
    planned = [
        "bin/deck-master",
        PRODUCT_CAPABILITY_MANIFEST_NAME,
        COMPANION_MANIFEST_NAME,
        RELEASE_MANIFEST_NAME,
        CAPABILITY_LOCK_NAME,
        SHA256SUMS_NAME,
        "skills",
        "capabilities",
        "contracts",
        "reference-packs",
        "examples",
        "benchmarks",
        "scripts",
    ]

    if dry_run:
        return {
            "schema_version": "deck_master_release_tree.v1",
            "status": "dry_run",
            "release_root": str(release_root),
            "planned": planned,
        }

    if release_root.exists() and any(release_root.iterdir()) and not marker.exists() and not force:
        raise SkillInstallError(
            f"Release root {release_root} is not managed by Deck Master. "
            "Use --force only after confirming it is safe."
        )

    release_root.mkdir(parents=True, exist_ok=True)
    marker.write_text("deck-master release tree\n", encoding="utf-8")

    for subdir in ("skills", "capabilities", "contracts", "reference-packs", "examples", "benchmarks", "bin", "scripts"):
        (release_root / subdir).mkdir(parents=True, exist_ok=True)

    for spec in _suite_specs(include_optional=False):
        name = str(spec["name"])
        source = _repo_skill_dir(name)
        if not source.exists():
            raise SkillInstallError(f"Required skill package missing: {source}")
        _copytree_replace(source, release_root / "skills" / name)

    for name in [str(spec["name"]) for spec in SUITE_SKILLS if str(spec["name"]).startswith("ppt-")]:
        source = _repo_capability_dir(name)
        if not source.exists():
            raise SkillInstallError(f"Required capability package missing: {source}")
        _copytree_replace(source, release_root / "capabilities" / name)

    contracts_src = _repo_root() / "docs" / "contracts"
    if not contracts_src.exists():
        contracts_src = _repo_root() / "contracts"
    if contracts_src.exists():
        _copytree_replace(contracts_src, release_root / "contracts")

    examples_src = _repo_root() / "examples"
    if examples_src.exists():
        _copytree_replace(
            examples_src,
            release_root / "examples",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache"),
        )

    benchmarks_src = _repo_root() / "benchmarks"
    if benchmarks_src.exists():
        _copytree_replace(
            benchmarks_src,
            release_root / "benchmarks",
            ignore=shutil.ignore_patterns("results", "__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache"),
        )

    _copytree_replace(
        _repo_root() / "scripts",
        release_root / "scripts",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache"),
    )

    (release_root / PRODUCT_CAPABILITY_MANIFEST_NAME).write_text(
        json.dumps(product_capability_manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (release_root / COMPANION_MANIFEST_NAME).write_text(
        json.dumps(companion_manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    bin_path = release_root / "bin" / "deck-master"
    bin_path.write_text(
        "#!/usr/bin/env sh\n"
        'RELEASE_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"\n'
        'exec python3 "$RELEASE_ROOT/scripts/deck_master.py" "$@"\n',
        encoding="utf-8",
    )
    bin_path.chmod(0o755)

    release_skills = [str(spec["name"]) for spec in _suite_specs(include_optional=False)]
    release_capabilities = [str(spec["name"]) for spec in SUITE_SKILLS if str(spec["name"]).startswith("ppt-")]
    source = {
        "repo_root": str(_repo_root()),
        "git_head": _git_head(),
    }
    capability_lock = {
        "schema_version": "deck_capability_lock.v1",
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "built_at": _utc_now(),
        "source": source,
        "skills": [
            {
                "name": str(spec["name"]),
                "path": f"skills/{spec['name']}",
                "required": bool(spec.get("required", True)),
                "install_source": str(spec.get("install_source") or ""),
                "required_capabilities": list(spec.get("required_capabilities") or []),
            }
            for spec in _suite_specs(include_optional=False)
        ],
        "capabilities": [
            {
                "name": name,
                "path": f"capabilities/{name}",
                "required": True,
            }
            for name in release_capabilities
        ],
        "contracts": _contract_lock_entries(release_root),
    }
    (release_root / CAPABILITY_LOCK_NAME).write_text(
        json.dumps(capability_lock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    release_manifest = {
        "schema_version": "deck_master_release_manifest.v1",
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "built_at": _utc_now(),
        "release_root": str(release_root),
        "self_contained": True,
        "entrypoint": "bin/deck-master",
        "scripts": "scripts",
        "examples": "examples",
        "benchmarks": "benchmarks",
        "product_capability_manifest": PRODUCT_CAPABILITY_MANIFEST_NAME,
        "companion_manifest": COMPANION_MANIFEST_NAME,
        "capability_lock": CAPABILITY_LOCK_NAME,
        "sha256sums": SHA256SUMS_NAME,
        "source": source,
        "skills": release_skills,
        "capabilities": release_capabilities,
    }
    (release_root / RELEASE_MANIFEST_NAME).write_text(
        json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sha256sums_path = _write_sha256sums(release_root)

    return {
        "schema_version": "deck_master_release_tree.v1",
        "status": "built",
        "release_root": str(release_root),
        "manifest_path": str(release_root / PRODUCT_CAPABILITY_MANIFEST_NAME),
        "release_manifest": str(release_root / RELEASE_MANIFEST_NAME),
        "capability_lock": str(release_root / CAPABILITY_LOCK_NAME),
        "sha256sums": str(sha256sums_path),
        "self_contained": True,
        "skills": release_skills,
        "capabilities": release_capabilities,
    }


def _suite_specs(include_optional: bool = False) -> list[dict[str, Any]]:
    return [
        spec for spec in SUITE_SKILLS
        if include_optional or spec.get("required", True)
    ]


def _cli_status(command: str, *, skill_name: str = "") -> str:
    if command == "deck-master":
        return "ready"
    if skill_name.startswith("ppt-") and (
        _installed_capability_dir(skill_name).exists() or _repo_capability_dir(skill_name).exists()
    ):
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
    target_readiness: dict[str, dict[str, Any]] = {}

    for target in resolved_targets:
        reports: list[dict[str, Any]] = []
        for spec in _suite_specs(include_optional=include_optional):
            report = inspect_skill_link(
                target,
                agent_skill_dir,
                skill_name=str(spec["name"]),
                required=bool(spec.get("required", True)),
            )
            cli_state = _cli_status(str(spec.get("cli") or spec["name"]), skill_name=str(spec["name"]))
            if report.get("status") == "ready" and cli_state == "cli_missing" and spec["name"] != SKILL_NAME:
                report["status"] = "blocked_cli_missing"
                report["valid"] = False
            report["cli_status"] = cli_state
            report["role"] = str(spec.get("role") or "")
            report["public_name"] = str(spec.get("public_name") or spec["name"])
            report["compat_aliases"] = list(spec.get("compat_aliases") or [])
            report["input_types"] = list(spec.get("input_types") or [])
            report["exit_artifacts"] = list(spec.get("exit_artifacts") or [])
            report["backend_dependency"] = str(spec.get("backend_dependency") or "")
            report["required_for"] = spec["required_for"]
            report["required"] = bool(spec.get("required", True))
            reports.append(report)
            skills.append({**report, "target": target})
            for capability in spec.get("required_capabilities", []):
                capabilities[str(capability)] = str(report.get("status") or "missing")
        target_reports[target] = reports
        required_reports = [report for report in reports if report.get("required")]
        missing_statuses = {"missing", "external_adoptable", "optional_missing", "source_missing"}
        missing_required = [
            str(report.get("skill"))
            for report in required_reports
            if str(report.get("status") or "missing") in missing_statuses
        ]
        blocked_required = [
            str(report.get("skill"))
            for report in required_reports
            if str(report.get("status") or "missing") not in missing_statuses
            and str(report.get("status") or "missing") != "ready"
        ]
        target_readiness[target] = {
            "required_ready": not missing_required and not blocked_required,
            "missing_required": missing_required,
            "blocked_required": blocked_required,
        }

    by_name: dict[str, str] = {}
    for item in skills:
        name = str(item["skill"])
        current = by_name.get(name)
        status = str(item.get("status") or "missing")
        if current == "ready" or status == "ready":
            by_name[name] = "ready"
        elif current is None:
            by_name[name] = status

    deck_ready = all(
        any(report.get("skill") == SKILL_NAME and report.get("status") == "ready" for report in target_reports[target])
        for target in resolved_targets
    )
    full_suite_ready = all(
        bool(target_readiness[target]["required_ready"])
        for target in resolved_targets
    )

    def ready(*names: str) -> bool:
        return all(by_name.get(name) == "ready" for name in names)

    task_readiness = {
        "full_deck_workflow": "ready" if full_suite_ready else ("blocked" if not deck_ready else "degraded_ready"),
        "setup": "ready" if ready("deck-setup") else "blocked",
        "upgrade": "ready" if ready("deck-upgrade") else "blocked",
        "diagnostics": "ready" if ready("deck-doctor") else "blocked",
        "deck_init": "ready" if ready("deck-init") else "blocked",
        "brief": "ready" if ready("deck-brief") else "blocked",
        "planning": "ready" if by_name.get("deck-planner") == "ready" else "blocked",
        "review": "ready" if by_name.get("deck-review") == "ready" else "blocked",
        "deck_sourcing": "ready" if ready("deck-sourcing") else "blocked",
        "library_sourcing": "ready" if ready("deck-sourcing", "ppt-library") else "blocked",
        "deck_producer": "ready" if ready("deck-producer") else "blocked",
        "new_generation": "ready" if ready("deck-producer", "ppt-deck-pro-max") else "blocked",
        "deck_builder_adapter": "ready" if ready("deck-builder") else "blocked",
        "ppt_master_backend": "ready" if ready("ppt-master") else "blocked",
        "deck_builder": "ready" if ready("deck-builder", "ppt-master") else "blocked",
        "render": "ready" if ready("deck-builder", "ppt-master") else "blocked",
        "deck_quality": "ready" if ready("deck-quality") else "blocked",
        "standalone_audit": "ready" if ready("deck-quality", "ppt-quality-gate") else "blocked",
        "learning": "ready" if by_name.get("deck-learn") == "ready" else "optional",
        "workflow_autopilot": "ready" if ready("deck-autopilot") else "blocked",
        "delivery": "ready" if full_suite_ready else "blocked",
    }

    status = "ready" if full_suite_ready else "degraded_ready"
    if not deck_ready:
        status = "blocked"

    next_command = ""
    next_agent_action = "Suite ready."
    if status == "blocked":
        next_command = "deck-master suite-repair --target codex --target claude-code"
        next_agent_action = "Repair Deck Master skill installation before creating or modifying production runs."
    elif not full_suite_ready:
        next_command = "deck-master suite-repair --target codex --target claude-code"
        next_agent_action = "Repair missing required Deck Master product capabilities before production work."

    return {
        "schema_version": COMPANION_MANIFEST_SCHEMA_VERSION,
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "status": status,
        "full_suite_ready": full_suite_ready,
        "skills": skills,
        "targets": target_reports,
        "target_readiness": target_readiness,
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
    release_install = install_release_tree()
    if release_install["status"] != "installed":
        return {
            "schema_version": "deck_master_suite_install.v1",
            "status": "blocked",
            "release_install": release_install,
            "manifest_path": str(INSTALL_LOG_DIR / "current" / COMPANION_MANIFEST_NAME),
            "results": [],
            "suite_status": inspect_suite_status(
                targets=resolved_targets,
                include_optional=True,
                agent_skill_dir=agent_skill_dir,
            ),
        }
    manifest_path = INSTALL_LOG_DIR / "current" / COMPANION_MANIFEST_NAME
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
        "release_install": release_install,
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


def _path_type(path: Path) -> str:
    if path.is_symlink():
        try:
            path.resolve(strict=True)
        except OSError:
            return "broken_symlink"
        return "symlink"
    if path.is_dir():
        return "real_directory"
    if path.exists():
        return "file"
    return "missing"


def _recognize_legacy_skill(path: Path, skill_name: str) -> str:
    skill_md = path / "SKILL.md"
    if skill_md.exists():
        try:
            text = skill_md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "unknown_real_directory"
        if f"name: {skill_name}" in text or skill_name in text[:500]:
            return f"legacy_{skill_name.replace('-', '_')}_skill"
    return "unknown_real_directory"


def suite_migration_plan(
    *,
    targets: list[str] | None = None,
    agent_skill_dir: str | None = None,
) -> dict[str, Any]:
    resolved_targets = targets or ["codex"]
    release_root = INSTALL_LOG_DIR / "current"
    rollback_id = _utc_now().replace(":", "").replace("+", "Z")
    actions: list[dict[str, Any]] = []
    for target in resolved_targets:
        target_dir = _resolve_target_dir(target, agent_skill_dir)
        for spec in _suite_specs(include_optional=False):
            skill = str(spec["name"])
            link = _link_path(target_dir, skill)
            target_link = release_root / "skills" / skill
            current_type = _path_type(link)
            action = "no_op"
            safe_to_apply = True
            warnings: list[str] = []
            recognized_as = ""
            backup_path = ""
            if current_type == "missing":
                action = "create_symlink"
            elif current_type == "symlink":
                resolved = link.resolve()
                target_resolved = target_link.resolve() if target_link.exists() else target_link
                if resolved == target_resolved:
                    action = "no_op"
                else:
                    action = "replace_foreign_symlink"
                    warnings.append(f"foreign symlink points to {resolved}")
            elif current_type == "broken_symlink":
                action = "repair_symlink"
                warnings.append("broken symlink")
            elif current_type == "real_directory":
                recognized_as = _recognize_legacy_skill(link, skill)
                if _is_full_external_skill_package(link, skill):
                    action = "preserve_external_full_package"
                    recognized_as = "external_full_ppt_master_skill"
                    warnings.append("preserving full external PPT Master package")
                else:
                    action = "backup_and_replace_with_symlink"
                    backup_path = str(release_root / "migration" / "backups" / rollback_id / target / skill)
            else:
                action = "manual_action"
                safe_to_apply = False
                warnings.append(f"unsupported target path type: {current_type}")
            actions.append({
                "target": target,
                "skill": skill,
                "current_path": str(link),
                "current_type": current_type,
                "recognized_as": recognized_as,
                "target_link": str(target_link),
                "backup_path": backup_path,
                "action": action,
                "safe_to_apply": safe_to_apply,
                "warnings": warnings,
            })
    return {
        "schema_version": "deck_master_legacy_skill_migration_plan.v1",
        "target": ",".join(resolved_targets),
        "agent_skill_dir": str(agent_skill_dir or ""),
        "created_at": _utc_now(),
        "actions": actions,
        "rollback": {
            "rollback_id": rollback_id,
            "command": f"deck-master suite-migrate-legacy-skills --rollback --rollback-id {rollback_id}",
        },
    }


def _write_rollback_record(rollback_id: str, records: list[dict[str, Any]]) -> Path:
    path = INSTALL_LOG_DIR / "current" / "migration" / "rollback" / f"{rollback_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rollback_id": rollback_id, "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def suite_migration_apply(plan_file: str | Path) -> dict[str, Any]:
    plan_path = Path(plan_file).expanduser().resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    rollback_id = str((plan.get("rollback") or {}).get("rollback_id") or _utc_now().replace(":", ""))
    release_install = install_release_tree()
    if release_install["status"] != "installed":
        raise SkillInstallError("Release install blocked; legacy skill migration was not applied.")
    results: list[dict[str, Any]] = []
    rollback_records: list[dict[str, Any]] = []
    for action in plan.get("actions", []):
        if not action.get("safe_to_apply", False):
            results.append({**action, "status": "blocked"})
            continue
        current = Path(str(action["current_path"])).expanduser()
        target = Path(str(action["target_link"])).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        current.parent.mkdir(parents=True, exist_ok=True)
        operation = str(action.get("action") or "")
        if operation in {"no_op", "preserve_external_full_package"}:
            results.append({**action, "status": "no_op"})
            continue
        if current.is_dir() and not current.is_symlink():
            backup = Path(str(action.get("backup_path") or "")).expanduser()
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                shutil.rmtree(backup)
            shutil.copytree(current, backup)
            shutil.rmtree(current)
            rollback_records.append({"path": str(current), "backup_path": str(backup), "type": "real_directory"})
        elif current.is_symlink() or current.exists():
            previous = str(current.resolve()) if current.is_symlink() else ""
            current.unlink()
            rollback_records.append({"path": str(current), "previous_target": previous, "type": "symlink"})
        current.symlink_to(target)
        results.append({**action, "status": "applied"})
    rollback_path = _write_rollback_record(rollback_id, rollback_records)
    return {
        "schema_version": "deck_master_legacy_skill_migration_apply.v1",
        "status": "applied" if all(item.get("status") != "blocked" for item in results) else "blocked",
        "plan_file": str(plan_path),
        "rollback_id": rollback_id,
        "rollback_record": str(rollback_path),
        "release_install": release_install,
        "results": results,
    }


def suite_migration_rollback(rollback_id: str) -> dict[str, Any]:
    record_path = INSTALL_LOG_DIR / "current" / "migration" / "rollback" / f"{rollback_id}.json"
    if not record_path.exists():
        raise SkillInstallError(f"Rollback record not found: {record_path}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for item in record.get("records", []):
        path = Path(str(item["path"])).expanduser()
        if path.is_symlink() or path.exists():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        if item.get("type") == "real_directory":
            backup = Path(str(item["backup_path"])).expanduser()
            if backup.exists():
                shutil.copytree(backup, path)
                results.append({"path": str(path), "status": "restored"})
            else:
                results.append({"path": str(path), "status": "missing_backup"})
        elif item.get("type") == "symlink" and item.get("previous_target"):
            path.symlink_to(Path(str(item["previous_target"])).expanduser())
            results.append({"path": str(path), "status": "symlink_restored"})
    return {
        "schema_version": "deck_master_legacy_skill_migration_rollback.v1",
        "status": "rolled_back",
        "rollback_id": rollback_id,
        "results": results,
    }


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
