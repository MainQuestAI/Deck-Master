from __future__ import annotations

import copy
import json
import os
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ContractError, assert_v2, read_json, run_relative, sha256_bytes, sha256_file, sha256_json, utc_now, write_json
from .integrity import sign_runtime_payload, verify_runtime_payload

BLUEPRINT_DIR = Path("high_density_build/blueprints")
PROMPT_DIR = Path("high_density_build/prompts")
BLUEPRINT_MANIFEST_DIR = BLUEPRINT_DIR
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg")
CANVAS_WIDTH = 1672
CANVAS_HEIGHT = 941
CANVAS_RATIO = CANVAS_WIDTH / CANVAS_HEIGHT
SAFE_PAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PROVIDER_HOST_ROOTS_ENV = "DECK_MASTER_PROVIDER_RESULT_ROOTS"


class BlueprintRequired(ContractError):
    def __init__(self, page_id: str, lock_ref: str) -> None:
        self.page_id = page_id
        self.lock_ref = lock_ref
        super().__init__(f"blueprint image required for page {page_id}")


class BlueprintInvalid(ContractError):
    pass


def _parse_timestamp(value: Any, *, field: str, page_id: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise BlueprintInvalid(f"blueprint {field} timestamp is invalid on page {page_id}") from exc
    if parsed.tzinfo is None:
        raise BlueprintInvalid(f"blueprint {field} timestamp must include a timezone on page {page_id}")
    return parsed


def _provider_request_sha256(provider: dict[str, Any]) -> str:
    return sha256_json(
        {
            "tool": str(provider.get("tool") or ""),
            "model": str(provider.get("model") or ""),
            "request_id": str(provider.get("request_id") or ""),
            "challenge_nonce": str(provider.get("challenge_nonce") or ""),
            "prompt_sha256": str(provider.get("prompt_sha256") or ""),
            "requested_at": str(provider.get("requested_at") or ""),
        }
    )


def _validate_provider_lineage(prompt: dict[str, Any], provider: dict[str, Any], page_id: str) -> None:
    challenge = prompt.get("provider_challenge") or {}
    required = ("tool", "model", "request_id", "challenge_nonce", "prompt_sha256", "request_sha256", "requested_at", "responded_at")
    missing = [field for field in required if not str(provider.get(field) or "")]
    if missing:
        raise BlueprintInvalid(f"blueprint provider lineage is incomplete on page {page_id}: {', '.join(missing)}")
    if str(provider["challenge_nonce"]) != str(challenge.get("nonce") or ""):
        raise BlueprintInvalid(f"blueprint provider challenge is stale on page {page_id}")
    if str(provider["prompt_sha256"]) != str(prompt.get("prompt_sha256") or ""):
        raise BlueprintInvalid(f"blueprint provider prompt hash is stale on page {page_id}")
    if str(provider["request_sha256"]) != _provider_request_sha256(provider):
        raise BlueprintInvalid(f"blueprint provider request hash is stale on page {page_id}")
    issued_at = _parse_timestamp(challenge.get("issued_at"), field="challenge issued_at", page_id=page_id)
    requested_at = _parse_timestamp(provider.get("requested_at"), field="provider requested_at", page_id=page_id)
    responded_at = _parse_timestamp(provider.get("responded_at"), field="provider responded_at", page_id=page_id)
    if requested_at < issued_at or responded_at < requested_at:
        raise BlueprintInvalid(f"blueprint provider timestamp chain is stale on page {page_id}")


def _assert_page_id(page_id: str) -> None:
    if not SAFE_PAGE_ID.fullmatch(str(page_id or "")) or ".." in str(page_id):
        raise BlueprintInvalid(f"unsafe blueprint page_id: {page_id}")


def blueprint_path(root: Path, page_id: str) -> Path | None:
    _assert_page_id(page_id)
    directory = root / BLUEPRINT_DIR
    for extension in SUPPORTED_EXTENSIONS:
        candidate = directory / f"{page_id}{extension}"
        if candidate.exists():
            return candidate
    return None


def blueprint_manifest_path(root: Path, page_id: str) -> Path:
    _assert_page_id(page_id)
    canonical = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json"
    legacy = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json"
    return canonical if canonical.exists() or not legacy.exists() else legacy


def prompt_path(root: Path, page_id: str) -> Path:
    _assert_page_id(page_id)
    return root / PROMPT_DIR / f"{page_id}.blueprint_prompt.json"


def provider_receipt_path(root: Path, page_id: str) -> Path:
    _assert_page_id(page_id)
    return root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.provider_receipt.json"


def provider_host_receipt_path(root: Path, page_id: str) -> Path:
    _assert_page_id(page_id)
    return root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.provider_host_receipt.json"


def _provider_source_roots() -> list[Path]:
    configured = os.environ.get(PROVIDER_HOST_ROOTS_ENV, "")
    values = [item for item in configured.split(os.pathsep) if item] if configured else ["~/.codex/generated_images"]
    roots: list[Path] = []
    for value in values:
        path = Path(value).expanduser().resolve()
        if path not in roots:
            roots.append(path)
    return roots


def _provider_source_locator(source: Path) -> tuple[Path, str]:
    resolved = source.expanduser().resolve()
    for root in _provider_source_roots():
        try:
            return root, resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    raise BlueprintInvalid(f"provider image must come from a configured Host-managed ImageGen root: {source}")


def _provider_source_path(receipt: dict[str, Any]) -> Path:
    root_hash = str(receipt.get("source_root_sha256") or "")
    relative = str(receipt.get("source_relative_path") or "")
    for root in _provider_source_roots():
        if sha256_bytes(str(root).encode("utf-8")) != root_hash:
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise BlueprintInvalid("provider Host receipt source path escapes its configured root") from exc
        return candidate
    raise BlueprintInvalid("provider Host receipt source root is not configured")


def _provider_source_created_at(source: Path) -> str:
    stat = source.stat()
    timestamp = getattr(stat, "st_birthtime", stat.st_mtime)
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _run_mode(root: Path) -> str:
    mode = str(read_json(root / "request.json").get("run_mode") or "production").strip().lower()
    return mode if mode in {"production", "benchmark", "fixture", "dev"} else "production"


def _validate_provider_challenge(root: Path, prompt: dict[str, Any], page_id: str) -> dict[str, Any]:
    challenge = prompt.get("provider_challenge") or {}
    payload = {key: value for key, value in challenge.items() if key != "integrity"}
    verify_runtime_payload("imagegen_provider_challenge.v1", payload, challenge.get("integrity") or {})
    expected = {
        "run_id": str(prompt.get("run_id") or ""),
        "page_id": page_id,
        "prompt_sha256": str(prompt.get("prompt_sha256") or ""),
        "content_lock_sha256": str(prompt.get("content_lock_sha256") or ""),
        "nbb_plan_sha256": str(prompt.get("nbb_plan_sha256") or ""),
        "style_lock_sha256": str(prompt.get("style_lock_sha256") or ""),
    }
    for field, value in expected.items():
        if str(challenge.get(field) or "") != value:
            raise BlueprintInvalid(f"blueprint provider challenge {field} is stale on page {page_id}")
    if str(challenge.get("run_mode") or "") != _run_mode(root):
        raise BlueprintInvalid(f"blueprint provider challenge run mode is stale on page {page_id}")
    return payload


def record_provider_host_result(root: Path, page_id: str, source_image: Path) -> Path:
    """Import a host-managed ImageGen result before production manifest sealing."""
    _assert_page_id(page_id)
    prompt = read_json(prompt_path(root, page_id))
    assert_v2("blueprint_prompt", prompt)
    challenge = _validate_provider_challenge(root, prompt, page_id)
    run_mode = _run_mode(root)
    if run_mode not in {"production", "benchmark"}:
        raise BlueprintInvalid("Host-managed provider receipt is only required for production or benchmark runs")
    source = Path(source_image).expanduser().resolve()
    if not source.is_file() or source.is_symlink() or source.suffix.lower() != ".png":
        raise BlueprintInvalid("Host-managed provider result must be a regular PNG file")
    root_path, relative = _provider_source_locator(source)
    if not re.fullmatch(r"exec-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.png", source.name):
        raise BlueprintInvalid("Host-managed provider result must use the ImageGen exec-UUID filename")
    source_created_at = _provider_source_created_at(source)
    if _parse_timestamp(source_created_at, field="provider source created_at", page_id=page_id) < _parse_timestamp(challenge.get("issued_at"), field="challenge issued_at", page_id=page_id):
        raise BlueprintInvalid("Host-managed provider result predates the Runtime challenge")
    destination = root / BLUEPRINT_DIR / f"{page_id}.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    provider = {
        "tool": "image_gen.imagegen",
        "model": "provider-managed-imagegen",
        "request_id": source.stem,
        "challenge_nonce": str(challenge["nonce"]),
        "prompt_sha256": str(prompt["prompt_sha256"]),
        "requested_at": str(challenge["issued_at"]),
        "responded_at": source_created_at,
    }
    provider["request_sha256"] = _provider_request_sha256(provider)
    payload = {
        "schema_version": "deck_provider_host_receipt.v1",
        "run_id": str(prompt.get("run_id") or ""),
        "page_id": page_id,
        "run_mode": run_mode,
        "challenge_payload_sha256": sha256_json(challenge),
        "prompt_sha256": str(prompt["prompt_sha256"]),
        "image_sha256": sha256_file(destination),
        "provider_tool": provider["tool"],
        "provider_model": provider["model"],
        "provider_request_id": provider["request_id"],
        "provider_request_sha256": provider["request_sha256"],
        "requested_at": provider["requested_at"],
        "responded_at": provider["responded_at"],
        "source_root_sha256": sha256_bytes(str(root_path).encode("utf-8")),
        "source_relative_path": relative,
        "source_file_sha256": sha256_file(source),
        "source_size_bytes": source.stat().st_size,
        "source_created_at": source_created_at,
        "recorded_at": utc_now(),
    }
    receipt = {**payload, "integrity": sign_runtime_payload("imagegen_host_result.v1", payload)}
    assert_v2("provider_host_receipt", receipt)
    write_json(provider_host_receipt_path(root, page_id), receipt)
    return destination


def load_provider_host_receipt(root: Path, page_id: str, prompt: dict[str, Any], image: Path) -> dict[str, Any]:
    try:
        receipt = read_json(provider_host_receipt_path(root, page_id))
    except ContractError as exc:
        raise BlueprintInvalid(f"Host-managed provider receipt is required on page {page_id}") from exc
    assert_v2("provider_host_receipt", receipt)
    payload = {key: value for key, value in receipt.items() if key != "integrity"}
    verify_runtime_payload("imagegen_host_result.v1", payload, receipt.get("integrity") or {})
    if str(receipt.get("run_id") or "") != str(prompt.get("run_id") or "") or str(receipt.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"Host-managed provider receipt identity is stale on page {page_id}")
    challenge = _validate_provider_challenge(root, prompt, page_id)
    expected = {
        "run_mode": _run_mode(root),
        "challenge_payload_sha256": sha256_json(challenge),
        "prompt_sha256": str(prompt.get("prompt_sha256") or ""),
        "image_sha256": sha256_file(image),
    }
    for field, value in expected.items():
        if str(receipt.get(field) or "") != value:
            raise BlueprintInvalid(f"Host-managed provider receipt {field} is stale on page {page_id}")
    source = _provider_source_path(receipt)
    if not source.is_file() or source.is_symlink() or sha256_file(source) != str(receipt.get("source_file_sha256") or "") or source.stat().st_size != int(receipt.get("source_size_bytes") or 0):
        raise BlueprintInvalid(f"Host-managed provider source is missing or stale on page {page_id}")
    if sha256_file(source) != sha256_file(image):
        raise BlueprintInvalid(f"Host-managed provider source does not match blueprint image on page {page_id}")
    if _provider_source_created_at(source) != str(receipt.get("source_created_at") or ""):
        raise BlueprintInvalid(f"Host-managed provider source timestamp is stale on page {page_id}")
    return receipt


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None


def _svg_dimensions(path: Path) -> tuple[int, int] | None:
    head = path.read_text(encoding="utf-8", errors="ignore")[:8192]
    viewbox = re.search(r"viewBox\s*=\s*[\"']\s*[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", head)
    if viewbox:
        return round(float(viewbox.group(1))), round(float(viewbox.group(2)))
    width = re.search(r"width\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    height = re.search(r"height\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    if width and height:
        return round(float(width.group(1))), round(float(height.group(1)))
    return None


def image_dimensions(path: Path) -> tuple[int, int]:
    dimensions = _png_dimensions(path) if path.suffix.lower() == ".png" else _svg_dimensions(path) if path.suffix.lower() == ".svg" else None
    if dimensions is None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                dimensions = image.size
        except Exception as exc:  # pragma: no cover - provider format path
            raise BlueprintInvalid(f"cannot read blueprint dimensions: {path}") from exc
    if dimensions[0] <= 0 or dimensions[1] <= 0:
        raise BlueprintInvalid(f"blueprint dimensions must be positive: {path}")
    return dimensions


def _default_slide_frame(width: int, height: int) -> dict[str, float]:
    ratio = width / height
    if abs(ratio - CANVAS_RATIO) <= 0.02:
        return {"x": 0, "y": 0, "w": width, "h": height}
    if ratio > CANVAS_RATIO:
        frame_width = height * CANVAS_RATIO
        return {"x": (width - frame_width) / 2, "y": 0, "w": frame_width, "h": height}
    frame_height = width / CANVAS_RATIO
    return {"x": 0, "y": (height - frame_height) / 2, "w": width, "h": frame_height}


def _content_summary(lock: dict[str, Any]) -> dict[str, Any]:
    visible = lock.get("customer_visible") or {}
    enrichment = lock.get("enrichment") or {}
    storyline_context = enrichment.get("storyline_context") or {}
    blocks = visible.get("body_blocks") or []
    caveats = list(enrichment.get("caveat") or [])
    storyline_caveat = str(storyline_context.get("caveat") or "")
    if storyline_caveat and storyline_caveat not in caveats:
        caveats.append(storyline_caveat)
    return {
        "title": str(visible.get("title") or ""),
        "subtitle": str(visible.get("subtitle") or ""),
        "conclusion": str(enrichment.get("conclusion") or ""),
        "supporting_arguments": [str(value) for value in enrichment.get("supporting_arguments") or []],
        "detailed_argument": str(enrichment.get("detailed_argument") or ""),
        "so_what": str(enrichment.get("so_what") or ""),
        "business_implication": str(enrichment.get("business_implication") or ""),
        "body": [json.dumps(block, ensure_ascii=False, sort_keys=True) if isinstance(block, (dict, list)) else str(block) for block in blocks],
        "evidence_ids": [str(item.get("evidence_id") if isinstance(item, dict) else item) for item in lock.get("evidence_bindings") or []],
        "required_components": list(lock.get("required_component_ids") or []),
        "storyline_id": str(enrichment.get("storyline_id") or (lock.get("lineage") or {}).get("selected_storyline_id") or ""),
        "handoff": str(enrichment.get("handoff") or ""),
        "caveat": caveats,
        "material_pool": enrichment.get("material_pool") or {},
        "evidence_hierarchy": enrichment.get("evidence_hierarchy") or {},
        "evidence_assessment": enrichment.get("evidence_assessment") or {},
        "chart_plan": enrichment.get("chart_plan") or {},
        "derived_claims": enrichment.get("derived_claims") or [],
        "storyline_context": storyline_context,
        "target_language": str(lock.get("target_language") or "zh-CN"),
    }


def _presentation_projection(lock: dict[str, Any]) -> dict[str, Any]:
    """Build the only content payload that may be shown to the image provider."""
    visible = lock.get("customer_visible") or {}
    enrichment = lock.get("enrichment") or {}
    policy = lock.get("visibility_policy") or {}
    chart_plan = dict(enrichment.get("chart_plan") or {})
    chart_plan.pop("source_refs", None)
    chart_plan.pop("annotations", None)
    allowed = [str(item.get("term") or "") for item in policy.get("allowed_visible_terms") or [] if isinstance(item, dict)]
    return {
        "title": str(visible.get("title") or ""),
        "subtitle": str(visible.get("subtitle") or ""),
        "body_blocks": copy.deepcopy(visible.get("body_blocks") or []),
        "callouts": copy.deepcopy(visible.get("callouts") or []),
        "management_conclusion": str(enrichment.get("conclusion") or visible.get("title") or ""),
        "supporting_arguments": [str(value) for value in enrichment.get("supporting_arguments") or []],
        "business_implication": str(enrichment.get("business_implication") or enrichment.get("so_what") or ""),
        "chart_plan": chart_plan,
        "required_components": list(lock.get("required_component_ids") or []),
        "density_target": copy.deepcopy(lock.get("density_target") or {}),
        "target_language": str(lock.get("target_language") or "zh-CN"),
        "allowed_visible_terms": [item for item in allowed if item],
    }


def build_blueprint_prompt(
    lock: dict[str, Any],
    style_lock: dict[str, Any] | None = None,
    *,
    nbb_plan_sha256: str = "",
    provider_challenge_nonce: str = "",
    attempt_index: int = 1,
) -> str:
    style = style_lock or {"style_id": "unlocked", "palette": {}, "grid": {}, "typography": {}}
    projection = _presentation_projection(lock)
    style_name = str(style.get("name") or style.get("style_id") or "locked style")
    return "\n".join(
        [
            "Create a high-density consulting presentation slide blueprint for an editable native redraw.",
            f"Visible title: {projection['title']}",
            f"Visible conclusion: {projection['management_conclusion']}",
            f"Express this management takeaway in customer-facing language without a label: {projection['business_implication']}",
            f"Supporting arguments: {' | '.join(projection['supporting_arguments']) or 'none'}.",
            f"Approved page content: {json.dumps(projection['body_blocks'], ensure_ascii=False, sort_keys=True)}.",
            f"Visible callouts: {json.dumps(projection['callouts'], ensure_ascii=False, sort_keys=True)}.",
            f"Use this intended visual form: {json.dumps(projection['chart_plan'], ensure_ascii=False, sort_keys=True)}.",
            f"Include these required visual components: {', '.join(projection['required_components'])}.",
            f"Target language: {projection['target_language']}.",
            f"Locked visual style: {style_name}; palette={json.dumps(style.get('palette') or {}, ensure_ascii=False, sort_keys=True)}; grid={json.dumps(style.get('grid') or {}, ensure_ascii=False, sort_keys=True)}; typography={json.dumps(style.get('typography') or {}, ensure_ascii=False, sort_keys=True)}; chart_language={json.dumps(style.get('chart_language') or {}, ensure_ascii=False, sort_keys=True)}; table_language={json.dumps(style.get('table_language') or {}, ensure_ascii=False, sort_keys=True)}; surface_system={json.dumps(style.get('surface_system') or {}, ensure_ascii=False, sort_keys=True)}; density_rules={json.dumps(style.get('density_rules') or {}, ensure_ascii=False, sort_keys=True)}.",
            f"Approved optional visible terms: {' | '.join(projection['allowed_visible_terms']) or 'none'}.",
            "Use a contained 16:9 slide frame with dense but readable information regions and explicit business hierarchy.",
            "Use only presentation-ready business language. Do not render field names, instructions, or metadata from this prompt. Do not add any footer, page number, page counter, source line, evidence marker, explanatory label, framework label, placeholder, prompt label, or production annotation.",
            "Treat all visible text as composition guidance. The native redraw restores exact locked text from the content lock.",
        ]
    )


def build_blueprint_prompt_artifact(root: Path, page_id: str, lock: dict[str, Any], *, style_lock: dict[str, Any] | None = None, nbb_plan_sha256: str = "") -> Path:
    from .blueprint_content_review import next_attempt_index

    attempt_index = next_attempt_index(root, page_id)
    challenge_seed = {"nonce": secrets.token_hex(16), "issued_at": utc_now()}
    prompt_text = build_blueprint_prompt(
        lock,
        style_lock,
        nbb_plan_sha256=nbb_plan_sha256,
        provider_challenge_nonce=challenge_seed["nonce"],
        attempt_index=attempt_index,
    )
    style_hash = str((style_lock or {}).get("style_lock_sha256") or "0" * 64)
    prompt_sha256 = sha256_json(prompt_text)
    challenge_payload = {
        **challenge_seed,
        "run_mode": _run_mode(root),
        "run_id": str(lock["run_id"]),
        "page_id": str(page_id),
        "prompt_sha256": prompt_sha256,
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "nbb_plan_sha256": nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64),
        "style_lock_sha256": style_hash,
    }
    challenge = {
        **challenge_payload,
        "integrity": sign_runtime_payload("imagegen_provider_challenge.v1", challenge_payload),
    }
    artifact = {
        "schema_version": "deck_blueprint_prompt.v1",
        "run_id": str(lock["run_id"]),
        "page_id": str(page_id),
        "prompt_template_version": "cyber-ppt-high-density.v3",
        "prompt_text": prompt_text,
        "prompt_sha256": prompt_sha256,
        "content_lock_ref": f"high_density_build/content_locks/{page_id}.content_lock.json",
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "nbb_plan_ref": "high_density_build/nbb/nbb_plan.json",
        "nbb_plan_sha256": nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64),
        "style_lock_ref": "high_density_build/style/style_lock.json",
        "style_lock_sha256": style_hash,
        "presentation_projection": _presentation_projection(lock),
        "visible_copy_allowlist": [str(item.get("term") or "") for item in (lock.get("visibility_policy") or {}).get("allowed_visible_terms") or [] if isinstance(item, dict)],
        "forbidden_visible_categories": list((lock.get("visibility_policy") or {}).get("hard_forbidden") or []) + list((lock.get("visibility_policy") or {}).get("hidden_by_default") or []),
        "attempt_index": attempt_index,
        "required_components": list(lock.get("required_component_ids") or []),
        "forbidden_items": ["page numbers", "internal labels", "source metadata", "method labels", "prompt labels", "wireframe labels", "generation annotations", "hidden production notes"],
        "provider_challenge": challenge,
        "created_at": utc_now(),
    }
    from .contracts import assert_v2

    assert_v2("blueprint_prompt", artifact)
    path = prompt_path(root, page_id)
    write_json(path, artifact)
    return path


def _validate_frame(frame: dict[str, Any], dimensions: tuple[int, int], page_id: str) -> None:
    try:
        x, y, width, height = (float(frame[key]) for key in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError) as exc:
        raise BlueprintInvalid(f"blueprint slide_frame is invalid on page {page_id}") from exc
    if height <= 0 or width <= 0 or abs(width / height - CANVAS_RATIO) > 0.02:
        raise BlueprintInvalid(f"approved slide_frame ratio drifts from 16:9 on page {page_id}")
    if x < 0 or y < 0 or x + width > dimensions[0] + 0.01 or y + height > dimensions[1] + 0.01:
        raise BlueprintInvalid(f"blueprint slide_frame is outside the source canvas on page {page_id}")


def _assert_manifest_mirror_consistent(root: Path, page_id: str, canonical: Path) -> None:
    legacy = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json"
    if not canonical.exists() or not legacy.exists():
        return
    try:
        canonical_payload = read_json(canonical)
        legacy_payload = read_json(legacy)
    except ContractError as exc:
        raise BlueprintInvalid(f"blueprint manifest mirror is unreadable on page {page_id}") from exc
    if canonical_payload != legacy_payload:
        raise BlueprintInvalid(f"blueprint manifest mirror is stale on page {page_id}")


def _provider_receipt_payload(
    root: Path,
    page_id: str,
    prompt: dict[str, Any],
    manifest: dict[str, Any],
    *,
    sealed_at: str,
) -> dict[str, Any]:
    challenge = _validate_provider_challenge(root, prompt, page_id)
    provider = manifest.get("provider") or {}
    approval = manifest.get("approval") or {}
    host_receipt_sha256 = "0" * 64
    if str(challenge.get("run_mode") or "") in {"production", "benchmark"}:
        load_provider_host_receipt(root, page_id, prompt, blueprint_path(root, page_id) or Path(""))
        host_receipt_sha256 = sha256_file(provider_host_receipt_path(root, page_id))
    return {
        "schema_version": "deck_provider_runtime_receipt.v1",
        "run_id": str(manifest.get("run_id") or ""),
        "page_id": page_id,
        "run_mode": str(challenge.get("run_mode") or ""),
        "challenge_payload_sha256": sha256_json(challenge),
        "prompt_sha256": str(manifest.get("prompt_sha256") or ""),
        "image_sha256": str(manifest.get("image_sha256") or ""),
        "provider_request_sha256": str(provider.get("request_sha256") or ""),
        "provider_tool": str(provider.get("tool") or ""),
        "provider_model": str(provider.get("model") or ""),
        "provider_request_id_sha256": sha256_bytes(str(provider.get("request_id") or "").encode("utf-8")),
        "provider_host_receipt_sha256": host_receipt_sha256,
        "requested_at": str(provider.get("requested_at") or ""),
        "responded_at": str(provider.get("responded_at") or ""),
        "approval_source": str(approval.get("source") or ""),
        "approved_at": str(approval.get("approved_at") or ""),
        "sealed_at": sealed_at,
    }


def _write_provider_runtime_receipt(
    root: Path,
    page_id: str,
    prompt: dict[str, Any],
    manifest: dict[str, Any],
) -> Path:
    payload = _provider_receipt_payload(root, page_id, prompt, manifest, sealed_at=utc_now())
    receipt = {
        **payload,
        "integrity": sign_runtime_payload("imagegen_provider_result.v1", payload),
    }
    assert_v2("provider_runtime_receipt", receipt)
    return write_json(provider_receipt_path(root, page_id), receipt)


def load_provider_runtime_receipt(
    root: Path,
    page_id: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    receipt = read_json(provider_receipt_path(root, page_id))
    assert_v2("provider_runtime_receipt", receipt)
    payload = {key: value for key, value in receipt.items() if key != "integrity"}
    verify_runtime_payload("imagegen_provider_result.v1", payload, receipt.get("integrity") or {})
    prompt = read_json(safe_run_path(root, str(manifest.get("prompt_ref") or "")))
    expected = _provider_receipt_payload(
        root,
        page_id,
        prompt,
        manifest,
        sealed_at=str(receipt.get("sealed_at") or ""),
    )
    if payload != expected:
        raise BlueprintInvalid(f"provider Runtime receipt is stale on page {page_id}")
    return receipt


def ensure_blueprint_manifest(
    root: Path,
    page_id: str,
    lock: dict[str, Any],
    *,
    style_lock: dict[str, Any] | None = None,
    nbb_plan_sha256: str = "",
    approval: dict[str, Any] | None = None,
) -> Path:
    _assert_page_id(page_id)
    image = blueprint_path(root, page_id)
    if image is None:
        raise BlueprintRequired(page_id, f"high_density_build/content_locks/{page_id}.content_lock.json")
    prompt_file = prompt_path(root, page_id)
    if not prompt_file.exists():
        raise BlueprintInvalid(f"blueprint prompt must be written before image generation on page {page_id}")
    prompt = read_json(prompt_file)
    assert_v2("blueprint_prompt", prompt)
    _validate_provider_challenge(root, prompt, page_id)
    expected_nbb_sha = nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64)
    expected_style_sha = str((style_lock or {}).get("style_lock_sha256") or prompt.get("style_lock_sha256") or "0" * 64)
    if str(prompt.get("run_id") or "") != str(lock.get("run_id") or "") or str(prompt.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"blueprint prompt identity is stale on page {page_id}")
    if str(prompt.get("nbb_plan_sha256") or "") != expected_nbb_sha or str(prompt.get("style_lock_sha256") or "") != expected_style_sha:
        raise BlueprintInvalid(f"blueprint prompt lineage is stale on page {page_id}")
    challenge = prompt.get("provider_challenge") or {}
    challenge_nonce = str(challenge.get("nonce") or "")
    if not challenge_nonce:
        raise BlueprintInvalid(f"blueprint provider challenge is missing on page {page_id}")
    expected_prompt = build_blueprint_prompt(
        lock,
        style_lock,
        nbb_plan_sha256=nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64),
        provider_challenge_nonce=challenge_nonce,
        attempt_index=int(prompt.get("attempt_index") or 1),
    )
    expected_prompt_sha = sha256_json(expected_prompt)
    if prompt.get("prompt_sha256") != expected_prompt_sha or prompt.get("content_lock_sha256") != lock.get("content_lock_sha256"):
        raise BlueprintInvalid(f"blueprint prompt is stale on page {page_id}")
    dimensions = image_dimensions(image)
    manifest_path = blueprint_manifest_path(root, page_id)
    _assert_manifest_mirror_consistent(root, page_id, root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json")
    existing = read_json(manifest_path) if manifest_path.exists() else {}
    if existing and existing.get("schema_version") != "deck_blueprint_manifest.v2":
        raise BlueprintInvalid(f"preview-era blueprint manifest cannot enter v2 production on page {page_id}")
    slide_frame = existing.get("slide_frame") or _default_slide_frame(*dimensions)
    _validate_frame(slide_frame, dimensions, page_id)
    frame_x = float(slide_frame["x"])
    frame_y = float(slide_frame["y"])
    frame_width = float(slide_frame["w"])
    frame_height = float(slide_frame["h"])
    scale = CANVAS_WIDTH / frame_width
    transform = {
        "scale": scale,
        "offset_x": -frame_x * scale,
        "offset_y": -frame_y * scale,
        "crop": {"x": frame_x, "y": frame_y, "w": frame_width, "h": frame_height},
        "rounding_policy": "half_up_2dp",
    }
    style_hash = str((style_lock or {}).get("style_lock_sha256") or prompt.get("style_lock_sha256") or "0" * 64)
    approval_record = copy.deepcopy(existing.get("approval") or approval or {})
    if str(approval_record.get("status") or "") != "approved":
        raise BlueprintInvalid(f"blueprint requires explicit approval on page {page_id}")
    if not all(str(approval_record.get(field) or "") for field in ("source", "approved_by", "approved_at")):
        raise BlueprintInvalid(f"blueprint approval evidence is incomplete on page {page_id}")
    internal_annotations = list(existing.get("internal_annotations") or [])
    if internal_annotations:
        raise BlueprintInvalid(f"blueprint contains internal annotations on page {page_id}")
    provider = copy.deepcopy(existing.get("provider") or {})
    if _run_mode(root) in {"production", "benchmark"}:
        host_receipt = load_provider_host_receipt(root, page_id, prompt, image)
        provider = {
            "tool": str(host_receipt["provider_tool"]),
            "model": str(host_receipt["provider_model"]),
            "request_id": str(host_receipt["provider_request_id"]),
            "challenge_nonce": challenge_nonce,
            "prompt_sha256": expected_prompt_sha,
            "requested_at": str(host_receipt["requested_at"]),
            "responded_at": str(host_receipt["responded_at"]),
            "request_sha256": str(host_receipt["provider_request_sha256"]),
        }
    else:
        placeholder_provider = not provider or any(str(provider.get(field) or "").lower() in {"", "unavailable", "unknown"} for field in ("tool", "model", "request_id"))
        if placeholder_provider:
            fixture_provider = str(approval_record.get("source") or "") == "fixture_runtime"
            provider = {
                "tool": "fixture_runtime" if fixture_provider else "agent_imagegen",
                "model": "deterministic-svg-fixture" if fixture_provider else "unavailable",
                "request_id": f"fixture-{page_id}-{expected_prompt_sha[:12]}" if fixture_provider else "unavailable",
                "challenge_nonce": challenge_nonce,
                "prompt_sha256": expected_prompt_sha,
                "requested_at": str(challenge.get("issued_at") or utc_now()),
                "responded_at": str(challenge.get("issued_at") or utc_now()),
            }
            provider["request_sha256"] = _provider_request_sha256(provider)
    _validate_provider_lineage(prompt, provider, page_id)
    from .blueprint_content_review import BlueprintContentReviewRequired, ensure_fixture_blueprint_content_review, load_blueprint_content_review, review_path as content_review_path

    try:
        content_review = (
            ensure_fixture_blueprint_content_review(root, page_id, lock)
            if _run_mode(root) in {"fixture", "dev"}
            else load_blueprint_content_review(root, page_id, lock)
        )
    except BlueprintContentReviewRequired as exc:
        raise BlueprintInvalid(str(exc)) from exc
    manifest = {
        "schema_version": "deck_blueprint_manifest.v2",
        "run_id": str(lock["run_id"]),
        "page_id": page_id,
        "image_path": run_relative(root, image),
        "image_sha256": sha256_file(image),
        "prompt_ref": run_relative(root, prompt_file),
        "prompt_sha256": expected_prompt_sha,
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "nbb_plan_sha256": nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64),
        "style_lock_sha256": style_hash,
        "content_review_ref": run_relative(root, content_review_path(root, page_id)),
        "content_review_sha256": sha256_file(content_review_path(root, page_id)),
        "source_canvas": {"width": dimensions[0], "height": dimensions[1], "unit": "px"},
        "slide_frame": {"x": frame_x, "y": frame_y, "w": frame_width, "h": frame_height},
        "source_to_scene_transform": transform,
        "fit_mode": "approved_frame" if existing.get("slide_frame") else "contain",
        "internal_annotations": internal_annotations,
        "provider": provider,
        "approval": approval_record,
        "approved": True,
        "created_at": str(existing.get("created_at") or utc_now()),
    }
    assert_v2("blueprint_manifest", manifest)
    write_json(root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json", manifest)
    # Compatibility mirror for existing callers; it carries the same v2 payload.
    write_json(root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json", manifest)
    _write_provider_runtime_receipt(root, page_id, prompt, manifest)
    return root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json"


def load_blueprint_manifest(root: Path, page_id: str, *, expected_run_id: str | None = None) -> dict[str, Any]:
    path = blueprint_manifest_path(root, page_id)
    _assert_manifest_mirror_consistent(root, page_id, root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json")
    manifest = read_json(path)
    assert_v2("blueprint_manifest", manifest)
    approval = manifest.get("approval") or {}
    if manifest.get("approved") is not True or str(approval.get("status") or "") != "approved":
        raise BlueprintInvalid(f"blueprint is not explicitly approved on page {page_id}")
    if not all(str(approval.get(field) or "") for field in ("source", "approved_by", "approved_at")):
        raise BlueprintInvalid(f"blueprint approval evidence is incomplete on page {page_id}")
    if str(manifest.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"blueprint manifest page_id mismatch on page {page_id}")
    if expected_run_id and str(manifest.get("run_id") or "") != expected_run_id:
        raise BlueprintInvalid(f"blueprint manifest run_id mismatch on page {page_id}: expected {expected_run_id}")
    image = safe_image_path(root, str(manifest.get("image_path") or ""))
    expected_image = blueprint_path(root, page_id)
    if expected_image is None or image.resolve() != expected_image.resolve():
        raise BlueprintInvalid(f"blueprint manifest image_path mismatch on page {page_id}")
    prompt = read_json(safe_run_path(root, str(manifest.get("prompt_ref") or "")))
    assert_v2("blueprint_prompt", prompt)
    _validate_provider_challenge(root, prompt, page_id)
    if str(prompt.get("run_id") or "") != str(manifest.get("run_id") or "") or str(prompt.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"blueprint prompt identity is stale on page {page_id}")
    for field in ("content_lock_sha256", "nbb_plan_sha256", "style_lock_sha256"):
        if str(prompt.get(field) or "") != str(manifest.get(field) or ""):
            raise BlueprintInvalid(f"blueprint prompt {field} is stale on page {page_id}")
    if prompt.get("prompt_sha256") != manifest.get("prompt_sha256"):
        raise BlueprintInvalid(f"blueprint prompt hash is stale on page {page_id}")
    if sha256_json(str(prompt.get("prompt_text") or "")) != str(prompt.get("prompt_sha256") or ""):
        raise BlueprintInvalid(f"blueprint prompt content hash is stale on page {page_id}")
    if str(manifest.get("image_sha256") or "") != sha256_file(image):
        raise BlueprintInvalid(f"blueprint hash is stale on page {page_id}")
    from .blueprint_content_review import load_blueprint_content_review, review_path as content_review_path

    load_blueprint_content_review(root, page_id, read_json(safe_run_path(root, str(prompt.get("content_lock_ref") or ""))))
    if str(manifest.get("content_review_ref") or "") != run_relative(root, content_review_path(root, page_id)) or str(manifest.get("content_review_sha256") or "") != sha256_file(content_review_path(root, page_id)):
        raise BlueprintInvalid(f"blueprint content review is stale on page {page_id}")
    _validate_provider_lineage(prompt, manifest.get("provider") or {}, page_id)
    load_provider_runtime_receipt(root, page_id, manifest)
    dimensions = image_dimensions(image)
    source_canvas = manifest.get("source_canvas") or {}
    if (float(source_canvas.get("width") or 0), float(source_canvas.get("height") or 0)) != dimensions:
        raise BlueprintInvalid(f"blueprint source canvas is stale on page {page_id}")
    _validate_frame(manifest.get("slide_frame") or {}, dimensions, page_id)
    if not manifest.get("approved"):
        raise BlueprintInvalid(f"blueprint has not been approved on page {page_id}")
    return manifest


def safe_run_path(root: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute() or ".." in raw.parts:
        raise BlueprintInvalid(f"blueprint path must be run-relative: {value}")
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise BlueprintInvalid(f"blueprint path escapes run directory: {value}") from exc
    if not path.exists() or not path.is_file():
        raise BlueprintInvalid(f"blueprint artifact missing: {value}")
    return path


def safe_image_path(root: Path, value: str) -> Path:
    path = safe_run_path(root, value)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise BlueprintInvalid(f"unsupported blueprint extension: {path.suffix}")
    return path


__all__ = [
    "BLUEPRINT_DIR",
    "BLUEPRINT_MANIFEST_DIR",
    "BlueprintInvalid",
    "BlueprintRequired",
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "PROMPT_DIR",
    "build_blueprint_prompt",
    "build_blueprint_prompt_artifact",
    "blueprint_manifest_path",
    "blueprint_path",
    "ensure_blueprint_manifest",
    "image_dimensions",
    "load_blueprint_manifest",
    "load_provider_host_receipt",
    "load_provider_runtime_receipt",
    "prompt_path",
    "provider_host_receipt_path",
    "provider_receipt_path",
    "record_provider_host_result",
    "safe_image_path",
]
