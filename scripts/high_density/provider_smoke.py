from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .blueprint import load_blueprint_manifest, safe_run_path
from .contracts import ContractError, assert_valid, assert_v2, read_json, run_relative, sha256_bytes, sha256_file, utc_now, write_json


class ProviderSmokeError(ContractError):
    pass


def _hash_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _artifact_ref(root: Path, page: dict[str, Any], key: str) -> dict[str, str]:
    value = page.get(key)
    if not isinstance(value, dict):
        raise ProviderSmokeError(f"completed high-density page is missing artifact ref: {key}")
    path = safe_run_path(root, str(value.get("path") or ""))
    return {"path": run_relative(root, path), "sha256": sha256_file(path)}


def build_provider_smoke_evidence(run_dir: str | Path, *, page_id: str = "", output: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
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
    blueprint = load_blueprint_manifest(root, selected_page_id, expected_run_id=str(manifest.get("run_id") or ""))
    provider = blueprint.get("provider") or {}
    tool = str(provider.get("tool") or "").strip()
    model = str(provider.get("model") or "").strip()
    request_id = str(provider.get("request_id") or "").strip()
    if not tool or not model or not request_id or any(value.lower() in {"unavailable", "unknown"} for value in (tool, model, request_id)):
        raise ProviderSmokeError(f"provider metadata is missing or placeholder on page {selected_page_id}")

    readback_ref = _artifact_ref(root, page, "readback_report")
    readback = read_json(root / readback_ref["path"])
    if readback.get("status") != "pass":
        raise ProviderSmokeError(f"PPTX readback has not passed on page {selected_page_id}")
    review_ref = _artifact_ref(root, page, "visual_review")
    review = read_json(root / review_ref["path"])
    if review.get("visual_status") != "pass" or review.get("verdict") != "pass":
        raise ProviderSmokeError(f"visual review has not passed on page {selected_page_id}")
    content_lock = page.get("content_lock") or {}
    content_lock_sha = str(content_lock.get("sha256") or "")
    if len(content_lock_sha) != 64:
        raise ProviderSmokeError(f"content lock lineage is missing on page {selected_page_id}")
    evidence = {
        "schema_version": "deck_high_density_provider_smoke.v1",
        "run_id_sha256": _hash_text(str(manifest.get("run_id") or "")),
        "page_id": selected_page_id,
        "status": "pass",
        "provider": {"tool": tool, "model": model, "request_id_sha256": _hash_text(request_id)},
        "lineage": {
            "prompt_sha256": str(blueprint.get("prompt_sha256") or ""),
            "image_sha256": str(blueprint.get("image_sha256") or ""),
            "content_lock_sha256": content_lock_sha,
            "nbb_plan_sha256": str(blueprint.get("nbb_plan_sha256") or ""),
            "style_lock_sha256": str(blueprint.get("style_lock_sha256") or ""),
        },
        "artifacts": {
            "blueprint": _artifact_ref(root, page, "blueprint"),
            "svg": _artifact_ref(root, page, "svg"),
            "pptx_trace": _artifact_ref(root, page, "pptx_trace"),
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
