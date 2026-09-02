from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_BOUND_GATES = frozenset({
    "render",
    "delivery",
    "customer_visible_safety",
    "delivery_validation",
})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_relative(root: Path | str, path: Path | str) -> str:
    root = Path(root)
    path = Path(path)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""


def is_artifact_bound_gate(report: dict[str, Any]) -> bool:
    gate = str(report.get("gate") or "").strip().lower().replace("-", "_")
    binding = report.get("artifact_binding")
    has_identity = isinstance(binding, dict) or any(
        str(report.get(key) or "").strip()
        for key in ("artifact_run_relative", "artifact_path", "artifact", "artifact_sha256", "artifact_hash")
    )
    return gate in ARTIFACT_BOUND_GATES or has_identity


def _read_manifest_metadata(root: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for relative in (
        Path("render_results") / "render_result.json",
        Path("build") / "build_manifest.json",
        Path("build") / "artifact_manifest.json",
    ):
        path = root / relative
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        fingerprint = str(payload.get("source_fingerprint") or "").strip()
        if fingerprint and not metadata.get("source_fingerprint"):
            metadata["source_fingerprint"] = fingerprint
        if relative.parts[-1] == "build_manifest.json":
            metadata["build_manifest_sha256"] = sha256_file(path)
        elif relative.parts[-1] == "artifact_manifest.json":
            metadata["artifact_manifest_sha256"] = sha256_file(path)
    return metadata


def artifact_identity(root: Path | str, artifact: Path | str) -> dict[str, Any]:
    resolved_root = Path(root).expanduser().resolve()
    resolved = Path(artifact).expanduser().resolve()
    relative = run_relative(resolved_root, resolved)
    digest = sha256_file(resolved) if resolved.exists() and resolved.is_file() else ""
    metadata = _read_manifest_metadata(resolved_root)
    binding = {
        "artifact_run_relative": relative,
        "artifact_sha256": digest,
        "source_fingerprint": metadata.get("source_fingerprint", ""),
        "build_manifest_sha256": metadata.get("build_manifest_sha256", ""),
        "artifact_manifest_sha256": metadata.get("artifact_manifest_sha256", ""),
    }
    return {
        "artifact_binding": binding,
        "artifact_path": relative or str(resolved),
        "artifact_run_relative": relative,
        "artifact_sha256": digest,
        "artifact_hash": digest,
        "source_fingerprint": binding["source_fingerprint"],
        "artifact_source_fingerprint": binding["source_fingerprint"],
        "build_manifest_sha256": binding["build_manifest_sha256"],
        "artifact_manifest_sha256": binding["artifact_manifest_sha256"],
    }


def _declared_path_matches(root: Path, declared: str, expected_relative: str, expected_absolute: Path) -> bool:
    value = str(declared or "").strip()
    if not value:
        return True
    if value == expected_relative or value == str(expected_absolute):
        return True
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.expanduser().resolve() == expected_absolute
    except OSError:
        return False


def report_currentity(
    root: Path | str,
    report: dict[str, Any],
    artifact: Path | str | None = None,
    *,
    artifact_bound: bool | None = None,
) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    bound = is_artifact_bound_gate(report) if artifact_bound is None else artifact_bound
    if artifact is None:
        if bound:
            return {"status": "unbound", "current": False, "reason": "current artifact is unavailable", "checks": []}
        return {"status": "current", "current": True, "reason": "", "checks": []}
    artifact = Path(artifact).expanduser().resolve()
    if bound and (not artifact.exists() or not artifact.is_file()):
        return {"status": "unbound", "current": False, "reason": "current artifact is missing", "checks": []}
    checks: list[str] = []
    artifact_rel = run_relative(root, artifact)
    artifact_hash = sha256_file(artifact) if artifact.exists() and artifact.is_file() else ""
    binding = report.get("artifact_binding") if isinstance(report.get("artifact_binding"), dict) else {}
    declared_path = ""
    declared_path_key = ""
    declared_hash = ""
    declared_hash_key = ""
    for key in ("artifact_run_relative", "artifact_path", "artifact"):
        value = str(binding.get(key) or report.get(key) or "").strip()
        if not value:
            continue
        declared_path = value
        check_key = f"artifact_binding.{key}" if key in binding else key
        declared_path_key = check_key
        checks.append(check_key)
        break

    for key in ("artifact_sha256", "artifact_hash"):
        value = str(binding.get(key) or report.get(key) or "").strip()
        if not value:
            continue
        declared_hash = value
        check_key = f"artifact_binding.{key}" if key in binding else key
        declared_hash_key = check_key
        checks.append(check_key)
        break

    if bound and not declared_path:
        reason = "artifact identity is missing" if not declared_hash else "artifact path binding is missing"
        return {"status": "unbound", "current": False, "reason": reason, "checks": checks}
    if bound and not declared_hash:
        return {"status": "unbound", "current": False, "reason": "artifact SHA-256 binding is missing", "checks": checks}

    if declared_path and not _declared_path_matches(root, declared_path, artifact_rel, artifact):
        return {"status": "stale", "current": False, "reason": f"{declared_path_key} is stale", "checks": checks}
    if declared_hash and declared_hash != artifact_hash:
        return {"status": "stale", "current": False, "reason": f"{declared_hash_key} is stale", "checks": checks}

    current_metadata = _read_manifest_metadata(root)
    for key in ("source_fingerprint", "build_manifest_sha256", "artifact_manifest_sha256"):
        declared = str(binding.get(key) or report.get(key) or "").strip()
        if not declared:
            continue
        checks.append(f"artifact_binding.{key}" if key in binding else key)
        current = current_metadata.get(key, "")
        if current and declared != current:
            return {"status": "stale", "current": False, "reason": f"{key} is stale", "checks": checks}
    source_fingerprint = str(report.get("source_fingerprint") or "")
    artifact_source = str(report.get("artifact_source_fingerprint") or "")
    if source_fingerprint and artifact_source and source_fingerprint != artifact_source:
        return {"status": "stale", "current": False, "reason": "source_fingerprint is stale", "checks": [*checks, "source_fingerprint"]}
    return {"status": "current", "current": True, "reason": "", "checks": checks}
