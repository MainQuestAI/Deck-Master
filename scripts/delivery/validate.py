from __future__ import annotations
import hashlib
import os
from pathlib import Path
from typing import Any
import json
import zipfile

from runtime.artifact_validator import sha256_file, validate_artifact_descriptor, validate_artifact_manifest
from quality.gate_freshness import artifact_identity, report_currentity
from quality.gate_policy import resolve_required_gates

SCHEMA_VERSION = "deck_delivery_validation.v1"
LINEAGE_SCHEMA_VERSION = "deck_final_version_lineage.v1"
BUILD_MANIFEST = Path("build") / "build_manifest.json"
ARTIFACT_MANIFEST = Path("build") / "artifact_manifest.json"
RENDER_RESULT = Path("render_results") / "render_result.json"
BLOCKING_STATUSES = {"rework_required", "failed", "blocked"}

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
    fixture_policy = _is_fixture_policy(run_dir)

    findings = []

    artifact_inside_run = _is_inside_run(run_dir, artifact)
    artifact_rel = str(artifact.relative_to(run_dir)) if artifact_inside_run else ""

    # 1. artifact 存在并且必须在 run 内
    if not artifact_inside_run:
        findings.append({
            "finding_id": "delivery_artifact_path_unsafe",
            "severity": "P0",
            "message": f"Final artifact must stay inside run directory: {artifact}",
            "repair_instruction": "把最终交付产物复制到当前 run 目录后再验证。",
        })
        return _build_report(run_id, artifact, findings, {}, artifact_root=run_dir)

    if not artifact.exists() or not artifact.is_file():
        findings.append({
            "finding_id": "delivery_artifact_missing",
            "severity": "P0",
            "message": f"Final artifact 不存在: {artifact}",
            "repair_instruction": "生成最终 PPTX 后再验证。",
        })
        return _build_report(run_id, artifact, findings, {}, artifact_root=run_dir)

    # 2. artifact hash
    artifact_hash = _compute_hash(artifact)
    descriptor = _artifact_descriptor(run_dir, artifact, artifact_rel)
    artifact_validation = validate_artifact_descriptor(
        run_dir,
        descriptor,
        allow_contract_smoke=fixture_policy,
        allow_non_client_deliverable=fixture_policy,
    )
    if not artifact_validation.get("valid"):
        findings.append({
            "finding_id": "delivery_artifact_invalid",
            "severity": "P0",
            "message": "Final artifact validation failed: " + "; ".join(artifact_validation.get("errors", [])),
            "repair_instruction": "重新生成最终 artifact，并确保格式、大小和 checksum 都有效。",
        })

    # 3. 页数检查
    actual_pages, page_count_error = _page_count(artifact)
    if page_count_error:
        findings.append({
            "finding_id": "delivery_artifact_parse_failed",
            "severity": "P0",
            "message": page_count_error,
            "repair_instruction": "重新生成可解析的最终交付文件。",
        })

    if actual_pages is not None and expected_page_count > 0:
        if actual_pages != expected_page_count:
            findings.append({
                "finding_id": "delivery_page_count_mismatch",
                "severity": "P1",
                "message": f"页数 {actual_pages} 与期望 {expected_page_count} 不一致。",
                "repair_instruction": "检查 approved queue 和组装流程。",
            })

    build_manifest = _read_json(run_dir / BUILD_MANIFEST)
    render_result = _read_json(run_dir / RENDER_RESULT)
    request = _read_json(run_dir / "request.json")
    run_mode = str(request.get("run_mode") or "").strip().lower()
    builder_profile = str(build_manifest.get("builder_profile") or "").strip().lower()
    output_profile = str(build_manifest.get("output_profile") or "").strip().lower()
    governance_enabled = bool(
        request or build_manifest or render_result or (run_dir / "high_density_build" / "status.json").exists()
    )

    # 4. quality reports 检查
    quality_dir = run_dir / "quality_reports"
    gates_checked: list[dict[str, Any]] = []
    quality_reports: list[dict[str, Any]] = []
    if quality_dir.exists():
        for gate_file in quality_dir.glob("*_gate.json"):
            try:
                report = json.loads(gate_file.read_text(encoding="utf-8"))
                gate_name = gate_file.stem.replace("_gate", "")
                report_for_currentity = report if report.get("gate") else {**report, "gate": gate_name}
                currentity = report_currentity(run_dir, report_for_currentity, artifact)
                report = {**report, "_gate_name": str(report.get("gate") or gate_name), "_report_file": gate_file.name}
                quality_reports.append(report)
                gates_checked.append({
                    "gate": gate_name,
                    "status": report.get("status", ""),
                    "blocks_delivery": report.get("blocks_delivery", False),
                    "current": bool(currentity.get("current")),
                    "currentity": str(currentity.get("status") or ("current" if currentity.get("current") else "stale")),
                    "stale_reason": str(currentity.get("reason") or ""),
                })
            except (json.JSONDecodeError, OSError):
                gates_checked.append({
                    "gate": gate_file.stem.replace("_gate", ""),
                    "status": "parse_failed",
                    "blocks_delivery": True,
                    "current": False,
                    "currentity": "missing",
                })
                findings.append({
                    "finding_id": "delivery_gate_parse_failed",
                    "severity": "P1",
                    "message": f"Quality gate JSON parse failed: {gate_file}",
                    "repair_instruction": "修复 quality gate JSON 后再验证交付。",
                })

    governance_policy: dict[str, Any] = {}
    if governance_enabled:
        policy_reports = [
            report
            for report in quality_reports
            if str(report.get("_gate_name") or "").strip().lower().replace("-", "_") != "delivery_validation"
        ]
        governance_policy = resolve_required_gates(
            run_dir,
            artifact,
            builder_profile=builder_profile,
            output_profile=output_profile or ("production_pptx" if artifact.suffix.lower() == ".pptx" else ""),
            run_mode=run_mode,
            reports=policy_reports,
            include_non_required_blockers=True,
        )
        existing_ids = {str(item.get("finding_id") or "") for item in findings if isinstance(item, dict)}
        for gate in governance_policy.get("missing_required_gates") or []:
            if run_mode in {"fixture", "dev"}:
                continue
            finding_id = f"delivery_required_gate_{gate}"
            if finding_id in existing_ids:
                continue
            findings.append({
                "finding_id": finding_id,
                "severity": "P1",
                "message": f"Required quality gate {gate} is missing, stale, or unbound for the current artifact.",
                "repair_instruction": f"重新运行当前 artifact 的 {gate} quality gate，并写入 path + SHA-256 binding。",
            })
            existing_ids.add(finding_id)
        for item in governance_policy.get("current_blockers") or []:
            if not isinstance(item, dict):
                continue
            finding_id = str(item.get("finding_id") or item.get("code") or item.get("message") or "")
            if finding_id and finding_id in existing_ids:
                continue
            findings.append({
                "finding_id": finding_id or "delivery_required_gate_blocking",
                "severity": str(item.get("severity") or "P1").upper(),
                "message": str(item.get("message") or f"{item.get('_gate_name') or 'quality'} gate blocks delivery."),
                "repair_instruction": str(item.get("repair_instruction") or "处理当前质量门阻断项后重新验证交付。"),
                **({"page_id": item["page_id"]} if item.get("page_id") else {}),
            })
            if finding_id:
                existing_ids.add(finding_id)

    artifact_manifest, artifact_manifest_validation = _validate_build_artifacts(
        run_dir,
        findings,
        allow_contract_smoke=fixture_policy,
        allow_non_client_deliverable=fixture_policy,
    )
    source_fingerprint = str(
        (render_result or {}).get("source_fingerprint")
        or (artifact_manifest or {}).get("source_fingerprint")
        or (build_manifest or {}).get("source_fingerprint")
        or ""
    )
    _check_source_fingerprint_consistency(build_manifest, artifact_manifest, render_result, findings)

    # 5. lineage
    lineage = {
        "schema_version": LINEAGE_SCHEMA_VERSION,
        "run_id": run_id,
        "artifact_path": str(artifact),
        "artifact_run_relative": artifact_rel,
        "artifact_hash": artifact_hash,
        "page_count": actual_pages,
        "expected_page_count": expected_page_count,
        "source_fingerprint": source_fingerprint,
        "artifact_validation": artifact_validation,
        "artifact_manifest_validation": artifact_manifest_validation,
        "build_manifest": str(BUILD_MANIFEST) if build_manifest else "",
        "artifact_manifest": str(ARTIFACT_MANIFEST) if artifact_manifest else "",
        "render_result": str(RENDER_RESULT) if render_result else "",
        "gates_checked": gates_checked,
        "required_gate_policy": governance_policy,
    }

    # 写 lineage
    delivery_dir = run_dir / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    lineage_path = delivery_dir / "final_version_lineage.json"
    tmp = lineage_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(lineage_path)

    return _build_report(run_id, artifact, findings, lineage, artifact_root=run_dir, governance_policy=governance_policy)

def _compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def _is_inside_run(run_dir: Path, path: Path) -> bool:
    try:
        resolved = path.resolve()
        root = run_dir.resolve()
        return str(resolved) == str(root) or str(resolved).startswith(str(root) + os.sep)
    except OSError:
        return False

def _kind_and_media(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "deck_html", "text/html"
    if suffix == ".pdf":
        return "deck_pdf", "application/pdf"
    if suffix == ".png":
        return "page_png", "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "page_jpeg", "image/jpeg"
    if suffix == ".svg":
        return "page_svg", "image/svg+xml"
    if suffix == ".pptx":
        return "deck_pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if suffix == ".json":
        return "quality_report", "application/json"
    return "asset_bundle", "application/octet-stream"

def _artifact_descriptor(run_dir: Path, artifact: Path, artifact_rel: str) -> dict[str, Any]:
    kind, media_type = _kind_and_media(artifact)
    return {
        "artifact_id": f"final_{kind}",
        "kind": kind,
        "path": artifact_rel,
        "media_type": media_type,
        "sha256": sha256_file(artifact),
        "bytes": artifact.stat().st_size,
        "validation_status": "validated",
        "editability": "native" if kind in {"deck_html", "deck_pptx"} else "flat_image",
    }

def _page_count(artifact: Path) -> tuple[int | None, str]:
    if artifact.suffix.lower() != ".pptx":
        return None, ""
    try:
        with zipfile.ZipFile(artifact) as pptx:
            slides = [
                name
                for name in pptx.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ]
    except (OSError, zipfile.BadZipFile) as exc:
        return None, f"Final PPTX cannot be parsed: {exc}"
    if not slides:
        return None, "Final PPTX contains no slides."
    return len(slides), ""

def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}

def _is_fixture_policy(run_dir: Path) -> bool:
    request = _read_json(run_dir / "request.json")
    mode = str(request.get("run_mode") or "production").strip().lower()
    return mode in {"fixture", "dev"}

def _validate_build_artifacts(
    run_dir: Path,
    findings: list[dict[str, Any]],
    *,
    allow_contract_smoke: bool = False,
    allow_non_client_deliverable: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact_manifest = _read_json(run_dir / ARTIFACT_MANIFEST)
    if not artifact_manifest:
        return {}, {}
    validation = validate_artifact_manifest(
        run_dir,
        artifact_manifest,
        expected_source_fingerprint=str(artifact_manifest.get("source_fingerprint") or ""),
        allow_contract_smoke=allow_contract_smoke,
        allow_non_client_deliverable=allow_non_client_deliverable,
    )
    if not validation.get("valid"):
        findings.append({
            "finding_id": "delivery_artifact_manifest_invalid",
            "severity": "P0",
            "message": "Artifact manifest validation failed: " + "; ".join(validation.get("errors", [])),
            "repair_instruction": "重新生成 build artifacts 后再验证交付。",
        })
    return artifact_manifest, validation

def _check_source_fingerprint_consistency(
    build_manifest: dict[str, Any],
    artifact_manifest: dict[str, Any],
    render_result: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    fingerprints = {
        "build_manifest": str(build_manifest.get("source_fingerprint") or ""),
        "artifact_manifest": str(artifact_manifest.get("source_fingerprint") or ""),
        "render_result": str(render_result.get("source_fingerprint") or ""),
    }
    present = {key: value for key, value in fingerprints.items() if value}
    if len(set(present.values())) > 1:
        findings.append({
            "finding_id": "delivery_source_fingerprint_stale",
            "severity": "P0",
            "message": f"Source fingerprint mismatch across delivery lineage: {present}",
            "repair_instruction": "用当前 preview/build 输入重新生成 artifact manifest 和 render result。",
        })

def _build_report(run_id, artifact, findings, lineage, *, artifact_root: Path | None = None, governance_policy: dict[str, Any] | None = None):
    has_p0 = any(f["severity"] == "P0" for f in findings)
    has_p1 = any(f["severity"] == "P1" for f in findings)
    status = "rework_required" if (has_p0 or has_p1) else "pass"
    report = {
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
    if artifact_root is not None:
        report.update(artifact_identity(artifact_root, artifact))
    if governance_policy:
        report["required_gate_policy"] = governance_policy
    return report
