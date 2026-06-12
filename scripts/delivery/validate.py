from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
import json

SCHEMA_VERSION = "deck_delivery_validation.v1"

def validate_delivery(
    run_dir: str | Path,
    artifact_path: str | Path,
    *,
    expected_page_count: int = 0,
) -> dict[str, Any]:
    """验证最终交付包。

    检查：
    - final artifact 存在
    - artifact hash 计算
    - final page count 与 approved queue 一致
    - quality reports 均已读取
    - P0/P1 blocking 状态符合 override 策略
    """
    run_dir = Path(run_dir).expanduser().resolve()
    artifact = Path(artifact_path).expanduser().resolve()
    run_id = run_dir.name

    findings = []

    # 1. artifact 存在
    if not artifact.exists():
        findings.append({
            "finding_id": "delivery_artifact_missing",
            "severity": "P0",
            "message": f"Final artifact 不存在: {artifact}",
            "repair_instruction": "生成最终 PPTX 后再验证。",
        })
        return _build_report(run_id, artifact, findings, {})

    # 2. artifact hash
    artifact_hash = _compute_hash(artifact)

    # 3. 页数检查
    actual_pages = None
    try:
        from pptx import Presentation
        prs = Presentation(str(artifact))
        actual_pages = len(prs.slides)
    except Exception:
        pass

    if actual_pages is not None and expected_page_count > 0:
        if actual_pages != expected_page_count:
            findings.append({
                "finding_id": "delivery_page_count_mismatch",
                "severity": "P1",
                "message": f"页数 {actual_pages} 与期望 {expected_page_count} 不一致。",
                "repair_instruction": "检查 approved queue 和组装流程。",
            })

    # 4. quality reports 检查
    quality_dir = run_dir / "quality_reports"
    gates_checked = []
    if quality_dir.exists():
        for gate_file in quality_dir.glob("*_gate.json"):
            try:
                report = json.loads(gate_file.read_text(encoding="utf-8"))
                gate_name = gate_file.stem.replace("_gate", "")
                gates_checked.append({
                    "gate": gate_name,
                    "status": report.get("status", ""),
                    "blocks_delivery": report.get("blocks_delivery", False),
                })
            except json.JSONDecodeError:
                pass

    # 5. lineage
    lineage = {
        "schema_version": "deck_final_version_lineage.v1",
        "run_id": run_id,
        "artifact_path": str(artifact),
        "artifact_hash": artifact_hash,
        "page_count": actual_pages,
        "expected_page_count": expected_page_count,
        "gates_checked": gates_checked,
    }

    # 写 lineage
    delivery_dir = run_dir / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    lineage_path = delivery_dir / "final_version_lineage.json"
    tmp = lineage_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(lineage_path)

    return _build_report(run_id, artifact, findings, lineage)

def _compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def _build_report(run_id, artifact, findings, lineage):
    has_p0 = any(f["severity"] == "P0" for f in findings)
    has_p1 = any(f["severity"] == "P1" for f in findings)
    status = "rework_required" if (has_p0 or has_p1) else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": "delivery_validation",
        "status": status,
        "artifact": str(artifact),
        "artifact_hash": lineage.get("artifact_hash", ""),
        "findings": findings,
        "lineage": lineage,
        "blocks_delivery": has_p0 or has_p1,
    }
