from __future__ import annotations

from typing import Any


# 所有已知 schema 版本注册表
SCHEMA_REGISTRY: dict[str, str] = {
    "deck_workspace.v1": "workspace_manifest.json",
    "deck_event.v1": "events.jsonl",
    "deck_next_step.v1": "next_step.json",
    "deck_preview_manifest.v1": "preview_manifest.json",
    "deck_consulting_judgments.v1": "consulting_judgments.json",
    "deck_claim_evidence_graph.v1": "claim_evidence_graph.json",
    "deck_asset_graph.v1": "asset_graph.json",
    "deck_quality_override.v1": "quality_overrides.json",
    "deck_delivery_outcome.v1": "delivery_outcome.json",
    "deck_connector_import.v1": "connector_import.json",
}


def schema_version(tag: str) -> str:
    """返回规范 schema version 字符串。

    >>> schema_version("deck_workspace.v1")
    'deck_workspace.v1'
    """
    return tag


def ensure_schema_version(data: dict[str, Any], expected_tag: str) -> dict[str, Any]:
    """确保 dict 有正确的 schema_version。

    如果没有 schema_version 字段，补上 expected_tag。
    如果有但不同，保留原值（不覆盖用户数据）。
    返回 data（可能是修改后的原 dict）。
    """
    if "schema_version" not in data:
        data["schema_version"] = expected_tag
    return data


def check_schema_version(data: dict[str, Any], expected_tag: str) -> bool:
    """检查 schema_version 是否匹配。

    无 schema_version 时返回 True（legacy 兼容）。
    """
    actual = data.get("schema_version")
    if actual is None:
        return True  # legacy 兼容
    return actual == expected_tag


def read_with_schema(
    data: dict[str, Any],
    expected_tag: str,
) -> dict[str, Any]:
    """读取 JSON dict 并确保 schema 兼容。

    - 无 schema_version 时按 legacy 解析，补上 expected_tag。
    - 有 schema_version 但不匹配时抛 SchemaVersionError。
    - 匹配时直接返回。
    """
    actual = data.get("schema_version")
    if actual is None:
        data["schema_version"] = expected_tag
        return data
    if actual != expected_tag:
        raise SchemaVersionError(
            f"Schema version mismatch: expected {expected_tag}, got {actual}"
        )
    return data


def write_with_schema(
    data: dict[str, Any],
    tag: str,
) -> dict[str, Any]:
    """写入前确保 schema_version 已设置。"""
    data["schema_version"] = tag
    return data


class SchemaVersionError(ValueError):
    """Schema 版本不匹配错误。"""
    pass
