from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from validators.companion_tools import validate_render_result
except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
    from scripts.validators.companion_tools import validate_render_result

try:
    from runtime.render_handoff import render_handoff_contract_ready
except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
    from scripts.runtime.render_handoff import render_handoff_contract_ready

SCHEMA_VERSION = "deck_builder_backend_status.v1"
BACKEND_BINDINGS_SCHEMA_VERSION = "deck_backend_bindings.v1"
BACKEND_NAME = "ppt-master"
PRODUCTION_RUN_MODES = {"production", "benchmark"}
REQUIRED_BACKEND_MANIFEST = "deck_master_backend_manifest.v1"
REQUIRED_CONTRACT = "deck_render_result.v2"
REQUIRED_PACKAGE_DIRS = ("references", "scripts", "templates", "workflows")
REQUIRED_PRODUCTION_OPERATIONS = {"render", "writeback", "smoke"}
REQUIRED_MANIFEST_KEYS = ("schema_version", "name", "contracts", "operations", "runtime")
REQUIRED_RUNTIME_KEYS = ("smoke_command", "operations")
REQUIRED_KEY_SCRIPTS = ("project_manager.py", "finalize_svg.py", "svg_to_pptx.py")
BACKEND_BINDINGS_NAME = "backend_bindings.json"
DEPENDENCY_KIND_EXTERNAL_REPO = "external_repo"
DEPENDENCY_KIND_GENERATION_BRIDGE = "generation_bridge"
RUNTIME_READY_ENV = "DECK_MASTER_PPT_MASTER_RUNTIME_WIRED"
GENERATION_BRIDGE_NAME = "ppt-deck-pro-max"
GENERATION_BRIDGE_REPO = "https://github.com/MainQuestAI/PPT-Deck-Pro-Max.git"
GENERATION_BRIDGE_REPO_PATH_ENV = "DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE"
GENERATION_BRIDGE_BRANCH = "codex/deck-master-bridge"
GENERATION_BRIDGE_SHA = "9444d88f573c3afa567bfb1763041325ef765313"
GENERATION_BRIDGE_VERIFIED_AT = "2026-07-03T00:00:00+08:00"
GENERATION_BRIDGE_CAPABILITIES = (
    "dispatch_import",
    "generation_result_export",
    "result_import_contract",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def production_requires_builder_backend(run_mode: str | None) -> bool:
    return str(run_mode or "production").strip().lower() in PRODUCTION_RUN_MODES


def backend_render_runtime_ready() -> bool:
    flag = os.environ.get(RUNTIME_READY_ENV, "").strip().lower()
    if flag in {"0", "false", "off", "no", "disabled"}:
        return False
    if flag in {"1", "true", "on", "yes", "enabled"}:
        return True
    return render_handoff_contract_ready()


def backend_bindings_path() -> Path:
    return Path.home() / ".deck-master" / BACKEND_BINDINGS_NAME


def _safe_json_read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": BACKEND_BINDINGS_SCHEMA_VERSION, "bindings": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": BACKEND_BINDINGS_SCHEMA_VERSION, "bindings": [], "_invalid": "backend binding file is invalid"}
    if not isinstance(payload, dict):
        return {"schema_version": BACKEND_BINDINGS_SCHEMA_VERSION, "bindings": [], "_invalid": "backend binding file is not an object"}
    payload.setdefault("schema_version", BACKEND_BINDINGS_SCHEMA_VERSION)
    bindings = payload.get("bindings")
    if not isinstance(bindings, list):
        payload["bindings"] = []
    return payload


def _safe_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_backend_bindings(path: Path | None = None) -> dict[str, Any]:
    return _safe_json_read(path or backend_bindings_path())


def _write_backend_bindings(payload: dict[str, Any], path: Path | None = None) -> None:
    target = (path or backend_bindings_path()).expanduser()
    normalized = dict(payload)
    normalized["schema_version"] = BACKEND_BINDINGS_SCHEMA_VERSION
    normalized.setdefault("updated_at", _utc_now())
    _safe_json_write(target, normalized)


def list_backend_bindings() -> list[dict[str, Any]]:
    payload = _read_backend_bindings()
    bindings = payload.get("bindings")
    if not isinstance(bindings, list):
        return []
    return [dict(item) for item in bindings if isinstance(item, dict)]


def _git_command(path: Path, args: list[str]) -> str | None:
    try:
        output = subprocess.run(
            ["git", *args],
            cwd=str(path),
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if output.returncode != 0:
        return None
    return output.stdout.strip()


def _repo_label_from_remote(remote: str | None) -> str:
    if not remote:
        return ""
    text = remote.strip().strip("\n\r")
    if not text:
        return ""
    if text.endswith(".git"):
        text = text[:-4]
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("@").pop()
    parts = text.split(":", 1)
    if len(parts) == 2 and "/" not in parts[0]:
        text = parts[1]
    segments = [segment for segment in text.split("/") if segment]
    if len(segments) >= 2:
        return "/".join(segments[-2:])
    return segments[-1] if segments else ""


def _read_git_metadata(path: Path) -> dict[str, Any]:
    remote = _git_command(path, ["config", "--get", "remote.origin.url"]) or ""
    branch = _git_command(path, ["rev-parse", "--abbrev-ref", "HEAD"]) or ""
    sha = _git_command(path, ["rev-parse", "HEAD"]) or ""
    status = _git_command(path, ["status", "--short", "--untracked-files=no"]) or ""
    return {
        "repo_label": _repo_label_from_remote(remote),
        "git_remote": remote,
        "git_branch": branch,
        "git_sha": sha,
        "worktree_dirty": bool(status.strip()),
    }


def _short_sha(value: str | None) -> str:
    sha = (value or "").strip()
    return sha[:8] if len(sha) > 8 else sha


def _normalize_backend_record(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(raw.get("name") or "").strip(),
        "repo_path": str(raw.get("repo_path") or "").strip(),
        "skill_path": str(raw.get("skill_path") or "").strip(),
        "git_remote": str(raw.get("git_remote") or "").strip(),
        "git_branch": str(raw.get("git_branch") or "").strip(),
        "git_sha": str(raw.get("git_sha") or "").strip(),
        "short_sha": _short_sha(str(raw.get("git_sha") or "")),
        "worktree_dirty": bool(raw.get("worktree_dirty")),
        "verified": bool(raw.get("verified")),
        "verified_at": str(raw.get("verified_at") or "").strip(),
        "validated_capabilities": list(raw.get("validated_capabilities") or []),
        "repo_label": str(raw.get("repo_label") or "").strip(),
        "dependency_kind": str(raw.get("dependency_kind") or DEPENDENCY_KIND_EXTERNAL_REPO).strip() or DEPENDENCY_KIND_EXTERNAL_REPO,
    }


def _merge_backend_record(
    current: dict[str, Any],
    repo_path: Path,
    skill_path: Path,
    *,
    verified: bool,
    verified_at: str,
    validated_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    metadata = _read_git_metadata(repo_path)
    result = _normalize_backend_record(current)
    result.update(
        {
            "name": BACKEND_NAME,
            "dependency_kind": DEPENDENCY_KIND_EXTERNAL_REPO,
            "repo_path": str(repo_path),
            "skill_path": str(skill_path),
            "repo_label": metadata.get("repo_label") or _repo_label_from_remote(""),
            "git_remote": metadata.get("git_remote") or "",
            "git_branch": metadata.get("git_branch") or "",
            "git_sha": metadata.get("git_sha") or "",
            "short_sha": _short_sha(metadata.get("git_sha")),
            "worktree_dirty": bool(metadata.get("worktree_dirty")),
            "verified": bool(verified),
            "verified_at": str(verified_at),
            "validated_capabilities": list(validated_capabilities or []),
        }
    )
    return result


def _set_backend_binding(record: dict[str, Any]) -> dict[str, Any]:
    payload = _read_backend_bindings()
    bindings = payload.get("bindings")
    if not isinstance(bindings, list):
        bindings = []
    updated: list[dict[str, Any]] = []
    replaced = False
    for item in [item for item in bindings if isinstance(item, dict)]:
        normalized = _normalize_backend_record(item)
        if normalized.get("name") == BACKEND_NAME:
            updated.append(record)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(record)
    payload["bindings"] = updated
    _write_backend_bindings(payload)
    return record


def _find_backend_binding(name: str) -> dict[str, Any] | None:
    if name != BACKEND_NAME:
        return None
    for item in list_backend_bindings():
        if item.get("name") == name:
            return _normalize_backend_record(item)
    return None


def bind_backend_dependency(repo_path: str, name: str = BACKEND_NAME) -> dict[str, Any]:
    if name != BACKEND_NAME:
        raise ValueError(f"Unknown backend dependency: {name}")
    repository = Path(repo_path).expanduser().resolve()
    if not repository.is_dir():
        raise ValueError(f"Backend repository not found: {repository}")
    if _git_command(repository, ["rev-parse", "--is-inside-work-tree"]) != "true":
        raise ValueError(f"Backend repository is not a git worktree: {repository}")
    skill_path = repository / "skills" / name
    if not skill_path.exists():
        raise ValueError(f"Backend skill path does not exist: {skill_path}")
    package = inspect_builder_backend_package(skill_path)
    metadata = _read_git_metadata(repository)
    record = _merge_backend_record(
        _find_backend_binding(name) or {},
        repository,
        skill_path,
        verified=bool(package.get("production_capable")),
        verified_at=_utc_now(),
        validated_capabilities=list(package.get("operations") or []),
    )
    record["repo_label"] = metadata.get("repo_label")
    record["git_branch"] = metadata.get("git_branch")
    record["git_sha"] = metadata.get("git_sha")
    record["git_remote"] = metadata.get("git_remote")
    record["short_sha"] = _short_sha(metadata.get("git_sha"))
    record["worktree_dirty"] = bool(metadata.get("worktree_dirty"))
    _set_backend_binding(record)
    return record


def verify_backend_dependency(name: str = BACKEND_NAME) -> dict[str, Any]:
    if name != BACKEND_NAME:
        raise ValueError(f"Unknown backend dependency: {name}")
    binding = _find_backend_binding(name)
    if not binding:
        raise ValueError(f"No backend binding for {name}")
    repo_path = Path(binding.get("repo_path") or "") if binding.get("repo_path") else None
    if not repo_path or not repo_path.exists():
        raise ValueError("Bound backend repository no longer exists.")
    skill_path = Path(binding.get("skill_path") or "")
    if not skill_path or not skill_path.exists():
        skill_path = repo_path / "skills" / name
    package = inspect_builder_backend_package(skill_path)
    metadata = _read_git_metadata(repo_path)
    record = _merge_backend_record(
        binding,
        repo_path,
        skill_path,
        verified=bool(package.get("production_capable")),
        verified_at=_utc_now(),
        validated_capabilities=list(package.get("operations") or []),
    )
    record["repo_label"] = metadata.get("repo_label")
    record["git_branch"] = metadata.get("git_branch")
    record["git_sha"] = metadata.get("git_sha")
    record["git_remote"] = metadata.get("git_remote")
    record["short_sha"] = _short_sha(metadata.get("git_sha"))
    record["worktree_dirty"] = bool(metadata.get("worktree_dirty"))
    _set_backend_binding(record)
    return record


def unbind_backend_dependency(name: str = BACKEND_NAME) -> dict[str, Any]:
    if name != BACKEND_NAME:
        raise ValueError(f"Unknown backend dependency: {name}")
    payload = _read_backend_bindings()
    bindings = payload.get("bindings")
    if not isinstance(bindings, list):
        bindings = []
    remaining = [item for item in bindings if isinstance(item, dict) and str(item.get("name") or "") != name]
    if len(remaining) == len([item for item in bindings if isinstance(item, dict)]):
        return {"status": "not_bound", "name": name, "message": f"No binding found for {name}"}
    payload["bindings"] = remaining
    _write_backend_bindings(payload)
    return {"status": "unbound", "name": name}


def _binding_status_for_name(name: str, *, render_runtime_ready: bool) -> dict[str, Any]:
    if name != BACKEND_NAME:
        return {
            "name": name,
            "dependency_kind": DEPENDENCY_KIND_EXTERNAL_REPO,
            "binding_status": "unbound",
            "repo_label": "",
            "repo_path": "",
            "skill_path": "",
            "git_remote": "",
            "git_sha": "",
            "short_sha": "",
            "git_branch": "",
            "worktree_dirty": False,
            "verified": False,
            "verified_at": "",
            "source": "",
            "validated_capabilities": [],
            "summary": "Dependency is not supported by this build.",
        }

    binding = _find_backend_binding(name)
    if not binding:
        return {
            "name": name,
            "dependency_kind": DEPENDENCY_KIND_EXTERNAL_REPO,
            "binding_status": "unbound",
            "repo_label": "",
            "repo_path": "",
            "skill_path": "",
            "git_remote": "",
            "git_sha": "",
            "short_sha": "",
            "git_branch": "",
            "worktree_dirty": False,
            "verified": False,
            "verified_at": "",
            "source": "",
            "validated_capabilities": [],
            "summary": "No formal backend binding found for PPT Master.",
        }

    repo_path = Path(binding.get("repo_path") or "")
    skill_path = Path(binding.get("skill_path") or "")
    package = inspect_builder_backend_package(skill_path) if skill_path else {}
    capabilities = binding.get("validated_capabilities")
    if not isinstance(capabilities, list):
        capabilities = list(package.get("operations") or [])

    verified = bool(binding.get("verified"))
    production_capable = bool(package.get("production_capable"))
    if not verified:
        binding_status = "bound_blocked"
        summary = "PPT Master 已绑定，但尚未通过 verify。"
    elif not production_capable:
        binding_status = "bound_blocked"
        summary = "PPT Master 已绑定，但当前绑定路径未通过生产认证。"
    elif not render_runtime_ready:
        binding_status = "bound_verified_runtime_blocked"
        summary = "PPT Master 已绑定且已认证，但运行时 wiring 未开启。"
    else:
        binding_status = "bound_verified"
        summary = "PPT Master 已绑定且已完成验证。"

    return {
        "name": name,
        "dependency_kind": DEPENDENCY_KIND_EXTERNAL_REPO,
        "binding_status": binding_status,
        "repo_label": str(binding.get("repo_label") or ""),
        "repo_path": str(repo_path),
        "skill_path": str(skill_path),
        "git_remote": str(binding.get("git_remote") or ""),
        "git_sha": str(binding.get("git_sha") or ""),
        "short_sha": _short_sha(binding.get("git_sha") if isinstance(binding.get("git_sha"), str) else None),
        "git_branch": str(binding.get("git_branch") or ""),
        "worktree_dirty": bool(binding.get("worktree_dirty")),
        "verified": bool(binding.get("verified")),
        "verified_at": str(binding.get("verified_at") or ""),
        "validated_capabilities": list(capabilities or []),
        "source": str(binding.get("git_remote") or binding.get("repo_label") or binding.get("repo_path") or ""),
        "summary": summary,
    }


def _generation_bridge_status() -> dict[str, Any]:
    configured_path = os.environ.get(GENERATION_BRIDGE_REPO_PATH_ENV, "").strip()
    base = {
        "name": GENERATION_BRIDGE_NAME,
        "dependency_kind": DEPENDENCY_KIND_GENERATION_BRIDGE,
        "repo": GENERATION_BRIDGE_REPO,
        "repo_label": _repo_label_from_remote(GENERATION_BRIDGE_REPO),
        "repo_path": configured_path,
        "skill_path": "",
        "git_remote": "",
        "git_sha": "",
        "short_sha": "",
        "git_branch": "",
        "worktree_dirty": False,
        "verified": False,
        "verified_at": "",
        "validated_capabilities": [],
        "source": GENERATION_BRIDGE_REPO,
    }
    if not configured_path:
        return {
            **base,
            "binding_status": "not_configured",
            "summary": (
                "PPT Deck Pro Max generation bridge is not configured. "
                f"Set {GENERATION_BRIDGE_REPO_PATH_ENV} to a local open-source checkout for production generation."
            ),
        }

    repo_path = Path(configured_path).expanduser()
    if not repo_path.exists() or _git_command(repo_path, ["rev-parse", "--is-inside-work-tree"]) != "true":
        return {
            **base,
            "binding_status": "invalid",
            "summary": "Configured PPT Deck Pro Max generation bridge path is not a git worktree.",
        }

    metadata = _read_git_metadata(repo_path)
    current_sha = str(metadata.get("git_sha") or "")
    verified = bool(current_sha and current_sha == GENERATION_BRIDGE_SHA)
    status = "bound_verified" if verified else "configured_unverified"
    return {
        **base,
        "binding_status": status,
        "repo_path": str(repo_path.resolve()),
        "git_remote": str(metadata.get("git_remote") or ""),
        "git_sha": current_sha,
        "short_sha": _short_sha(current_sha),
        "git_branch": str(metadata.get("git_branch") or ""),
        "worktree_dirty": bool(metadata.get("worktree_dirty")),
        "verified": verified,
        "verified_at": GENERATION_BRIDGE_VERIFIED_AT if verified else "",
        "validated_capabilities": list(GENERATION_BRIDGE_CAPABILITIES) if verified else [],
        "summary": (
            "PPT Deck Pro Max generation bridge is pinned and verified."
            if verified
            else "PPT Deck Pro Max generation bridge is configured but not pinned to the expected release SHA."
        ),
    }


def backend_dependency_statuses(*, render_runtime_ready: bool | None = None) -> list[dict[str, Any]]:
    return [
        _binding_status_for_name(BACKEND_NAME, render_runtime_ready=bool(backend_render_runtime_ready() if render_runtime_ready is None else render_runtime_ready)),
    ]


def external_dependency_statuses(*, render_runtime_ready: bool | None = None) -> list[dict[str, Any]]:
    return backend_dependency_statuses(render_runtime_ready=render_runtime_ready)


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get("DECK_MASTER_PPT_MASTER_BACKEND")
    if env_path:
        paths.append(Path(env_path).expanduser())
    home = Path.home()
    paths.extend(
        [
            home / ".codex" / "skills" / BACKEND_NAME,
            home / ".deck-master" / "current" / "skills" / BACKEND_NAME,
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _frontmatter_ok(path: Path) -> bool:
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        return False
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---\n"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    frontmatter = parts[1]
    return f"name: {BACKEND_NAME}" in frontmatter and "description:" in frontmatter


def _nonempty_dir(path: Path) -> bool:
    try:
        return path.is_dir() and any(path.iterdir())
    except OSError:
        return False


def _load_capability(path: Path) -> dict[str, Any]:
    for name in ("deck-master-backend.json", "capability.json"):
        capability_path = path / name
        if not capability_path.exists():
            continue
        try:
            payload = json.loads(capability_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"_parse_error": str(capability_path)}
        return payload if isinstance(payload, dict) else {}
    return {}


def _operations(capability: dict[str, Any]) -> set[str]:
    raw: list[Any] = []
    runtime = capability.get("runtime") if isinstance(capability.get("runtime"), dict) else {}
    if isinstance(runtime.get("operations"), list):
        raw.extend(runtime.get("operations"))
    if isinstance(capability.get("operations"), list):
        raw.extend(capability.get("operations"))

    operations: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        for token in str(item or "").strip().lower().replace("_", "-").split():
            operations.add(token)
    return operations


def _has_required_key_scripts(root: Path) -> tuple[dict[str, bool], list[str]]:
    checks: dict[str, bool] = {}
    missing: list[str] = []
    for name in REQUIRED_KEY_SCRIPTS:
        exists = (root / "scripts" / name).exists()
        checks[name] = exists
        if not exists:
            missing.append(name)
    return checks, missing


def _smoke_command_path(root: Path, manifest: dict[str, Any]) -> tuple[str | None, list[str]]:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        return None, ["runtime block missing"]
    value = runtime.get("smoke_command")
    if not isinstance(value, str) or not value.strip():
        return None, ["runtime.smoke_command missing"]

    script: str | None = None
    try:
        tokens = shlex.split(value)
    except ValueError:
        tokens = [part for part in value.split() if part]
    for token in tokens:
        if token.lower().endswith(".py"):
            script = token
            break
    if not script:
        return None, ["runtime.smoke_command does not include a .py script"]

    candidate = (root / script).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, [f"runtime.smoke_command script escapes backend root: {script}"]
    if not candidate.exists():
        return None, [f"runtime.smoke_command script missing: {script}"]
    return str(candidate), []


def _run_smoke_check(root: Path, smoke_command: str | None) -> tuple[dict[str, Any] | None, list[str]]:
    if not smoke_command:
        return None, ["backend smoke command could not be resolved"]
    with tempfile.TemporaryDirectory(prefix="deck_master_backend_smoke_") as temp_dir:
        try:
            completed = subprocess.run(
                ["python3", smoke_command, "--output-dir", temp_dir],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            return None, ["backend smoke command timed out"]
        if completed.returncode != 0:
            return None, [f"backend smoke command failed with exit {completed.returncode}"]
        stdout = completed.stdout.strip()
        if not stdout:
            return None, ["backend smoke command produced no output"]
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return None, ["backend smoke command did not return JSON output"]
        if not isinstance(payload, dict):
            return None, ["backend smoke command returned a non-object payload"]
        if str(payload.get("status") or "").strip().lower() != "pass":
            return payload, ["backend smoke command did not report pass status"]
        contract = payload.get("contract_smoke_output")
        if not isinstance(contract, dict):
            return payload, ["backend smoke command did not return contract_smoke_output"]
        render_result_path = contract.get("render_result_path")
        fake_pptx_path = contract.get("fake_pptx_path")
        if not isinstance(render_result_path, str) or not render_result_path.strip():
            return payload, ["backend smoke command did not return render_result_path"]
        if not isinstance(fake_pptx_path, str) or not fake_pptx_path.strip():
            return payload, ["backend smoke command did not return fake_pptx_path"]
        render_result = Path(render_result_path).expanduser().resolve()
        fake_pptx = Path(fake_pptx_path).expanduser().resolve()
        temp_root = Path(temp_dir).resolve()
        for candidate, label in ((render_result, "render_result_path"), (fake_pptx, "fake_pptx_path")):
            try:
                candidate.relative_to(temp_root)
            except ValueError:
                return payload, [f"backend smoke {label} escapes smoke output dir"]
            if not candidate.exists():
                return payload, [f"backend smoke {label} is missing"]
        try:
            render_payload = json.loads(render_result.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return payload, ["backend smoke render_result is unreadable"]
        validation = validate_render_result(render_payload)
        if not validation.get("valid"):
            return payload, ["backend smoke render_result failed validation: " + "; ".join(validation.get("errors", []))]
        return payload, []


def inspect_builder_backend_package(path: str | Path) -> dict[str, Any]:
    root = Path(path).expanduser()
    resolved = root.resolve() if root.exists() else root
    result: dict[str, Any] = {
        "path": str(root),
        "resolved": str(resolved),
        "exists": root.exists(),
        "is_symlink": root.is_symlink(),
        "frontmatter_ok": False,
        "required_dirs": {},
        "capability_manifest": False,
        "capability_path": "",
        "capability_schema": "",
        "manifest_contract": [],
        "operations": [],
        "key_scripts": {},
        "smoke_check": {},
        "full_package": False,
        "production_capable": False,
        "reasons": [],
        "smoke_command": None,
    }
    if not root.exists() or not root.is_dir():
        result["reasons"].append("backend package is missing")
        return result

    result["frontmatter_ok"] = _frontmatter_ok(root)
    if not result["frontmatter_ok"]:
        result["reasons"].append("SKILL.md frontmatter is missing name/description")

    dir_status = {name: _nonempty_dir(root / name) for name in REQUIRED_PACKAGE_DIRS}
    result["required_dirs"] = dir_status
    missing_dirs = [name for name, ready in dir_status.items() if not ready]
    if missing_dirs:
        result["reasons"].append("backend package is missing non-empty dirs: " + ", ".join(missing_dirs))

    capability = _load_capability(root)
    if capability and "_parse_error" not in capability:
        if (root / "deck-master-backend.json").exists():
            result["capability_path"] = str(root / "deck-master-backend.json")
        elif (root / "capability.json").exists():
            result["capability_path"] = str(root / "capability.json")
    result["capability_manifest"] = bool(capability) and "_parse_error" not in capability
    result["capability_schema"] = str(capability.get("schema_version") or "")
    raw_contracts = capability.get("contracts")
    contracts = raw_contracts if isinstance(raw_contracts, dict) else None
    result["manifest_contract"] = list((contracts.get("outputs") or [])) if isinstance(contracts, dict) else []
    operations = _operations(capability)
    result["operations"] = sorted(operations)
    result["full_package"] = bool(result["frontmatter_ok"] and not missing_dirs)

    if not result["capability_manifest"]:
        result["reasons"].append("backend capability manifest is missing or invalid")
    missing_manifest_keys = [name for name in REQUIRED_MANIFEST_KEYS if name not in capability]
    if capability and "_parse_error" not in capability and missing_manifest_keys:
        result["reasons"].append("backend manifest missing required fields: " + ", ".join(missing_manifest_keys))
    if result["capability_schema"] != REQUIRED_BACKEND_MANIFEST:
        result["reasons"].append("backend manifest schema version is invalid: " + result["capability_schema"])
    if capability.get("name") != BACKEND_NAME:
        result["reasons"].append("backend manifest name is invalid")
    if isinstance(contracts, dict):
        outputs = contracts.get("outputs")
        if not isinstance(outputs, list) or REQUIRED_CONTRACT not in outputs:
            result["reasons"].append("backend manifest does not declare required output: deck_render_result.v2")
        else:
            result["manifest_contract"] = outputs
    else:
        result["reasons"].append("backend manifest contracts block is invalid")
    key_scripts, missing_scripts = _has_required_key_scripts(root)
    result["key_scripts"] = key_scripts
    if missing_scripts:
        result["reasons"].append("backend key script missing: " + ", ".join(missing_scripts))
    runtime = capability.get("runtime", {})
    missing_runtime_keys: list[str] = []
    if not isinstance(runtime, dict):
        result["reasons"].append("backend manifest runtime block is invalid")
    else:
        missing_runtime_keys = [name for name in REQUIRED_RUNTIME_KEYS if name not in runtime]
        if missing_runtime_keys:
            result["reasons"].append("backend manifest.runtime missing: " + ", ".join(missing_runtime_keys))
    smoke_command, smoke_errors = _smoke_command_path(root, capability)
    if smoke_errors:
        result["reasons"].extend(smoke_errors)
    result["smoke_command"] = smoke_command
    smoke_check, smoke_check_errors = _run_smoke_check(root, smoke_command)
    if smoke_check_errors:
        result["reasons"].extend(smoke_check_errors)
    result["smoke_check"] = smoke_check or {}

    missing_ops = sorted(REQUIRED_PRODUCTION_OPERATIONS - operations)
    if missing_ops:
        result["reasons"].append("backend capability manifest lacks operations: " + ", ".join(missing_ops))

    result["production_capable"] = bool(
        result["full_package"]
        and result["capability_manifest"]
        and not missing_ops
        and result["capability_schema"] == REQUIRED_BACKEND_MANIFEST
        and not missing_scripts
        and not smoke_errors
        and not smoke_check_errors
        and not missing_runtime_keys
        and not result["reasons"]
        and result["capability_path"]
    )
    return result


def builder_backend_status() -> dict[str, Any]:
    render_runtime_ready = backend_render_runtime_ready()
    dependency_status = _binding_status_for_name(
        BACKEND_NAME,
        render_runtime_ready=render_runtime_ready,
    )
    candidates = [inspect_builder_backend_package(path) for path in _candidate_paths()]
    bound = _find_backend_binding(BACKEND_NAME)
    selected = candidates[0] if candidates else {}
    if bound:
        bound_path = Path(str(bound.get("skill_path") or "")).expanduser() if bound.get("skill_path") else None
        if bound_path is not None and bound_path.exists():
            selected = inspect_builder_backend_package(bound_path)
    binding_verified = dependency_status.get("binding_status") in {"bound_verified", "bound_verified_runtime_blocked"}
    runtime_ready = bool(render_runtime_ready)
    if dependency_status.get("binding_status") == "bound_verified_runtime_blocked":
        runtime_ready = False
    render_capable = dependency_status.get("binding_status") == "bound_verified"
    backend_type = "missing"
    if render_capable:
        backend_type = "production_backend"
    elif dependency_status.get("binding_status") == "bound_blocked":
        backend_type = "bound_but_not_verified"
    elif selected.get("full_package"):
        backend_type = "full_package_not_certified"
    elif selected.get("exists"):
        backend_type = "adapter_only"

    reasons = [
        str(item)
        for item in selected.get("reasons", [])
        + [dependency_status.get("summary", "")]
        if item
    ]
    blocking_reason = (
        "PPT Master production backend is ready."
        if render_capable
        else "PPT Master production backend is not ready: " + "; ".join(reasons)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "backend_name": BACKEND_NAME,
        "status": "ready" if render_capable else "blocked",
        "backend_type": backend_type,
        "binding_verified": binding_verified,
        "runtime_ready": runtime_ready,
        "render_capable": render_capable,
        "production_capable": render_capable,
        "dependency_status": dependency_status,
        "selected": selected,
        "candidates": candidates,
        "blocking_reason": blocking_reason,
    }
