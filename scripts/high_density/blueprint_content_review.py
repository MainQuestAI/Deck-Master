from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from .blueprint import blueprint_path, prompt_path, safe_run_path
from .contracts import ContractError, assert_v2, read_json, run_relative, sha256_file, utc_now, write_json
from .visibility import HARD_FORBIDDEN_CATEGORIES


REVIEW_DIR = Path("high_density_build/reviews")
ZONE_DIR = REVIEW_DIR / "blueprint_content"
REJECTED_DIR = Path("high_density_build/blueprints/rejected")
ZONE_IDS = ("full_page", "header", "footer", "top_left", "top_right", "bottom_left", "bottom_right")


class BlueprintContentReviewRequired(ContractError):
    pass


def review_path(root: Path, page_id: str) -> Path:
    return root / REVIEW_DIR / f"{page_id}.blueprint_content_review.json"


def _attempts_path(root: Path, page_id: str) -> Path:
    return root / REJECTED_DIR / page_id / "attempts.json"


def next_attempt_index(root: Path, page_id: str) -> int:
    path = _attempts_path(root, page_id)
    if not path.exists():
        return 1
    payload = read_json(path)
    count = int(payload.get("failed_attempt_count") or 0)
    return min(3, count + 1)


def archive_rejected_blueprint(root: Path, page_id: str) -> int:
    """Preserve a failed provider attempt, then clear its canonical artifacts."""
    attempt_index = next_attempt_index(root, page_id)
    destination = root / REJECTED_DIR / page_id / f"attempt-{attempt_index}"
    destination.mkdir(parents=True, exist_ok=True)
    candidates = [
        blueprint_path(root, page_id),
        prompt_path(root, page_id),
        review_path(root, page_id),
        root / "high_density_build/blueprints" / f"{page_id}.blueprint_manifest.json",
        root / "high_density_build/blueprints" / f"{page_id}.manifest.json",
        root / "high_density_build/blueprints" / f"{page_id}.provider_receipt.json",
        root / "high_density_build/blueprints" / f"{page_id}.provider_host_receipt.json",
    ]
    for source in candidates:
        if source is not None and source.is_file():
            shutil.copy2(source, destination / source.name)
    zones = root / ZONE_DIR / page_id
    if zones.is_dir():
        shutil.copytree(zones, destination / "zones", dirs_exist_ok=True)
    state = {
        "page_id": page_id,
        "failed_attempt_count": attempt_index,
        "last_attempt_path": run_relative(root, destination),
        "updated_at": utc_now(),
    }
    write_json(_attempts_path(root, page_id), state)
    for source in candidates:
        if source is not None and source.is_file():
            source.unlink()
    if zones.is_dir():
        shutil.rmtree(zones)
    return attempt_index


def _zone_boxes(width: int, height: int) -> dict[str, tuple[int, int, int, int]]:
    corner_w, corner_h = max(1, width // 4), max(1, height // 4)
    header_h, footer_h = max(1, height // 5), max(1, height // 5)
    return {
        "full_page": (0, 0, width, height),
        "header": (0, 0, width, header_h),
        "footer": (0, height - footer_h, width, height),
        "top_left": (0, 0, corner_w, corner_h),
        "top_right": (width - corner_w, 0, width, corner_h),
        "bottom_left": (0, height - corner_h, corner_w, height),
        "bottom_right": (width - corner_w, height - corner_h, width, height),
    }


def write_review_zones(root: Path, page_id: str) -> list[dict[str, str]]:
    image = blueprint_path(root, page_id)
    if image is None:
        raise BlueprintContentReviewRequired(f"blueprint image is missing on page {page_id}")
    destination = root / ZONE_DIR / page_id
    destination.mkdir(parents=True, exist_ok=True)
    if image.suffix.lower() != ".png":
        zones: list[dict[str, str]] = []
        for zone_id in ZONE_IDS:
            target = destination / f"{zone_id}{image.suffix.lower()}"
            shutil.copyfile(image, target)
            zones.append({"zone_id": zone_id, "path": run_relative(root, target), "sha256": sha256_file(target)})
        return zones
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - declared runtime dependency
        raise BlueprintContentReviewRequired("Pillow is required for blueprint content review crops") from exc
    with Image.open(image) as source:
        rgb = source.convert("RGB")
        boxes = _zone_boxes(*rgb.size)
        zones = []
        for zone_id in ZONE_IDS:
            target = destination / f"{zone_id}.png"
            rgb.crop(boxes[zone_id]).save(target)
            zones.append({"zone_id": zone_id, "path": run_relative(root, target), "sha256": sha256_file(target)})
    return zones


def write_blueprint_content_review(
    root: Path,
    page_id: str,
    lock: dict[str, Any],
    *,
    findings: list[dict[str, Any]],
    reviewer_id: str,
    action_id: str,
) -> Path:
    image = blueprint_path(root, page_id)
    if image is None:
        raise BlueprintContentReviewRequired(f"blueprint image is missing on page {page_id}")
    prompt = read_json(prompt_path(root, page_id))
    policy = lock.get("visibility_policy") or {}
    allowed = {str(item.get("term") or "") for item in policy.get("allowed_visible_terms") or [] if isinstance(item, dict)}
    normalized: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        category = str(item.get("category") or "")
        if category in HARD_FORBIDDEN_CATEGORIES:
            item["disposition"] = "blocked"
        elif item.get("disposition") == "allowed" and str(item.get("allowlist_term") or "") not in allowed:
            item["disposition"] = "blocked"
        normalized.append(item)
    blocked = [item for item in normalized if item.get("disposition") == "blocked"]
    payload = {
        "schema_version": "deck_blueprint_content_review.v1",
        "run_id": str(lock["run_id"]),
        "page_id": page_id,
        "image_sha256": sha256_file(image),
        "prompt_sha256": str(prompt["prompt_sha256"]),
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "style_lock_sha256": str(prompt["style_lock_sha256"]),
        "visibility_policy_sha256": str(policy.get("visibility_policy_sha256") or ""),
        "zones": write_review_zones(root, page_id),
        "findings": normalized,
        "reviewer_id": reviewer_id,
        "action_id": action_id,
        "status": "needs_regeneration" if blocked else "pass",
        "created_at": utc_now(),
    }
    assert_v2("blueprint_content_review", payload)
    return write_json(review_path(root, page_id), payload)


def load_blueprint_content_review(root: Path, page_id: str, lock: dict[str, Any]) -> dict[str, Any]:
    path = review_path(root, page_id)
    if not path.exists():
        raise BlueprintContentReviewRequired(f"blueprint content review is required on page {page_id}")
    review = read_json(path)
    assert_v2("blueprint_content_review", review)
    image = blueprint_path(root, page_id)
    if image is None or str(review.get("image_sha256") or "") != sha256_file(image):
        raise BlueprintContentReviewRequired(f"blueprint content review image hash is stale on page {page_id}")
    prompt = read_json(prompt_path(root, page_id))
    expected = {
        "run_id": str(lock.get("run_id") or ""),
        "page_id": page_id,
        "prompt_sha256": str(prompt.get("prompt_sha256") or ""),
        "content_lock_sha256": str(lock.get("content_lock_sha256") or ""),
        "style_lock_sha256": str(prompt.get("style_lock_sha256") or ""),
        "visibility_policy_sha256": str((lock.get("visibility_policy") or {}).get("visibility_policy_sha256") or ""),
    }
    for field, value in expected.items():
        if str(review.get(field) or "") != value:
            raise BlueprintContentReviewRequired(f"blueprint content review {field} is stale on page {page_id}")
    zones = review.get("zones") or []
    if {str(item.get("zone_id") or "") for item in zones if isinstance(item, dict)} != set(ZONE_IDS):
        raise BlueprintContentReviewRequired(f"blueprint content review zones are incomplete on page {page_id}")
    for zone in zones:
        path_value = str(zone.get("path") or "")
        try:
            zone_path = safe_run_path(root, path_value)
        except ContractError as exc:
            raise BlueprintContentReviewRequired(f"blueprint content review crop is invalid on page {page_id}") from exc
        if not zone_path.is_file() or str(zone.get("sha256") or "") != sha256_file(zone_path):
            raise BlueprintContentReviewRequired(f"blueprint content review crop is stale on page {page_id}")
    blocked = [item for item in review.get("findings") or [] if isinstance(item, dict) and item.get("disposition") == "blocked"]
    if review.get("status") != "pass" or blocked:
        raise BlueprintContentReviewRequired(f"blueprint content review requires regeneration on page {page_id}")
    return review


def ensure_fixture_blueprint_content_review(root: Path, page_id: str, lock: dict[str, Any]) -> dict[str, Any]:
    try:
        return load_blueprint_content_review(root, page_id, lock)
    except BlueprintContentReviewRequired:
        write_blueprint_content_review(root, page_id, lock, findings=[], reviewer_id="fixture_runtime", action_id="fixture_content_review")
        return load_blueprint_content_review(root, page_id, lock)


def _main() -> int:
    parser = argparse.ArgumentParser(description="Write a high-density blueprint content review")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--findings-file", required=True)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--action-id", required=True)
    args = parser.parse_args()
    root = Path(args.run_dir).expanduser().resolve()
    findings = json.loads(Path(args.findings_file).expanduser().read_text(encoding="utf-8"))
    if not isinstance(findings, list):
        raise SystemExit("--findings-file must contain a JSON array")
    lock = read_json(root / "high_density_build" / "content_locks" / f"{args.page_id}.content_lock.json")
    output = write_blueprint_content_review(
        root,
        args.page_id,
        lock,
        findings=findings,
        reviewer_id=args.reviewer_id,
        action_id=args.action_id,
    )
    print(output)
    return 0


__all__ = [
    "archive_rejected_blueprint",
    "BlueprintContentReviewRequired",
    "ensure_fixture_blueprint_content_review",
    "load_blueprint_content_review",
    "next_attempt_index",
    "review_path",
    "write_blueprint_content_review",
    "write_review_zones",
]


if __name__ == "__main__":  # pragma: no cover - exercised through the Agent continuation
    raise SystemExit(_main())
