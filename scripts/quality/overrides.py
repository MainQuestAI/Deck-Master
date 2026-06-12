from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_quality_override.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def overrides_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / "quality_reports" / "overrides.json"


def create_override(
    run_dir: str | Path,
    finding_id: str,
    severity: str,
    reason: str,
    approver: str,
    *,
    scope: str = "client_export",
    actor: str = "user",
    expires_days: int = 14,
    run_id: str = "",
) -> dict[str, Any]:
    """创建 quality override。

    政策：
    - P0 不能 override 到 client export
    - P1 override 必须有 reason、approver、expires_at
    - P1 override 最长期限 14 天
    """
    if severity == "P0":
        raise ValueError("P0 findings cannot be overridden for client export.")
    if not reason:
        raise ValueError("Override reason is required.")
    if not approver:
        raise ValueError("Override approver is required.")
    if expires_days > 14:
        raise ValueError("P1 override maximum duration is 14 days.")

    overrides = load_overrides(run_dir)
    override_id = f"override_{len(overrides) + 1:03d}"

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=expires_days)).isoformat()

    override = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "override_id": override_id,
        "run_id": run_id or Path(run_dir).name,
        "target_type": "quality_finding",
        "target_id": finding_id,
        "severity": severity,
        "scope": scope,
        "reason": reason,
        "actor": actor,
        "approver": approver,
        "expires_at": expires_at,
        "status": "active",
    }

    overrides.append(override)
    save_overrides(run_dir, overrides)

    # 写 typed event
    try:
        from runtime.events import append_typed_event
        append_typed_event(
            run_dir, "manual_action", "override.create",
            f"Override created for finding {finding_id}: {reason[:50]}",
            refs=["quality_reports/overrides.json"],
            payload={"override_id": override_id, "severity": severity},
        )
    except Exception:
        pass

    return override


def revoke_override(
    run_dir: str | Path,
    override_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """撤销 override。"""
    overrides = load_overrides(run_dir)
    for override in overrides:
        if override.get("override_id") == override_id:
            if override.get("status") != "active":
                raise ValueError(f"Override {override_id} is not active.")
            override["status"] = "revoked"
            override["revoked_at"] = utc_now()
            override["revoke_reason"] = reason
            save_overrides(run_dir, overrides)

            try:
                from runtime.events import append_typed_event
                append_typed_event(
                    run_dir, "manual_action", "override.revoke",
                    f"Override {override_id} revoked: {reason[:50]}",
                    refs=["quality_reports/overrides.json"],
                )
            except Exception:
                pass

            return override

    raise ValueError(f"Override not found: {override_id}")


def load_overrides(run_dir: str | Path) -> list[dict[str, Any]]:
    path = overrides_path(run_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        return []


def save_overrides(run_dir: str | Path, overrides: list[dict]) -> Path:
    path = overrides_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(overrides, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def list_active_overrides(run_dir: str | Path) -> list[dict[str, Any]]:
    """列出所有 active 的 overrides。"""
    overrides = load_overrides(run_dir)
    now = datetime.now(timezone.utc)
    active = []
    for o in overrides:
        if o.get("status") != "active":
            continue
        # 检查过期
        expires = o.get("expires_at", "")
        if expires:
            try:
                exp_dt = datetime.fromisoformat(expires)
                if exp_dt < now:
                    o["status"] = "expired"
                    continue
            except ValueError:
                pass
        active.append(o)
    return active


def has_active_override(run_dir: str | Path, finding_id: str) -> bool:
    """检查某个 finding 是否有 active override。"""
    active = list_active_overrides(run_dir)
    return any(o.get("target_id") == finding_id for o in active)
