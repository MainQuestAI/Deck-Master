"""Deck Master skill installer.

Manages symlinks from external Agent skill directories to the
installed Deck Master skill package under ``~/.deck-master/current``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_NAME = "deck-master"

SUPPORTED_TARGETS = {"codex", "claude-code", "hermes", "custom"}

DEFAULT_AGENT_SKILL_DIRS = {
    "codex": "~/.codex/skills",
    "claude-code": "~/.claude/skills",
    "hermes": "~/.hermes/skills",
}

INSTALL_LOG_DIR = Path.home() / ".deck-master"
INSTALL_LOG_NAME = "install_log.jsonl"
INSTALLED_SKILL_DIR = INSTALL_LOG_DIR / "current" / "skills" / SKILL_NAME


class SkillInstallError(Exception):
    """Raised when a skill installation operation fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_skill_dir() -> Path:
    """Return the absolute path to ``skills/deck-master/`` in this repo."""
    return Path(__file__).resolve().parents[2] / "skills" / SKILL_NAME


def _resolve_source_dir(source_skill_dir: str | None = None) -> Path:
    if source_skill_dir:
        return Path(source_skill_dir).expanduser()
    if INSTALLED_SKILL_DIR.exists():
        return INSTALLED_SKILL_DIR
    return _repo_skill_dir()


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


def _link_path(target_dir: Path) -> Path:
    return target_dir / SKILL_NAME


def _append_install_log(action: str, **fields: Any) -> None:
    INSTALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": _utc_now(), "action": action, **fields}
    log_path = INSTALL_LOG_DIR / INSTALL_LOG_NAME
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _skill_package_error(source: Path) -> str | None:
    skill_md = source / "SKILL.md"
    if not source.exists():
        return (
            f"Deck Master skill source not found: {source}. "
            "Run setup first or pass --source-skill-dir explicitly."
        )
    if not source.is_dir():
        return f"Deck Master skill source is not a directory: {source}."
    if not skill_md.exists():
        return f"SKILL.md not found in {source}."

    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return f"SKILL.md at {skill_md} is missing YAML frontmatter."
    parts = text.split("---", 2)
    if len(parts) < 3:
        return f"SKILL.md at {skill_md} has incomplete YAML frontmatter."
    frontmatter = parts[1]
    if "name: deck-master" not in frontmatter:
        return f"SKILL.md at {skill_md} is missing 'name: deck-master'."
    if "description:" not in frontmatter:
        return f"SKILL.md at {skill_md} is missing 'description'."
    return None


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
    if target not in SUPPORTED_TARGETS:
        raise SkillInstallError(
            f"Unsupported target '{target}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_TARGETS))}"
        )

    source = _resolve_source_dir(source_skill_dir)
    canonical_source = source.resolve()
    package_error = _skill_package_error(source)
    if package_error:
        raise SkillInstallError(package_error)

    target_dir = _resolve_target_dir(target, agent_skill_dir)
    link = _link_path(target_dir)

    # Idempotent: already a symlink pointing here.
    if link.is_symlink():
        existing_target = link.resolve()
        if existing_target == canonical_source:
            _append_install_log(
                "install_skill",
                target=target,
                status="already_installed",
                link=str(link),
                source=str(source),
            )
            return {
                "status": "already_installed",
                "link": str(link),
                "source": str(source),
                "target_dir": str(target_dir),
            }
        if not force:
            raise SkillInstallError(
                f"Symlink already exists at {link} pointing to {existing_target}. "
                "Use --force to replace it."
            )
        # --force: replace symlink.
        link.unlink()

    elif link.exists():
        # Real file or directory — refuse unless --force and it is a file.
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
        status="installed",
        link=str(link),
        source=str(source),
    )

    return {
        "status": "installed",
        "link": str(link),
        "source": str(source),
        "target_dir": str(target_dir),
    }


def validate_skill(
    target: str,
    agent_skill_dir: str | None = None,
    source_skill_dir: str | None = None,
) -> dict[str, Any]:
    """Check whether the skill symlink is valid and points to the installed skill.

    Returns a result dict with ``valid``, ``link_path`` and diagnostic details.
    """
    if target not in SUPPORTED_TARGETS:
        return {
            "valid": False,
            "error": (
                f"Unsupported target '{target}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_TARGETS))}"
            ),
        }

    target_dir = _resolve_target_dir(target, agent_skill_dir)
    link = _link_path(target_dir)
    source = _resolve_source_dir(source_skill_dir)
    canonical_source = source.resolve() if source.exists() else source

    if not link.exists() and not link.is_symlink():
        return {
            "valid": False,
            "link": str(link),
            "error": "Symlink does not exist. Run install-skill first.",
        }

    if not link.is_symlink():
        return {
            "valid": False,
            "link": str(link),
            "error": "Path exists but is not a symlink.",
        }

    try:
        resolved = link.resolve()
    except OSError as exc:
        return {
            "valid": False,
            "link": str(link),
            "error": f"Broken symlink: {exc}",
        }

    package_error = _skill_package_error(resolved)
    skill_md_exists = (resolved / "SKILL.md").exists()

    valid = resolved == canonical_source and package_error is None
    error = None
    if resolved != canonical_source:
        error = f"Symlink points to {resolved}, expected {source}."
    elif package_error:
        error = package_error

    result: dict[str, Any] = {
        "valid": valid,
        "link": str(link),
        "resolved": str(resolved),
        "expected_source": str(source),
        "skill_md_exists": skill_md_exists,
    }
    if error:
        result["error"] = error

    _append_install_log(
        "validate_skill",
        target=target,
        valid=valid,
        link=str(link),
    )

    return result


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
