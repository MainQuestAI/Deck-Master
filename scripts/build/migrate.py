"""SC-1.1 batch-3: build migrate --dry-run (old-run detection, no mutation)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_build_migration_plan.v1"


def build_migration_plan(run_dir: str | Path) -> dict[str, Any]:
    """Dry-run only (SC-1.1 ND-05, review batch 3): detect an old run's
    engine traces and produce a migration plan. Read-only — apply/rollback
    are explicitly out of scope this round; nothing is mutated."""

    root = Path(run_dir).expanduser().resolve()
    run_kind = _detect_run_kind(root)
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": root.name,
        "run_dir": str(root),
        "detected": run_kind,
        "dry_run": True,
        "target_profile": "native",
        "actions": [],
        "rollback": "not implemented in this iteration (dry-run only)",
        "notes": [],
    }
    if run_kind == "native":
        plan["notes"].append("run is already on the native route; no migration needed")
        return plan
    if run_kind == "high_density":
        plan["actions"] = [
            {"kind": "rebuild_route", "detail": "persist build/route.json with engine_id=deck_native, density=high"},
            {"kind": "recompile", "detail": "re-run build run --profile native; approved SVGs/scenes/locks are reused by the native kernel"},
            {"kind": "reapprove", "detail": "the compiled deck is a NEW artifact; gates and the final artifact approval must re-run for the new version"},
        ]
        plan["notes"].append("old high-density artifacts stay read-only; nothing is deleted or overwritten by the dry run")
        return plan
    if run_kind == "legacy_ppt_master":
        plan["actions"] = [
            {"kind": "verify_binding", "detail": "legacy route requires the PPT Master binding to stay valid until migration completes"},
            {"kind": "rebuild_route", "detail": "persist build/route.json with engine_id=deck_native"},
            {"kind": "reproduce", "detail": "page packages must be approved (ready_for_build) before the native build; run the producer if missing"},
            {"kind": "recompile", "detail": "build run --profile native through the built-in engine"},
            {"kind": "reapprove", "detail": "gates + final artifact approval re-run for the new artifact; the old approved file and its hash are preserved"},
        ]
        return plan
    plan["detected"] = "unknown"
    plan["notes"].append("no engine traces found; treat as read-only and report — never guess a route")
    return plan


def _detect_run_kind(root: Path) -> str:
    if (root / "build" / "route.json").exists():
        route = json.loads((root / "build" / "route.json").read_text(encoding="utf-8"))
        engine = str(route.get("engine_id") or "")
        if engine == "legacy_ppt_master":
            return "legacy_ppt_master"
        return "native"
    if (root / "high_density_build" / "status.json").exists():
        return "high_density"
    if (root / "build" / "render_request.json").exists():
        return "legacy_ppt_master"
    if (root / "render_results" / "render_result.json").exists():
        result = json.loads((root / "render_results" / "render_result.json").read_text(encoding="utf-8"))
        if str(result.get("tool") or "") == "deck_native":
            return "native"
    return "unknown"
