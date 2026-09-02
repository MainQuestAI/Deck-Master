from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


ARTIFACT_BOUND_GATES = frozenset({
    "render",
    "delivery",
    "customer_visible_safety",
    "customer-visible-safety",
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
    gate = str(report.get("gate") or "").strip().lower()
    return gate in ARTIFACT_BOUND_GATES


def artifact_identity(root: Path | str, artifact: Path | str) -> dict[str, Any]:
    resolved_root = Path(root).expanduser().resolve()
    resolved = Path(artifact).expanduser().resolve()
    relative = run_relative(resolved_root, resolved)
    digest = sha256_file(resolved) if resolved.exists() and resolved.is_file() else ""
    binding = {
        "artifact_run_relative": relative,
        "artifact_sha256": digest,
        "source_fingerprint": "",
        "build_manifest_sha256": "",
        "artifact_manifest_sha256": "",
    }
    return {
        "artifact_binding": binding,
        "artifact_path": relative or str(resolved),
        "artifact_run_relative": relative,
        "artifact_sha256": digest,
        "artifact_hash": digest,
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
    if binding:
        declared_identity = True
        declared_rel = str(binding.get("artifact_run_relative") or "").strip()
        if declared_rel:
            checks.append("artifact_binding.artifact_run_relative")
            if not _declared_path_matches(root, declared_rel, artifact_rel, artifact):
                return {"status": "stale", "current": False, "reason": "artifact_binding.artifact_run_relative is stale", "checks": checks}
        declared_hash = str(binding.get("artifact_sha256") or "").strip()
        if declared_hash:
            checks.append("artifact_binding.artifact_sha256")
            if declared_hash != artifact_hash:
                return {"status": "stale", "current": False, "reason": "artifact_binding.artifact_sha256 is stale", "checks": checks}
        if not declared_rel and not declared_hash and bound:
            return {"status": "unbound", "current": False, "reason": "artifact binding identity is missing", "checks": checks}
    else:
        declared_identity = False
    expected_path = {
        "artifact_path": artifact_rel,
        "artifact_run_relative": artifact_rel,
    }
    for key, value in expected_path.items():
        declared = str(report.get(key) or "").strip()
        if declared:
            declared_identity = True
            checks.append(key)
            if not _declared_path_matches(root, declared, value, artifact):
                return {"status": "stale", "current": False, "reason": f"{key} is stale", "checks": checks}
    legacy_artifact = str(report.get("artifact") or "").strip()
    if legacy_artifact:
        declared_identity = True
        checks.append("artifact")
        if not _declared_path_matches(root, legacy_artifact, artifact_rel, artifact):
            return {"status": "stale", "current": False, "reason": "artifact is stale", "checks": checks}
    expected_hash = {
        "artifact_sha256": artifact_hash,
        "artifact_hash": artifact_hash,
    }
    for key, value in expected_hash.items():
        declared = str(report.get(key) or "").strip()
        if declared:
            declared_identity = True
            checks.append(key)
            if declared != value:
                return {"status": "stale", "current": False, "reason": f"{key} is stale", "checks": checks}
    if bound and not declared_identity:
        return {"status": "unbound", "current": False, "reason": "artifact identity is missing", "checks": checks}
    source_fingerprint = str(report.get("source_fingerprint") or "")
    artifact_source = str(report.get("artifact_source_fingerprint") or "")
    if source_fingerprint and artifact_source and source_fingerprint != artifact_source:
        return {"status": "stale", "current": False, "reason": "source_fingerprint is stale", "checks": [*checks, "source_fingerprint"]}
    return {"status": "current", "current": True, "reason": "", "checks": checks}
