"""Canonical read-only PPT Library readiness inspection."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
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
_EXPECTED_DECLARATION = {
    "operations": (
        "status",
        "search",
        "select-slides",
        "doctor",
        "schema",
        "smoke --fixture",
        "writeback",
    ),
    "outputs": (
        "deck_master_ppt_library_selection.v1",
        "deck_master_ppt_library_selection.v2",
    ),
    "canonical_output": "deck_master_ppt_library_selection.v2",
    "readiness_output": SCHEMA_VERSION,
    "canonical_artifact": "external/ppt_library/library_results.v2.json",
    "required_capabilities": (
        "ppt_library.doctor.v1",
        "ppt_library.search.v1",
        "ppt_library.selection.v1",
        "ppt_library.selection.v2",
        "ppt_library.status.v2",
    ),
    "schema_versions": {
        "selection_output_legacy": "deck_master_ppt_library_selection.v1",
        "selection_output": "deck_master_ppt_library_selection.v2",
        "library_status": SCHEMA_VERSION,
        "feedback_input": "deck_master_ppt_library_feedback.v1",
    },
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


def _yaml_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized in {"true", "false"}:
        return normalized == "true"
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in "\"'":
        return normalized[1:-1]
    return normalized


def _read_capability_yaml(path: Path) -> dict[str, Any] | None:
    """Parse the manifest's intentionally small, dependency-free YAML subset."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    payload: dict[str, Any] = {}
    section: str | None = None
    for raw_line in lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0:
            if ":" not in line:
                return None
            key, value = line.split(":", 1)
            section = key.strip()
            payload[section] = _yaml_scalar(value) if value.strip() else None
            continue
        if indent != 2 or section is None:
            return None
        if line.startswith("- "):
            if payload[section] is None:
                payload[section] = []
            if not isinstance(payload[section], list):
                return None
            payload[section].append(_yaml_scalar(line[2:]))
            continue
        if ":" not in line:
            return None
        if payload[section] is None:
            payload[section] = {}
        if not isinstance(payload[section], dict):
            return None
        key, value = line.split(":", 1)
        payload[section][key.strip()] = _yaml_scalar(value)
    return payload


def _read_installer_library_spec(path: Path) -> dict[str, Any] | None:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None
    value_node: ast.expr | None = None
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "SUITE_SKILLS":
                value_node = node.value
                break
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SUITE_SKILLS"
            for target in node.targets
        ):
            value_node = node.value
            break
    if value_node is None:
        return None
    try:
        specs = ast.literal_eval(value_node)
    except (ValueError, TypeError, SyntaxError):
        return None
    if not isinstance(specs, (list, tuple)):
        return None
    return next(
        (
            spec
            for spec in specs
            if isinstance(spec, dict) and spec.get("name") == "ppt-library"
        ),
        None,
    )


def _normalized_declaration(payload: Mapping[str, Any], *, capability: bool) -> dict[str, Any]:
    contracts = payload.get("contracts") if capability else payload
    runtime = payload.get("runtime") if capability else payload
    state_policy = payload.get("state_policy") if capability else payload
    contracts = contracts if isinstance(contracts, Mapping) else {}
    runtime = runtime if isinstance(runtime, Mapping) else {}
    state_policy = state_policy if isinstance(state_policy, Mapping) else {}
    outputs_key = "outputs" if capability or "outputs" in contracts else "contract_outputs"
    return {
        "operations": tuple(str(item) for item in runtime.get("operations", [])),
        "outputs": tuple(str(item) for item in contracts.get(outputs_key, [])),
        "canonical_output": contracts.get("canonical_output"),
        "readiness_output": contracts.get("readiness_output"),
        "canonical_artifact": state_policy.get("canonical_artifact"),
        "required_capabilities": tuple(
            str(item) for item in payload.get("required_capabilities", [])
        ),
        "schema_versions": payload.get("schema_versions"),
    }


def _legacy_selection_schemas_ready(
    capability_schema: Mapping[str, Any] | None,
    docs_schema: Mapping[str, Any] | None,
) -> bool:
    if not capability_schema or not docs_schema or capability_schema != docs_schema:
        return False
    properties = capability_schema.get("properties")
    if not isinstance(properties, Mapping):
        return False
    version = properties.get("schema_version")
    if not isinstance(version, Mapping) or version.get("const") != (
        "deck_master_ppt_library_selection.v1"
    ):
        return False
    required = capability_schema.get("required")
    if not isinstance(required, list) or {str(item) for item in required} != {
        "schema_version",
        "run_id",
    }:
        return False
    expected_shapes = {
        ("selections", "array"),
        ("by_beat", "object"),
        ("beats", "array"),
    }
    actual_shapes = {
        (name, str(schema.get("type")))
        for name in ("selections", "by_beat", "beats")
        if isinstance((schema := properties.get(name)), Mapping)
    }
    any_of = capability_schema.get("anyOf")
    if not isinstance(any_of, list):
        return False
    required_shapes = {
        tuple(str(item) for item in branch.get("required", []))
        for branch in any_of
        if isinstance(branch, Mapping) and isinstance(branch.get("required"), list)
    }
    return actual_shapes == expected_shapes and required_shapes == {
        ("selections",),
        ("by_beat",),
        ("beats",),
    }


def _contract_state(repo_root: Path) -> tuple[bool, str]:
    paths = (
        repo_root / "product_capabilities" / "ppt-library" / "capability.json",
        repo_root / "product_capabilities" / "ppt-library" / "capability.yaml",
        repo_root
        / "product_capabilities"
        / "ppt-library"
        / "contracts"
        / "library-selection.v1.schema.json",
        repo_root / "docs" / "contracts" / "ppt-library-selection.v1.schema.json",
        repo_root / "docs" / "contracts" / "ppt-library-selection.v2.schema.json",
        repo_root / "docs" / "contracts" / "ppt-library-bridge-plan.v1.schema.json",
        repo_root / "docs" / "contracts" / "library-status.v2.schema.json",
        repo_root / "scripts" / "tools" / "ppt_library_client.py",
        repo_root / "scripts" / "skills" / "installer.py",
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(repo_root).as_posix().encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")

    capability = _read_json_object(paths[0])
    capability_yaml = _read_capability_yaml(paths[1])
    capability_legacy_selection = _read_json_object(paths[2])
    docs_legacy_selection = _read_json_object(paths[3])
    selection = _read_json_object(paths[4])
    bridge_plan = _read_json_object(paths[5])
    library_status = _read_json_object(paths[6])
    installer_spec = _read_installer_library_spec(paths[8])
    if not capability or capability.get("name") != "ppt-library":
        return False, digest.hexdigest()
    if not capability_yaml or capability_yaml.get("name") != "ppt-library" or not installer_spec:
        return False, digest.hexdigest()
    json_declaration = _normalized_declaration(capability, capability=True)
    yaml_declaration = _normalized_declaration(capability_yaml, capability=False)
    installer_declaration = _normalized_declaration(installer_spec, capability=False)
    selection_version = ((selection or {}).get("properties") or {}).get("schema_version")
    bridge_version = ((bridge_plan or {}).get("properties") or {}).get("schema_version")
    status_version = ((library_status or {}).get("properties") or {}).get("schema_version")
    ready = bool(
        json_declaration == _EXPECTED_DECLARATION
        and yaml_declaration == _EXPECTED_DECLARATION
        and installer_declaration == _EXPECTED_DECLARATION
        and _legacy_selection_schemas_ready(
            capability_legacy_selection,
            docs_legacy_selection,
        )
        and isinstance(selection_version, dict)
        and selection_version.get("const") == "deck_master_ppt_library_selection.v2"
        and isinstance(bridge_version, dict)
        and bridge_version.get("const") == "deck_master_ppt_library_bridge_plan.v1"
        and isinstance(status_version, dict)
        and status_version.get("const") == SCHEMA_VERSION
        and paths[7].is_file()
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
    commands = (
        ["cp", "--reflink=always", str(source), str(target)],
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


def _backup_index_database(
    source: Path,
    target: Path,
    *,
    timeout_seconds: float = COMMAND_TIMEOUT_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    started_at = clock()
    succeeded = False
    source_connection: sqlite3.Connection | None = None
    target_connection: sqlite3.Connection | None = None

    def progress(_status: int, _remaining: int, _total: int) -> None:
        if clock() - started_at > timeout_seconds:
            raise TimeoutError("PPT Library snapshot backup timed out")

    try:
        target.unlink(missing_ok=True)
        source_connection = sqlite3.connect(
            f"{source.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=min(timeout_seconds, 5.0),
        )
        target_connection = sqlite3.connect(
            target,
            timeout=min(timeout_seconds, 5.0),
        )
        source_connection.backup(
            target_connection,
            pages=256,
            progress=progress,
            sleep=0.05,
        )
        succeeded = target.is_file()
        return succeeded
    except (OSError, sqlite3.Error, TimeoutError):
        return False
    finally:
        if target_connection is not None:
            target_connection.close()
        if source_connection is not None:
            source_connection.close()
        if not succeeded:
            target.unlink(missing_ok=True)


def _clone_library_state(
    source_home: Path,
    target_home: Path,
    *,
    copy_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    source_index = source_home / "index.db"
    source_signature = _source_signature(source_home)
    if not source_index.is_file() or source_signature is None:
        return False
    with tempfile.TemporaryDirectory(
        prefix="sqlite-backup-source-",
        dir=target_home,
    ) as staging_dir:
        staging_home = Path(staging_dir)
        for name in ("index.db", "index.db-wal"):
            source = source_home / name
            if source.is_file() and not _copy_snapshot_file(
                source,
                staging_home / name,
                copy_runner=copy_runner,
            ):
                return False
        if not _backup_index_database(
            staging_home / "index.db",
            target_home / "index.db",
        ):
            return False
        source_config = source_home / "config.yml"
        if source_config.is_file():
            if not _copy_snapshot_file(
                source_config,
                target_home / "config.yml",
                copy_runner=copy_runner,
            ):
                return False
    if _source_signature(source_home) != source_signature:
        (target_home / "index.db").unlink(missing_ok=True)
        (target_home / "config.yml").unlink(missing_ok=True)
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
        (source_home / "index.db").stat()
    except OSError:
        return None
    signatures: list[Any] = [str(source_home)]
    for name in ("index.db", "index.db-wal", "index.db-shm", "config.yml"):
        try:
            stat = (source_home / name).stat()
            signatures.extend((name, stat.st_mtime_ns, stat.st_size))
        except OSError:
            signatures.extend((name, 0, 0))
    return tuple(signatures)


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
