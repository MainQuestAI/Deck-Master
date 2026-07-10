"""Canonical read-only PPT Library readiness inspection."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "deck_master_library_status.v2"
CANONICAL_ROLES = {
    "opener",
    "problem",
    "solution",
    "architecture",
    "case",
    "roi",
    "cta",
    "appendix",
}


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _flatten(payload: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}

    def visit(node: Mapping[str, Any]) -> None:
        for key, value in node.items():
            normalized = _normalized_key(key)
            if normalized and normalized not in values:
                values[normalized] = value
            if isinstance(value, Mapping):
                visit(value)

    visit(payload)
    return values


def _first(values: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in values:
            return values[key]
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value > 0
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "ready", "available", "healthy", "pass", "passed"}:
        return True
    if text in {"false", "no", "blocked", "missing", "unavailable", "failed", "error"}:
        return False
    return None


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _contract_ready(repo_root: Path) -> bool:
    capability = _read_json_object(
        repo_root / "product_capabilities" / "ppt-library" / "capability.json"
    )
    selection = _read_json_object(
        repo_root / "docs" / "contracts" / "ppt-library-selection.v2.schema.json"
    )
    bridge_plan = _read_json_object(
        repo_root / "docs" / "contracts" / "ppt-library-bridge-plan.v1.schema.json"
    )
    if not capability or capability.get("name") != "ppt-library":
        return False
    operations = (capability.get("runtime") or {}).get("operations")
    if not isinstance(operations, list) or "status" not in operations:
        return False
    selection_version = ((selection or {}).get("properties") or {}).get("schema_version")
    bridge_version = ((bridge_plan or {}).get("properties") or {}).get("schema_version")
    return bool(
        isinstance(selection_version, dict)
        and selection_version.get("const") == "deck_master_ppt_library_selection.v2"
        and isinstance(bridge_version, dict)
        and bridge_version.get("const") == "deck_master_ppt_library_bridge_plan.v1"
        and (repo_root / "scripts" / "tools" / "ppt_library_client.py").is_file()
    )


def _role_selection_ready(payload: Mapping[str, Any], values: Mapping[str, Any]) -> bool:
    explicit = _as_bool(
        _first(values, "role_selection_ready", "role_search_ready", "annotation_ready")
    )
    if explicit is not None:
        return explicit

    role_counts = _first(values, "role_counts", "roles", "role_coverage")
    if not isinstance(role_counts, Mapping):
        return False
    normalized_counts = {
        _normalized_key(role): _as_number(count)
        for role, count in role_counts.items()
    }
    return all((normalized_counts.get(role) or 0) > 0 for role in CANONICAL_ROLES)


def _business_ranking_status(values: Mapping[str, Any], *, runtime_ready: bool) -> str:
    if not runtime_ready:
        return "blocked"
    explicit = _first(values, "business_ranking_ready", "business_ranking_status")
    if isinstance(explicit, bool):
        return "ready" if explicit else "cold_start"
    explicit_text = str(explicit or "").strip().lower()
    if explicit_text in {"ready", "cold_start", "blocked"}:
        return explicit_text
    deals = _as_number(_first(values, "deals_count", "deal_count", "deals")) or 0
    usage = _as_number(
        _first(values, "slide_usage_count", "usage_count", "usages_count", "usage")
    ) or 0
    return "ready" if deals > 0 and usage > 0 else "cold_start"


def _data_hygiene_status(values: Mapping[str, Any], *, runtime_ready: bool) -> str:
    if not runtime_ready:
        return "blocked"
    explicit = str(
        _first(values, "data_hygiene_status", "hygiene_status") or ""
    ).strip().lower()
    if explicit in {"ready", "degraded", "blocked"}:
        return explicit
    failed_value = _first(values, "failed_jobs_count", "failed_job_count", "failed_jobs")
    orphan_value = _first(
        values,
        "orphan_presentations_count",
        "orphan_presentation_count",
        "orphan_count",
        "orphans",
    )
    failed = _as_number(failed_value)
    orphan = _as_number(orphan_value)
    coverage = _as_number(_first(values, "source_coverage", "source_coverage_ratio"))
    if (failed or 0) > 0 or (orphan or 0) > 0 or (coverage is not None and coverage < 1):
        return "degraded"
    if failed is not None and orphan is not None:
        return "ready"
    return "degraded"


def _clone_library_state(source_home: Path, target_home: Path) -> bool:
    clone_flag = "-c" if sys.platform == "darwin" else "--reflink=always"
    for name in ("index.db", "config.yml"):
        source = source_home / name
        if not source.is_file():
            continue
        try:
            completed = subprocess.run(
                ["cp", clone_flag, str(source), str(target_home / name)],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        if completed.returncode != 0:
            return False
    return (target_home / "index.db").is_file()


def inspect_library_status(
    *,
    repo_root: str | Path | None = None,
    command: str = "ppt-lib",
    which: Callable[[str], str | None] = shutil.which,
    library_home: str | Path | None = None,
    snapshotter: Callable[[Path, Path], bool] = _clone_library_state,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Return v2 status without changing the source Library or user files."""
    root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parents[2]
    source_home = (
        Path(library_home).expanduser().resolve()
        if library_home is not None
        else Path.home() / ".ppt-library"
    )
    contract_ready = _contract_ready(root)
    cli_path = which(command)
    payload: dict[str, Any] = {}
    runtime_ready = False
    runtime_failure = "PPT_LIBRARY_CLI_MISSING" if not cli_path else ""
    state_ready = (source_home / "index.db").is_file() if cli_path else False
    if cli_path and not state_ready:
        runtime_failure = "PPT_LIBRARY_STATE_MISSING"

    if cli_path and state_ready:
        with tempfile.TemporaryDirectory(prefix="deck-master-library-status-") as tmp:
            isolated_home = Path(tmp)
            if not snapshotter(source_home, isolated_home):
                completed = None
                runtime_failure = "PPT_LIBRARY_READ_ONLY_SNAPSHOT_UNAVAILABLE"
            else:
                try:
                    completed = runner(
                        [
                            command,
                            "--home-dir",
                            str(isolated_home),
                            "status",
                            "--output",
                            "json",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=15,
                    )
                except (OSError, subprocess.SubprocessError):
                    completed = None
        if completed is None or completed.returncode != 0:
            if runtime_failure != "PPT_LIBRARY_READ_ONLY_SNAPSHOT_UNAVAILABLE":
                runtime_failure = "PPT_LIBRARY_STATUS_FAILED"
        else:
            try:
                decoded = json.loads(completed.stdout)
            except (TypeError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, dict):
                payload = decoded
                runtime_ready = True
            else:
                runtime_failure = "PPT_LIBRARY_STATUS_INVALID"

    values = _flatten(payload)
    semantic_explicit = _as_bool(
        _first(
            values,
            "semantic_search_ready",
            "semantic_ready",
            "search_ready",
            "semantic_search_available",
        )
    )
    slide_count = _as_number(
        _first(values, "slides_count", "slide_count", "total_slides", "indexed_slides")
    )
    semantic_search_ready = bool(
        runtime_ready
        and contract_ready
        and (semantic_explicit if semantic_explicit is not None else (slide_count or 0) > 0)
    )
    role_selection_ready = bool(
        semantic_search_ready and _role_selection_ready(payload, values)
    )
    preview_explicit = _as_bool(
        _first(values, "preview_ready", "screenshots_ready", "screenshot_ready")
    )
    preview_ready = bool(runtime_ready and preview_explicit is True)
    fallback_ready = bool(runtime_ready and contract_ready and semantic_search_ready)
    business_ranking_ready = _business_ranking_status(values, runtime_ready=runtime_ready)
    data_hygiene_status = _data_hygiene_status(values, runtime_ready=runtime_ready)

    blocking_summary: list[str] = []
    if runtime_failure:
        blocking_summary.append(runtime_failure)
    if not contract_ready:
        blocking_summary.append("PPT_LIBRARY_CONTRACT_MISSING")
    if runtime_ready and contract_ready and not semantic_search_ready:
        blocking_summary.append("PPT_LIBRARY_SEMANTIC_SEARCH_UNAVAILABLE")

    warnings: list[str] = []
    if semantic_search_ready and not role_selection_ready:
        warnings.append("ROLE_SELECTION_UNAVAILABLE")
    if runtime_ready and not preview_ready:
        warnings.append("PREVIEW_DEGRADED")
    if business_ranking_ready == "cold_start":
        warnings.append("BUSINESS_RANKING_COLD_START")
    if data_hygiene_status == "degraded":
        warnings.append("DATA_HYGIENE_DEGRADED")

    status = "blocked" if blocking_summary else "degraded_ready"
    if (
        runtime_ready
        and contract_ready
        and semantic_search_ready
        and role_selection_ready
        and fallback_ready
        and preview_ready
    ):
        status = "ready"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "runtime_ready": runtime_ready,
        "contract_ready": contract_ready,
        "semantic_search_ready": semantic_search_ready,
        "role_selection_ready": role_selection_ready,
        "fallback_ready": fallback_ready,
        "preview_ready": preview_ready,
        "business_ranking_ready": business_ranking_ready,
        "data_hygiene_status": data_hygiene_status,
        "blocking_summary": blocking_summary,
        "warnings": warnings,
    }


__all__ = ["SCHEMA_VERSION", "inspect_library_status"]
