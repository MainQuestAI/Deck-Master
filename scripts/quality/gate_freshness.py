from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""


def report_currentity(root: Path, report: dict[str, Any], artifact: Path | None = None) -> dict[str, Any]:
    if artifact is None:
        return {"current": True, "reason": "", "checks": []}
    checks: list[str] = []
    artifact = artifact.expanduser().resolve()
    artifact_rel = run_relative(root, artifact)
    artifact_hash = sha256_file(artifact) if artifact.exists() and artifact.is_file() else ""
    expected = {
        "artifact_path": artifact_rel,
        "artifact_run_relative": artifact_rel,
        "artifact_sha256": artifact_hash,
        "artifact_hash": artifact_hash,
    }
    for key, value in expected.items():
        declared = str(report.get(key) or "")
        if not declared:
            continue
        checks.append(key)
        if declared != value:
            return {"current": False, "reason": f"{key} is stale", "checks": checks}
    source_fingerprint = str(report.get("source_fingerprint") or "")
    artifact_source = str(report.get("artifact_source_fingerprint") or "")
    if source_fingerprint and artifact_source and source_fingerprint != artifact_source:
        return {"current": False, "reason": "source_fingerprint is stale", "checks": [*checks, "source_fingerprint"]}
    return {"current": True, "reason": "", "checks": checks}
