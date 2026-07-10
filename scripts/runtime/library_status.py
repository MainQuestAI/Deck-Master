"""Canonical read-only PPT Library readiness inspection."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "deck_master_library_status.v2"
SEMANTIC_PROBE_QUERY = "business solution architecture"
COMMAND_TIMEOUT_SECONDS = 15
DEFAULT_CACHE_TTL_SECONDS = 10.0
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
_STATUS_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}
_STATUS_CACHE_LOCK = threading.Lock()


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


def _contract_state(repo_root: Path) -> tuple[bool, str]:
    paths = (
        repo_root / "product_capabilities" / "ppt-library" / "capability.json",
        repo_root / "docs" / "contracts" / "ppt-library-selection.v2.schema.json",
        repo_root / "docs" / "contracts" / "ppt-library-bridge-plan.v1.schema.json",
        repo_root / "docs" / "contracts" / "library-status.v2.schema.json",
        repo_root / "scripts" / "tools" / "ppt_library_client.py",
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(repo_root).as_posix().encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")

    capability = _read_json_object(paths[0])
    selection = _read_json_object(paths[1])
    bridge_plan = _read_json_object(paths[2])
    library_status = _read_json_object(paths[3])
    if not capability or capability.get("name") != "ppt-library":
        return False, digest.hexdigest()
    operations = (capability.get("runtime") or {}).get("operations")
    if not isinstance(operations, list) or not {"status", "search", "select-slides"}.issubset(
        {str(item) for item in operations}
    ):
        return False, digest.hexdigest()
    contracts = capability.get("contracts") if isinstance(capability.get("contracts"), dict) else {}
    outputs = contracts.get("outputs") if isinstance(contracts.get("outputs"), list) else []
    state_policy = (
        capability.get("state_policy") if isinstance(capability.get("state_policy"), dict) else {}
    )
    selection_version = ((selection or {}).get("properties") or {}).get("schema_version")
    bridge_version = ((bridge_plan or {}).get("properties") or {}).get("schema_version")
    status_version = ((library_status or {}).get("properties") or {}).get("schema_version")
    ready = bool(
        {
            "deck_master_ppt_library_selection.v1",
            "deck_master_ppt_library_selection.v2",
        }.issubset({str(item) for item in outputs})
        and contracts.get("canonical_output") == "deck_master_ppt_library_selection.v2"
        and contracts.get("readiness_output") == SCHEMA_VERSION
        and state_policy.get("canonical_artifact")
        == "external/ppt_library/library_results.v2.json"
        and isinstance(selection_version, dict)
        and selection_version.get("const") == "deck_master_ppt_library_selection.v2"
        and isinstance(bridge_version, dict)
        and bridge_version.get("const") == "deck_master_ppt_library_bridge_plan.v1"
        and isinstance(status_version, dict)
        and status_version.get("const") == SCHEMA_VERSION
        and paths[4].is_file()
    )
    return ready, digest.hexdigest()


def _contract_ready(repo_root: Path) -> bool:
    return _contract_state(repo_root)[0]


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


def _copy_snapshot_file(
    source: Path,
    target: Path,
    *,
    copy_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> bool:
    clone_flag = "-c" if sys.platform == "darwin" else "--reflink=always"
    commands = (
        ["cp", clone_flag, str(source), str(target)],
        ["cp", str(source), str(target)],
    )
    for command in commands:
        try:
            target.unlink(missing_ok=True)
            completed = copy_runner(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0 and target.is_file():
            return True
    return False


def _clone_library_state(
    source_home: Path,
    target_home: Path,
    *,
    copy_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    for name in ("index.db", "config.yml"):
        source = source_home / name
        if not source.is_file():
            continue
        if not _copy_snapshot_file(source, target_home / name, copy_runner=copy_runner):
            return False
    return (target_home / "index.db").is_file()


def _search_probe_ready(payload: Any) -> bool:
    if isinstance(payload, list):
        return bool(payload)
    if not isinstance(payload, dict):
        return False
    for key in ("results", "slides", "items", "matches"):
        results = payload.get(key)
        if isinstance(results, list):
            return bool(results)
    return False


def _source_signature(source_home: Path) -> tuple[Any, ...] | None:
    try:
        index_stat = (source_home / "index.db").stat()
    except OSError:
        return None
    try:
        config_stat = (source_home / "config.yml").stat()
        config_signature = (config_stat.st_mtime_ns, config_stat.st_size)
    except OSError:
        config_signature = (0, 0)
    return (
        str(source_home),
        index_stat.st_mtime_ns,
        index_stat.st_size,
        *config_signature,
    )


def _clear_library_status_cache() -> None:
    with _STATUS_CACHE_LOCK:
        _STATUS_CACHE.clear()


def _cached_status(key: tuple[Any, ...], now: float) -> dict[str, Any] | None:
    with _STATUS_CACHE_LOCK:
        cached = _STATUS_CACHE.get(key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            _STATUS_CACHE.pop(key, None)
            return None
        return copy.deepcopy(payload)


def _store_cached_status(
    key: tuple[Any, ...],
    payload: dict[str, Any],
    *,
    expires_at: float,
) -> None:
    with _STATUS_CACHE_LOCK:
        _STATUS_CACHE[key] = (expires_at, copy.deepcopy(payload))


def inspect_library_status(
    *,
    repo_root: str | Path | None = None,
    command: str = "ppt-lib",
    which: Callable[[str], str | None] = shutil.which,
    library_home: str | Path | None = None,
    snapshotter: Callable[[Path, Path], bool] = _clone_library_state,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Return v2 status without changing the source Library or user files."""
    root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parents[2]
    source_home = (
        Path(library_home).expanduser().resolve()
        if library_home is not None
        else Path.home() / ".ppt-library"
    )
    contract_ready, contract_fingerprint = _contract_state(root)
    cli_path = which(command)
    source_signature = _source_signature(source_home) if cli_path else None
    cache_key = (
        str(Path(cli_path).expanduser().resolve()) if cli_path else "",
        *source_signature,
        contract_fingerprint,
    ) if source_signature else None
    now = clock()
    if cache_key is not None and cache_ttl_seconds > 0:
        cached = _cached_status(cache_key, now)
        if cached is not None:
            return cached
    payload: dict[str, Any] = {}
    search_probe_ready = False
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
                        timeout=COMMAND_TIMEOUT_SECONDS,
                    )
                except (OSError, subprocess.SubprocessError):
                    completed = None
            if completed is not None and completed.returncode == 0:
                try:
                    decoded = json.loads(completed.stdout)
                except (TypeError, json.JSONDecodeError):
                    decoded = None
                if isinstance(decoded, dict):
                    payload = decoded
                    runtime_ready = True
                    try:
                        search_completed = runner(
                            [
                                command,
                                "--home-dir",
                                str(isolated_home),
                                "search",
                                SEMANTIC_PROBE_QUERY,
                                "--top-k",
                                "1",
                                "--threshold",
                                "0",
                                "--output",
                                "json",
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=COMMAND_TIMEOUT_SECONDS,
                        )
                    except (OSError, subprocess.SubprocessError):
                        search_completed = None
                    if search_completed is not None and search_completed.returncode == 0:
                        try:
                            search_payload = json.loads(search_completed.stdout)
                        except (TypeError, json.JSONDecodeError):
                            search_payload = None
                        search_probe_ready = _search_probe_ready(search_payload)
                else:
                    runtime_failure = "PPT_LIBRARY_STATUS_INVALID"

        if completed is None or completed.returncode != 0:
            if runtime_failure != "PPT_LIBRARY_READ_ONLY_SNAPSHOT_UNAVAILABLE":
                runtime_failure = "PPT_LIBRARY_STATUS_FAILED"

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
    semantic_search_ready = bool(
        runtime_ready
        and contract_ready
        and search_probe_ready
        and semantic_explicit is not False
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

    result = {
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
    if cache_key is not None and cache_ttl_seconds > 0 and runtime_ready:
        _store_cached_status(
            cache_key,
            result,
            expires_at=now + cache_ttl_seconds,
        )
    return result


__all__ = ["SCHEMA_VERSION", "inspect_library_status"]
