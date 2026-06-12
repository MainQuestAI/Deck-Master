from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.run_state import RunStateError, read_json


SCHEMA_VERSION = "deck_benchmark_case.v1"
ALLOWED_PLANNING_MODES = {"classic", "narrative_v2"}
_SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class BenchmarkCaseError(ValueError):
    pass


@dataclass(frozen=True)
class BenchmarkCase:
    data: dict[str, Any]
    path: Path
    case_dir: Path
    benchmark_dir: Path | None
    resolved_paths: dict[str, Path]
    warnings: list[str]


def _require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkCaseError(f"{field} must be an object.")
    return value


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkCaseError(f"{field} is required.")
    return value.strip()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_case_id(case_id: Any) -> str:
    actual = _require_non_empty_string(case_id, "case_id")
    if actual in {".", ".."} or "/" in actual or "\\" in actual or not _SAFE_CASE_ID.match(actual):
        raise BenchmarkCaseError("case_id must be filename-safe.")
    return actual


def validate_benchmark_case(data: dict[str, Any]) -> list[str]:
    """Validate benchmark_case.json and return non-blocking warnings."""
    warnings: list[str] = []
    _require_object(data, "benchmark case")

    if data.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkCaseError(f"schema_version must be {SCHEMA_VERSION}.")

    _validate_case_id(data.get("case_id"))
    _require_non_empty_string(data.get("case_name"), "case_name")

    target_pages = data.get("target_pages")
    if target_pages is not None and (
        not isinstance(target_pages, int) or isinstance(target_pages, bool) or target_pages <= 0
    ):
        raise BenchmarkCaseError("target_pages must be a positive integer when provided.")

    inputs = _require_object(data.get("inputs"), "inputs")
    baseline = inputs.get("baseline_manual_hours")
    if not _is_number(baseline):
        raise BenchmarkCaseError("inputs.baseline_manual_hours is required and must be numeric.")
    if baseline <= 0:
        raise BenchmarkCaseError("inputs.baseline_manual_hours must be greater than 0.")

    workflow = _require_object(data.get("workflow"), "workflow")
    planning_mode = workflow.get("planning_mode")
    if planning_mode not in ALLOWED_PLANNING_MODES:
        allowed = ", ".join(sorted(ALLOWED_PLANNING_MODES))
        raise BenchmarkCaseError(f"workflow.planning_mode must be one of: {allowed}.")

    success_targets = _require_object(data.get("success_targets"), "success_targets")
    if not success_targets:
        raise BenchmarkCaseError("success_targets must contain at least one target.")

    scoring = data.get("scoring")
    if scoring is not None:
        scoring_obj = _require_object(scoring, "scoring")
        weights = scoring_obj.get("weights")
        if weights is not None:
            weights_obj = _require_object(weights, "scoring.weights")
            if not weights_obj:
                raise BenchmarkCaseError("scoring.weights must not be empty when provided.")
            invalid = [key for key, value in weights_obj.items() if not _is_number(value)]
            if invalid:
                raise BenchmarkCaseError(f"scoring.weights values must be numeric: {', '.join(sorted(invalid))}.")
            total = sum(float(value) for value in weights_obj.values())
            if abs(total - 1.0) > 0.001:
                warnings.append(f"scoring.weights sum is {total:.4f}; expected approximately 1.0.")

    return warnings


def _infer_benchmark_dir(case_path: Path) -> Path | None:
    case_dir = case_path.parent
    if case_dir.parent.name == "cases":
        return case_dir.parent.parent.resolve()
    return None


def _resolve_path(value: Any, *, base_dir: Path, benchmark_dir: Path | None) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    parts = raw.parts
    if benchmark_dir is not None and parts and parts[0] == benchmark_dir.name:
        return (benchmark_dir.parent / raw).resolve()
    return (base_dir / raw).resolve()


def _resolved_paths(data: dict[str, Any], case_path: Path, benchmark_dir: Path | None) -> dict[str, Path]:
    case_dir = case_path.parent
    paths: dict[str, Path] = {"case_dir": case_dir}
    workspace = _resolve_path(data.get("workspace"), base_dir=benchmark_dir or case_dir, benchmark_dir=benchmark_dir)
    runs_dir = _resolve_path(data.get("runs_dir"), base_dir=benchmark_dir or case_dir, benchmark_dir=benchmark_dir)
    context_pack = _resolve_path(
        data.get("inputs", {}).get("context_pack"),
        base_dir=case_dir,
        benchmark_dir=benchmark_dir,
    )
    if benchmark_dir is not None:
        paths["benchmark_dir"] = benchmark_dir
    if workspace is not None:
        paths["workspace"] = workspace
    if runs_dir is not None:
        paths["runs_dir"] = runs_dir
    if context_pack is not None:
        paths["context_pack"] = context_pack
    return paths


def load_benchmark_case(
    case_path: str | Path,
    *,
    benchmark_dir: str | Path | None = None,
) -> BenchmarkCase:
    """Read, validate, and resolve paths for benchmark_case.json."""
    path = Path(case_path).expanduser().resolve()
    try:
        data = read_json(path)
    except RunStateError as exc:
        raise BenchmarkCaseError(str(exc)) from exc

    warnings = validate_benchmark_case(data)
    actual_benchmark_dir = (
        Path(benchmark_dir).expanduser().resolve()
        if benchmark_dir is not None
        else _infer_benchmark_dir(path)
    )
    return BenchmarkCase(
        data=data,
        path=path,
        case_dir=path.parent,
        benchmark_dir=actual_benchmark_dir,
        resolved_paths=_resolved_paths(data, path, actual_benchmark_dir),
        warnings=warnings,
    )


def load_case_json(path: str | Path) -> dict[str, Any]:
    """Small CLI-friendly wrapper that keeps JSON errors under BenchmarkCaseError."""
    try:
        return read_json(path)
    except RunStateError as exc:
        raise BenchmarkCaseError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkCaseError(str(exc)) from exc
