from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from runtime.final_approval import final_approval_clearance, write_final_artifact_approval  # noqa: E402


def _seed_ready_run(root: Path) -> tuple[Path, str]:
    artifact = root / "build" / "deck.pptx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"approved deck")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    delivery = root / "delivery"
    delivery.mkdir()
    (delivery / "final_readiness.json").write_text(
        json.dumps(
            {
                "schema_version": "deck_final_readiness.v1",
                "run_id": root.name,
                "ready": True,
                "status": "ready",
                "computed_at": "2026-07-13T00:00:00+00:00",
                "final_artifact": {"path": "build/deck.pptx", "hash": digest},
            }
        ),
        encoding="utf-8",
    )
    return artifact, digest


def _approval(root: Path) -> dict:
    payload = {
        "run_id": root.name,
        "approval_id": "approval_final",
        "handoff_id": "handoff_review_export",
        "decision": "approved",
        "actor": {"id": "boss", "role": "approver"},
        "decided_at": "2026-07-13T00:01:00+00:00",
        "artifact_binding": {"output_fingerprint": "abc", "artifacts": []},
        "to_stage": "client_export",
    }
    approval_dir = root / "workflow" / "approvals"
    approval_dir.mkdir(parents=True, exist_ok=True)
    (approval_dir / "approval_final.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_final_approval_binds_current_artifact(tmp_path: Path) -> None:
    _seed_ready_run(tmp_path)
    write_final_artifact_approval(tmp_path, _approval(tmp_path))
    assert final_approval_clearance(tmp_path)["ready"] is True


def test_final_approval_is_stale_after_artifact_changes(tmp_path: Path) -> None:
    artifact, _digest = _seed_ready_run(tmp_path)
    write_final_artifact_approval(tmp_path, _approval(tmp_path))
    artifact.write_bytes(b"changed after approval")
    clearance = final_approval_clearance(tmp_path)
    assert clearance["ready"] is False
    assert "stale" in clearance["reason"]


def test_final_approval_rejects_missing_approval(tmp_path: Path) -> None:
    _seed_ready_run(tmp_path)
    clearance = final_approval_clearance(tmp_path)
    assert clearance["ready"] is False
    assert "missing" in clearance["reason"]
