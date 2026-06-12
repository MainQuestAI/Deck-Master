from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_connector_import.v1"

# 敏感来源类型
HIGH_SENSITIVITY_KINDS = {
    "credential", "password", "api_key", "financial_raw", "salary",
}


def validate_import_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """验证导入 manifest。

    检查：
    - schema_version 匹配
    - source_files 列表有效
    - 未 redaction 的高敏来源被拒绝
    - 不调用外部实时 API
    """
    errors = []
    warnings = []

    # schema check
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"Invalid schema_version: expected {SCHEMA_VERSION}")

    # source system
    source_system = manifest.get("source_system", "")
    if not source_system:
        errors.append("source_system is required")

    # source files
    source_files = manifest.get("source_files", [])
    if not isinstance(source_files, list):
        errors.append("source_files must be a list")
    else:
        for i, sf in enumerate(source_files):
            if not isinstance(sf, dict):
                errors.append(f"source_files[{i}] must be an object")
                continue
            if not sf.get("path"):
                errors.append(f"source_files[{i}].path is required")
            if not sf.get("source_kind"):
                warnings.append(f"source_files[{i}].source_kind is recommended")

    # redaction check
    redaction_status = manifest.get("redaction_status", "")
    import_policy = manifest.get("import_policy", {})
    allow_sensitive = import_policy.get("allow_sensitive_raw_text", False)

    for sf in source_files if isinstance(source_files, list) else []:
        if not isinstance(sf, dict):
            continue
        kind = sf.get("source_kind", "")
        if kind in HIGH_SENSITIVITY_KINDS and redaction_status != "reviewed" and not allow_sensitive:
            errors.append(f"High-sensitivity source '{kind}' requires redaction_status=reviewed")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "source_file_count": len(source_files) if isinstance(source_files, list) else 0,
    }


def import_to_context_manifest(
    manifest: dict[str, Any],
    *,
    base_dir: str | Path = "",
) -> dict[str, Any]:
    """将导入 manifest 转换为 context manifest 格式。

    不调用外部 API，只处理本地文件。
    """
    validation = validate_import_manifest(manifest)
    if not validation["valid"]:
        raise ValueError(f"Invalid import manifest: {'; '.join(validation['errors'])}")

    sources = []
    for i, sf in enumerate(manifest.get("source_files", [])):
        source = {
            "source_id": f"imported_{i+1:03d}",
            "kind": sf.get("source_kind", "unknown"),
            "name": sf.get("name", Path(sf.get("path", "")).name),
            "path": sf.get("path", ""),
            "sha256": sf.get("sha256", ""),
            "imported_from": manifest.get("source_system", ""),
            "import_export_id": manifest.get("source_export_id", ""),
        }

        # 尝试读取本地文件计算 hash
        if base_dir and not source["sha256"]:
            file_path = Path(base_dir) / sf.get("path", "")
            if file_path.exists():
                h = hashlib.sha256()
                with file_path.open("rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                source["sha256"] = h.hexdigest()

                # 尝试读取摘要
                try:
                    text = file_path.read_text(encoding="utf-8")
                    source["summary"] = text[:500]
                    source["excerpt"] = text[:200]
                except (UnicodeDecodeError, PermissionError):
                    pass

        sources.append(source)

    return {
        "schema_version": "deck_context_manifest.v1",
        "import_source": manifest.get("source_system", ""),
        "import_export_id": manifest.get("source_export_id", ""),
        "sources": sources,
        "summary": f"Imported {len(sources)} files from {manifest.get('source_system', 'unknown')}",
    }
