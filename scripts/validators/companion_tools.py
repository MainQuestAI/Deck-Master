"""Companion Tool UAT Validators for Deck Master v0.9.

Implements:
- validate_ppt_library_result: validate PPT Library candidate output.
- validate_render_result: validate PPT Master render output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ValidatorError(ValueError):
    """Raised when validation input is invalid."""


# --------------------------------------------------------------------------- #
# PPT Library Candidate Validator
# --------------------------------------------------------------------------- #


REQUIRED_LIBRARY_FIELDS = {
    "slide_id", "title", "text_summary", "source_file",
    "page_number", "confidence",
}

WARNING_LIBRARY_FIELDS = {"canonical_slide_id", "screenshot_path"}


def validate_ppt_library_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate a PPT Library candidate result.

    Returns {"valid": True/False, "errors": [...], "warnings": [...]}.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(result, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}

    # Check candidates list or single candidate.
    candidates = result.get("candidates", [result])
    if not isinstance(candidates, list):
        candidates = [result]

    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"candidates[{i}] must be an object.")
            continue

        prefix = f"candidates[{i}]" if len(candidates) > 1 else ""

        # Required fields.
        for field in REQUIRED_LIBRARY_FIELDS:
            if field not in candidate or candidate[field] is None:
                errors.append(f"{prefix} Missing required field: '{field}'.")

        # page_number must be numeric.
        pn = candidate.get("page_number")
        if pn is not None and not isinstance(pn, (int, float)):
            try:
                int(pn)
            except (TypeError, ValueError):
                errors.append(f"{prefix} page_number must be numeric, got '{pn}'.")

        # confidence must be 0-1.
        conf = candidate.get("confidence")
        if conf is not None:
            try:
                conf_f = float(conf)
                if not (0.0 <= conf_f <= 1.0):
                    errors.append(f"{prefix} confidence must be 0-1, got {conf}.")
            except (TypeError, ValueError):
                errors.append(f"{prefix} confidence must be numeric, got '{conf}'.")

        # Warning fields.
        for field in WARNING_LIBRARY_FIELDS:
            if not candidate.get(field):
                warnings.append(f"{prefix} Optional field '{field}' is missing.")

        # source_file existence (warning only).
        sf = candidate.get("source_file", "")
        if sf and not Path(sf).exists():
            warnings.append(f"{prefix} source_file does not exist: '{sf}'.")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# --------------------------------------------------------------------------- #
# Render Result Validator
# --------------------------------------------------------------------------- #


def validate_render_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate a PPT Master render result.

    Returns {"valid": True/False, "errors": [...], "warnings": [...]}.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(result, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}

    schema = result.get("schema_version")
    if schema != "deck_render_result.v1":
        errors.append(f"schema_version must be 'deck_render_result.v1', got '{schema}'.")

    if not result.get("run_id"):
        errors.append("run_id is required.")
    if not result.get("tool"):
        errors.append("tool is required.")

    status = result.get("status", "")
    valid_statuses = {"completed", "failed", "partial"}
    if status not in valid_statuses:
        errors.append(f"status must be one of {sorted(valid_statuses)}.")

    if status == "completed":
        artifact = result.get("artifact_path", "")
        if not artifact:
            errors.append("completed result must have artifact_path.")
        elif not Path(artifact).exists():
            warnings.append(f"artifact_path does not exist: '{artifact}'.")

        page_count = result.get("page_count")
        if page_count is not None and not isinstance(page_count, int):
            errors.append(f"page_count must be integer, got '{page_count}'.")

    if status == "failed":
        err_list = result.get("errors", [])
        if not err_list:
            errors.append("failed result must have errors.")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
