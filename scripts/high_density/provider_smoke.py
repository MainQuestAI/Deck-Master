from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .blueprint import load_blueprint_manifest, safe_run_path
from .contracts import ContractError, assert_valid, assert_v2, read_json, run_relative, sha256_bytes, sha256_file, sha256_json, utc_now, write_json


class ProviderSmokeError(ContractError):
    pass


def _hash_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _timestamp(value: Any, *, field: str, page_id: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderSmokeError(f"provider smoke {field} timestamp is invalid on page {page_id}") from exc
    if parsed.tzinfo is None:
        raise ProviderSmokeError(f"provider smoke {field} timestamp must include a timezone on page {page_id}")
    return parsed


def _artifact_ref(root: Path, page: dict[str, Any], key: str) -> dict[str, str]:
    value = page.get(key)
    if not isinstance(value, dict):
        raise ProviderSmokeError(f"completed high-density page is missing artifact ref: {key}")
    path = safe_run_path(root, str(value.get("path") or ""))
    actual_sha = sha256_file(path)
    if str(value.get("sha256") or "") != actual_sha:
        raise ProviderSmokeError(f"completed high-density artifact hash is stale: {key}")
    return {"path": run_relative(root, path), "sha256": actual_sha}


def build_provider_smoke_evidence(run_dir: str | Path, *, page_id: str = "", output: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    request = read_json(root / "request.json")
    run_mode = str(request.get("run_mode") or "")
    if run_mode not in {"production", "benchmark"}:
        raise ProviderSmokeError("fresh provider smoke requires production or benchmark run mode")
    manifest_path = root / "high_density_build" / "high_density_manifest.json"
    if not manifest_path.exists():
        raise ProviderSmokeError("provider smoke requires a completed high-density manifest")
    manifest = read_json(manifest_path)
    assert_v2("high_density_manifest", manifest)
    if manifest.get("status") != "completed":
        raise ProviderSmokeError("provider smoke requires high-density manifest status completed")
    pages = [page for page in manifest.get("pages") or [] if isinstance(page, dict)]
    if page_id:
        pages = [page for page in pages if str(page.get("page_id") or "") == page_id]
    if len(pages) != 1:
        raise ProviderSmokeError("provider smoke must target exactly one completed page")
    page = pages[0]
    selected_page_id = str(page.get("page_id") or "")
    try:
        blueprint = load_blueprint_manifest(root, selected_page_id, expected_run_id=str(manifest.get("run_id") or ""))
    except ContractError as exc:
        raise ProviderSmokeError(str(exc)) from exc
    provider = blueprint.get("provider") or {}
    tool = str(provider.get("tool") or "").strip()
    model = str(provider.get("model") or "").strip()
    request_id = str(provider.get("request_id") or "").strip()
    if (
        not tool
        or not model
        or not request_id
        or tool in {"fixture_runtime", "agent_imagegen"}
        or any(value.lower() in {"unavailable", "unknown"} for value in (tool, model, request_id))
    ):
        raise ProviderSmokeError(f"fresh provider metadata is missing or placeholder on page {selected_page_id}")
    prompt_path = safe_run_path(root, str(blueprint.get("prompt_ref") or ""))
    prompt = read_json(prompt_path)
    challenge = prompt.get("provider_challenge") or {}
    if str(provider.get("challenge_nonce") or "") != str(challenge.get("nonce") or ""):
        raise ProviderSmokeError(f"provider challenge lineage is stale on page {selected_page_id}")
    if str(provider.get("prompt_sha256") or "") != str(prompt.get("prompt_sha256") or ""):
        raise ProviderSmokeError(f"provider prompt lineage is stale on page {selected_page_id}")

    readback_ref = _artifact_ref(root, page, "readback_report")
    readback = read_json(root / readback_ref["path"])
    if readback.get("status") != "pass":
        raise ProviderSmokeError(f"PPTX readback has not passed on page {selected_page_id}")
    review_ref = _artifact_ref(root, page, "visual_review")
    review = read_json(root / review_ref["path"])
    if review.get("visual_status") != "pass" or review.get("verdict") != "pass":
        raise ProviderSmokeError(f"visual review has not passed on page {selected_page_id}")
    content_lock_ref = _artifact_ref(root, page, "content_lock")
    content_lock_payload = read_json(root / content_lock_ref["path"])
    assert_v2("content_lock", content_lock_payload)
    content_lock_sha = str(content_lock_payload.get("content_lock_sha256") or "")
    expected_content_lock_sha = sha256_json({key: value for key, value in content_lock_payload.items() if key not in {"content_lock_sha256", "created_at", "updated_at"}})
    if content_lock_sha != expected_content_lock_sha:
        raise ProviderSmokeError(f"content lock hash is stale on page {selected_page_id}")
    if str(blueprint.get("content_lock_sha256") or "") != content_lock_sha:
        raise ProviderSmokeError(f"blueprint content lock lineage is stale on page {selected_page_id}")
    svg_ref = _artifact_ref(root, page, "svg")
    scene_ref = _artifact_ref(root, page, "page_scene")
    trace_ref = _artifact_ref(root, page, "pptx_trace")
    trace_wrapper = read_json(root / trace_ref["path"])
    trace = trace_wrapper.get("trace") if isinstance(trace_wrapper.get("trace"), dict) else {}
    if str(trace.get("page_id") or "") != selected_page_id or str(trace.get("svg_sha256") or "") != svg_ref["sha256"]:
        raise ProviderSmokeError(f"page trace lineage is stale on page {selected_page_id}")
    deck_trace_path = root / "high_density_build" / "traces" / "pptx_trace.json"
    deck_trace = read_json(deck_trace_path)
    assert_v2("svg_to_drawingml_trace", deck_trace)
    pptx_path = root / "high_density_build" / "pptx" / "deck_high_density.pptx"
    if not pptx_path.is_file():
        raise ProviderSmokeError(f"compiled PPTX is missing on page {selected_page_id}")
    pptx_sha = sha256_file(pptx_path)
    if str(deck_trace.get("pptx_sha256") or "") != pptx_sha or str(readback.get("pptx_sha256") or "") != pptx_sha:
        raise ProviderSmokeError(f"PPTX lineage is stale on page {selected_page_id}")
    approval = blueprint.get("approval") or {}
    if str(approval.get("source") or "") not in {"explicit_user", "agent_review"}:
        raise ProviderSmokeError(f"fresh provider smoke requires explicit blueprint approval on page {selected_page_id}")
    timeline = [
        ("challenge", _timestamp(challenge.get("issued_at"), field="challenge", page_id=selected_page_id)),
        ("request", _timestamp(provider.get("requested_at"), field="request", page_id=selected_page_id)),
        ("response", _timestamp(provider.get("responded_at"), field="response", page_id=selected_page_id)),
        ("approval", _timestamp(approval.get("approved_at"), field="approval", page_id=selected_page_id)),
        ("visual review", _timestamp(review.get("created_at"), field="visual review", page_id=selected_page_id)),
        ("readback", _timestamp(readback.get("created_at"), field="readback", page_id=selected_page_id)),
    ]
    for (previous_name, previous), (current_name, current) in zip(timeline, timeline[1:], strict=False):
        if current < previous:
            raise ProviderSmokeError(f"provider smoke timeline is stale on page {selected_page_id}: {current_name} precedes {previous_name}")
    evidence = {
        "schema_version": "deck_high_density_provider_smoke.v1",
        "run_mode": run_mode,
        "run_id_sha256": _hash_text(str(manifest.get("run_id") or "")),
        "page_id": selected_page_id,
        "status": "pass",
        "provider": {
            "tool": tool,
            "model": model,
            "request_id_sha256": _hash_text(request_id),
            "request_sha256": str(provider.get("request_sha256") or ""),
            "challenge_nonce_sha256": _hash_text(str(challenge.get("nonce") or "")),
            "requested_at": str(provider.get("requested_at") or ""),
            "responded_at": str(provider.get("responded_at") or ""),
        },
        "lineage": {
            "prompt_sha256": str(blueprint.get("prompt_sha256") or ""),
            "image_sha256": str(blueprint.get("image_sha256") or ""),
            "scene_sha256": scene_ref["sha256"],
            "svg_sha256": svg_ref["sha256"],
            "pptx_sha256": pptx_sha,
            "readback_sha256": readback_ref["sha256"],
            "content_lock_sha256": content_lock_sha,
            "nbb_plan_sha256": str(blueprint.get("nbb_plan_sha256") or ""),
            "style_lock_sha256": str(blueprint.get("style_lock_sha256") or ""),
        },
        "timeline": {
            "challenge_issued_at": str(challenge.get("issued_at") or ""),
            "requested_at": str(provider.get("requested_at") or ""),
            "responded_at": str(provider.get("responded_at") or ""),
            "approved_at": str(approval.get("approved_at") or ""),
            "visual_reviewed_at": str(review.get("created_at") or ""),
            "readback_at": str(readback.get("created_at") or ""),
        },
        "artifacts": {
            "prompt": {"path": run_relative(root, prompt_path), "sha256": sha256_file(prompt_path)},
            "blueprint": _artifact_ref(root, page, "blueprint"),
            "page_scene": scene_ref,
            "svg": svg_ref,
            "content_lock": content_lock_ref,
            "pptx": {"path": run_relative(root, pptx_path), "sha256": pptx_sha},
            "pptx_trace": trace_ref,
            "visual_review": review_ref,
            "readback": readback_ref,
        },
        "gates": {
            "high_density_manifest": "pass",
            "visual_review": "pass",
            "readback": "pass",
            "svg_to_pptx": "pass",
        },
        "raw_provider_payload_included": False,
        "created_at": utc_now(),
    }
    assert_valid("provider_smoke", evidence)
    if output is not None:
        write_json(Path(output).expanduser().resolve(), evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write sanitized high-density ImageGen provider smoke evidence.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--page-id", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        evidence = build_provider_smoke_evidence(args.run_dir, page_id=args.page_id, output=args.output)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
