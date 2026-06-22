from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_artifact_validation.v1"

KNOWN_MEDIA_TYPES = {
    "deck_html": "text/html",
    "page_html": "text/html",
    "html_fragment": "text/html",
    "deck_pdf": "application/pdf",
    "page_png": "image/png",
    "page_jpeg": "image/jpeg",
    "page_svg": "image/svg+xml",
    "deck_pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "page_pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "artifact_manifest": "application/json",
    "quality_report": "application/json",
    "source_snapshot": "application/json",
}

PLACEHOLDER_TOKENS = (
    b"deck-master bundled generation placeholder",
    b"deck-master bundled generation preview",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_id(artifact: dict[str, Any], index: int) -> str:
    return str(artifact.get("artifact_id") or artifact.get("path") or f"artifact_{index:03d}")


def _safe_run_path(run_dir: Path, path_value: Any) -> tuple[Path | None, str | None]:
    text = str(path_value or "").strip()
    if not text:
        return None, "path is required."
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        return None, f"path must be run-relative: {text}"
    resolved = (run_dir / path).resolve()
    root = str(run_dir.resolve())
    if str(resolved) != root and not str(resolved).startswith(root + os.sep):
        return None, f"path escapes run directory: {text}"
    return resolved, None


def _first_bytes(path: Path, limit: int = 4096) -> bytes:
    with path.open("rb") as fh:
        return fh.read(limit)


def _looks_like_html(data: bytes) -> bool:
    stripped = data.lstrip().lower()
    return stripped.startswith(b"<!doctype html") or stripped.startswith(b"<html") or b"<html" in stripped[:512]


def _looks_like_fragment(data: bytes) -> bool:
    stripped = data.lstrip()
    return stripped.startswith(b"<") and b">" in stripped[:512]


def _looks_like_svg(data: bytes) -> bool:
    stripped = data.lstrip().lower()
    return stripped.startswith(b"<svg") or stripped.startswith(b"<?xml") and b"<svg" in stripped[:1024]


def _magic_error(path: Path, kind: str, media_type: str) -> str:
    data = _first_bytes(path)
    if kind in {"deck_html", "page_html"} or media_type == "text/html":
        if not _looks_like_html(data):
            return "html artifact does not look like HTML."
    if kind == "html_fragment":
        if not _looks_like_fragment(data):
            return "html fragment does not look like markup."
    if kind == "deck_pdf" or media_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            return "pdf artifact has invalid signature."
    if kind == "page_png" or media_type == "image/png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png artifact has invalid signature."
    if kind == "page_jpeg" or media_type == "image/jpeg":
        if not data.startswith(b"\xff\xd8\xff"):
            return "jpeg artifact has invalid signature."
    if kind == "page_svg" or media_type == "image/svg+xml":
        if not _looks_like_svg(data):
            return "svg artifact has invalid signature."
    if kind in {"deck_pptx", "page_pptx"} or media_type.endswith("presentationml.presentation"):
        if not zipfile.is_zipfile(path):
            return "pptx artifact is not a zip package."
        with zipfile.ZipFile(path) as pptx:
            names = set(pptx.namelist())
        if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
            return "pptx artifact is missing required package parts."
    if kind in {"artifact_manifest", "quality_report", "source_snapshot"} or media_type == "application/json":
        stripped = data.lstrip()
        if not (stripped.startswith(b"{") or stripped.startswith(b"[")):
            return "json artifact has invalid signature."
    return ""


def _placeholder_error(path: Path) -> str:
    data = _first_bytes(path)
    if any(token in data for token in PLACEHOLDER_TOKENS):
        return "artifact points to bundled placeholder content."
    return ""


def validate_artifact_descriptor(
    run_dir: str | Path,
    artifact: dict[str, Any],
    *,
    index: int = 1,
    expected_source_fingerprint: str | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    artifact_id = _artifact_id(artifact, index)
    kind = str(artifact.get("kind") or "")
    media_type = str(artifact.get("media_type") or "")
    resolved, path_error = _safe_run_path(root, artifact.get("path"))
    if path_error:
        errors.append(path_error)
    if not kind:
        errors.append("kind is required.")
    if not media_type:
        errors.append("media_type is required.")
    expected_media_type = KNOWN_MEDIA_TYPES.get(kind)
    if expected_media_type and media_type and media_type != expected_media_type:
        errors.append(f"media_type mismatch: got {media_type}, expected {expected_media_type}.")
    if artifact.get("validation_status") in {"invalid", "missing", "stale"}:
        errors.append(f"validation_status is {artifact.get('validation_status')}.")
    artifact_source_fingerprint = str(artifact.get("source_fingerprint") or "")
    if expected_source_fingerprint and artifact_source_fingerprint and artifact_source_fingerprint != expected_source_fingerprint:
        errors.append("artifact source_fingerprint is stale.")

    if resolved is not None:
        if not resolved.exists() or not resolved.is_file():
            errors.append(f"path not found: {artifact.get('path')}")
        else:
            actual_size = resolved.stat().st_size
            if actual_size <= 0:
                errors.append("artifact is empty.")
            declared_size = artifact.get("bytes")
            if not isinstance(declared_size, int) or declared_size < 1:
                errors.append("bytes must be a positive integer.")
            elif declared_size != actual_size:
                errors.append(f"bytes mismatch: got {declared_size}, expected {actual_size}.")
            actual_sha = sha256_file(resolved)
            declared_sha = str(artifact.get("sha256") or "")
            if not declared_sha:
                errors.append("sha256 is required.")
            elif declared_sha != actual_sha:
                errors.append("sha256 mismatch.")
            magic_error = _magic_error(resolved, kind, media_type)
            if magic_error:
                errors.append(magic_error)
            placeholder_error = _placeholder_error(resolved)
            if placeholder_error:
                errors.append(placeholder_error)

    return {
        "artifact_id": artifact_id,
        "path": str(artifact.get("path") or ""),
        "kind": kind,
        "media_type": media_type,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def validate_artifact_manifest(
    run_dir: str | Path,
    manifest: dict[str, Any],
    *,
    expected_source_fingerprint: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(manifest, dict):
        return {
            "schema_version": SCHEMA_VERSION,
            "valid": False,
            "errors": ["manifest must be a JSON object."],
            "warnings": [],
            "artifacts": [],
        }
    manifest_fingerprint = str(manifest.get("source_fingerprint") or "")
    if expected_source_fingerprint and manifest_fingerprint != expected_source_fingerprint:
        errors.append("manifest source_fingerprint is stale.")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty list.")
        artifacts = []

    artifact_results: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, dict):
            artifact_results.append(
                {
                    "artifact_id": f"artifact_{index:03d}",
                    "path": "",
                    "kind": "",
                    "media_type": "",
                    "valid": False,
                    "errors": ["artifact must be an object."],
                    "warnings": [],
                }
            )
            continue
        artifact_results.append(
            validate_artifact_descriptor(
                run_dir,
                artifact,
                index=index,
                expected_source_fingerprint=manifest_fingerprint or expected_source_fingerprint,
            )
        )

    for result in artifact_results:
        if not result.get("valid"):
            errors.extend(f"{result.get('artifact_id')}: {error}" for error in result.get("errors", []))
        warnings.extend(f"{result.get('artifact_id')}: {warning}" for warning in result.get("warnings", []))

    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "artifact_count": len(artifact_results),
        "artifacts": artifact_results,
    }
