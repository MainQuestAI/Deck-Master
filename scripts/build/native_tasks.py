"""Durable host tasks: stable resumes, finite retries, declared page scope."""

from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Any
from native_pptx.contracts import ContractError, read_json, sha256_file, write_json
from high_density.blueprint import blueprint_path
from workflow.actions import action_applied, check_action_budget, read_current_revision

STAGE_STATUS = {"imagegen": "awaiting_agent_imagegen", "reconstruct": "awaiting_agent_reconstruct", "svg": "awaiting_svg_authoring"}


def record_native_failure(root: Path, *, action_id: str, task_id: str, reason: str):
    """A result losing the cancellation race is the same terminated attempt."""
    from workflow.actions import _acquire_run_lock, _release_run_lock, _safe_path, _record_action_failure_locked
    root=Path(root).expanduser().resolve()
    lock=_acquire_run_lock(root)
    try:
        cancelled=_safe_path(root, f"workflow/actions/cancelled/{action_id}.json")
        if cancelled.is_file():
            return read_json(cancelled)
        return _record_action_failure_locked(root, action_id=action_id, task_id=task_id, reason=reason)
    finally:
        _release_run_lock(lock)


def stopped_native_tasks(root: Path) -> list[dict[str, Any]]:
    from workflow.actions import _safe_path
    root=Path(root).expanduser().resolve()
    stopped=[]
    for path in sorted((root / "build/native_tasks").glob("native_*.json")):
        task=read_json(path)
        marker=_safe_path(root, f"workflow/actions/cancelled/{task['action_id']}.json")
        if marker.is_file() and not action_applied(root, task['action_id']):
            stopped.append({**read_json(marker), 'status':'stopped',
                            **{key:task[key] for key in ('action_id','task_id','page_id','run_id','kind')}})
    return stopped


def cancel_native_action(root: Path, action_id: str, *, reason: str) -> dict[str, Any]:
    """Serialize user stop with result commit; never erase its budget evidence."""
    from workflow.actions import _acquire_run_lock, _release_run_lock, _safe_path, _atomic_json, validate_identifier
    from datetime import datetime, timezone
    root=Path(root).expanduser().resolve()
    validate_identifier(action_id, "action_id")
    if not str(reason).strip():
        raise ContractError("native cancellation requires a reason")
    lock=_acquire_run_lock(root)
    try:
        issued=_safe_path(root, f"build/native_tasks/issued/{action_id}.json")
        if not issued.is_file():
            raise ContractError("cancel requires a Runtime-issued action")
        task=read_json(issued)
        task_id=validate_identifier(task.get('task_id'), 'task_id')
        page_id=validate_identifier(task.get('page_id'), 'page_id')
        current=_safe_path(root, f"build/native_tasks/{task_id}.json")
        if task.get('action_id')!=action_id or task.get('run_id')!=root.name or task.get('scope_pages')!=[page_id] or task.get('kind') not in STAGE_STATUS:
            raise ContractError("cancel action does not belong to this run/page")
        if action_applied(root, action_id):
            raise ContractError("committed action cannot be cancelled")
        marker_path=_safe_path(root, f"workflow/actions/cancelled/{action_id}.json")
        if marker_path.is_file():
            return {**read_json(marker_path), 'idempotent':True}
        if not current.is_file() or read_json(current).get('action_id')!=action_id:
            raise ContractError("only the current issued action can be cancelled")
        marker={'status':'stopped','action_id':action_id,'task_id':task_id,'run_id':root.name,
                'page_id':page_id,'kind':task['kind'],'reason':str(reason).strip(),
                'recorded_at':datetime.now(timezone.utc).isoformat()}
        attempts=_safe_path(root, f"workflow/actions/attempts/{action_id}")
        if not attempts.exists() or not any(attempts.glob('*.json')):
            _atomic_json(_safe_path(root, f"workflow/actions/attempts/{action_id}/cancelled.json"), marker)
        _atomic_json(marker_path,marker)
        return marker
    finally:
        _release_run_lock(lock)


def pending_native_task(root: Path) -> dict[str, Any] | None:
    """Return current, fresh host work, including explicitly requested repairs."""
    from build.native_engine import _svg_input_fingerprint
    pages = []
    for path in sorted((root / "build/native_tasks").glob("native_*.json")):
        page = read_json(path)
        if action_applied(root, page["action_id"]):
            continue
        try:
            issued_task(root, page["action_id"], page["page_id"], page["produced_against"], allowed_kinds=set(STAGE_STATUS))
        except ContractError:
            continue
        if page["produced_against"] == _svg_input_fingerprint(root, page["page_id"]):
            pages.append(page)
    if not pages:
        return None
    stage = next(kind for kind in STAGE_STATUS if any(page["kind"] == kind for page in pages))
    return {"schema_version": "deck_host_native_task.v1", "run_id": root.name,
            "engine_id": "deck_native", "stage": stage, "status": STAGE_STATUS[stage],
            "pages": [page for page in pages if page["kind"] == stage]}


def dispatch_native_task(root: Path, stage: str, packages: list[dict[str, Any]], *, resume_cancelled: bool = False) -> dict[str, Any]:
    from workflow.actions import _acquire_run_lock, _release_run_lock

    root = Path(root).expanduser().resolve()
    lock = _acquire_run_lock(root)
    try:
        from workflow.actions import revision_read
        with revision_read(root, fresh=True):
            from build.native_engine import _approved_packages
            ids = {p["page_id"] for p in packages}
            current = [p for p in _approved_packages(root) if p["page_id"] in ids]
            if {p["page_id"] for p in current} != ids:
                raise ContractError("native dispatch page is outside the approved run")
            stopped=[task for task in stopped_native_tasks(root) if task['page_id'] in ids]
            if stopped and (not resume_cancelled or not any(task['kind']==stage for task in stopped)):
                raise ContractError("native page is stopped; explicitly retry its cancelled stage")
            return _dispatch_native_task_locked(root, stage, current)
    finally:
        _release_run_lock(lock)


def _dispatch_native_task_locked(root: Path, stage: str, packages: list[dict[str, Any]]) -> dict[str, Any]:
    from build.native_engine import _svg_input_fingerprint
    from high_density.content import load_content_lock
    from workflow.actions import revision_input_path

    if stage not in STAGE_STATUS:
        raise ContractError(f"unknown native stage: {stage}")
    request = read_json(root / "request.json")
    limit = int(request.get("native_max_actions", 3))
    if limit < 1 or limit > 20:
        raise ContractError("native_max_actions must be between 1 and 20")
    pages = []
    for package in packages:
        page_id = str(package["page_id"])
        fingerprint = _svg_input_fingerprint(root, page_id)
        task_id = f"native_{stage}_{page_id}"
        budget = check_action_budget(root, task_id, max_actions=limit)
        if budget["exhausted"]:
            raise ContractError(f"native task {task_id} budget exhausted; repair inputs or explicitly increase native_max_actions")
        task_file = root / "build/native_tasks" / f"{task_id}.json"
        prior = read_json(task_file) if task_file.exists() else {}
        action_id = str(prior.get("action_id") or "")
        # Failures and completed actions are new attempts, ordinary polling
        # retains the same action identity and does not consume the budget.
        from workflow.actions import _actions_root

        attempts = _actions_root(root) / "attempts" / action_id
        reuse = bool(
            action_id
            and prior.get("produced_against") == fingerprint
            and prior.get("status") not in {"cancelled", "superseded"}
            and not (_actions_root(root) / "cancelled" / f"{action_id}.json").exists()
            and not action_applied(root, action_id)
            and not attempts.exists()
        )
        if reuse:
            entry = prior
        else:
            action_id = f"{stage}_{page_id}_{uuid.uuid4().hex}"
            lock = load_content_lock(root, page_id)
            blueprint = approved_blueprint(root, page_id)
            entry = {
                "action_id": action_id,
                "task_id": task_id,
                "kind": stage,
                "page_id": page_id,
                "scope_pages": [page_id],
                "run_id": root.name,
                "build_revision": read_current_revision(root).get("revision_id", ""),
                "produced_against": fingerprint,
                "input_fingerprint": fingerprint,
                "input_refs": [
                    {"ref": f"page_packages/{page_id}.json", "sha256": sha256_file(revision_input_path(root, root / "page_packages" / f"{page_id}.json"))},
                    {
                        "ref": f"high_density_build/content_locks/{page_id}.content_lock.json",
                        "sha256": sha256_file(revision_input_path(root, root / "high_density_build/content_locks" / f"{page_id}.content_lock.json")),
                    },
                ],
                "content_lock": lock,
                "budget": {"max_actions": limit},
                "remaining_budget": budget["remaining"],
                "required_tools": ["image_generation", "image_read"] if stage == "imagegen" else ["svg_authoring", "image_read"],
                "output_contract": {
                    "kind": "blueprint_image" if stage == "imagegen" else "svg_and_scene",
                    "files": ["blueprint.png"] if stage == "imagegen" else ["page.svg", "scene.json"],
                    "submit": "deck-master build submit --run-dir <run> --page-id <page> --action-id <action> --produced-against <fingerprint> --svg <svg> --scene <scene>"
                    if stage != "imagegen"
                    else "deck-master build submit --run-dir <run> --page-id <page> --action-id <action> --produced-against <fingerprint> --blueprint <image> --observation <json>",
                },
                "acceptance_command": "deck-master build submit",
                "resume_command": "deck-master build run --run-dir <run>",
                "blueprint_brief": dict(package.get("customer_visible") or {}),
            }
            if blueprint:
                entry["blueprint_ref"] = blueprint.relative_to(root).as_posix()
                entry["blueprint_sha256"] = sha256_file(blueprint)
            write_json(task_file, entry)
            write_json(root / "build/native_tasks/issued" / f"{action_id}.json", entry)
        pages.append(entry)
    task = {
        "schema_version": "deck_host_native_task.v1",
        "run_id": root.name,
        "stage": stage,
        "status": STAGE_STATUS[stage],
        "engine_id": "deck_native",
        "pages": pages,
    }
    write_json(root / "build/host_imagegen_task.json", task)
    return task


def issued_task(
    root: Path, action_id: str, page_id: str, produced_against: str, *, allowed_kinds: set[str] | None = None
) -> dict[str, Any]:
    import re

    if not re.fullmatch(r"[A-Za-z0-9_-]+", action_id):
        raise ContractError("unsafe native action_id")
    path = root / "build/native_tasks/issued" / f"{action_id}.json"
    if not path.exists():
        raise ContractError("native submit requires a Runtime-issued action")
    task = read_json(path)
    if (
        task.get("run_id") != root.name
        or task.get("scope_pages") != [page_id]
        or task.get("kind") not in (allowed_kinds or {"svg", "reconstruct"})
    ):
        raise ContractError("native action scope or output kind mismatch")
    if task.get("produced_against") != produced_against:
        raise ContractError("native action dispatch fingerprint mismatch")
    from workflow.actions import _actions_root

    if task.get("status") in {"cancelled", "superseded"} or (_actions_root(root) / "cancelled" / f"{action_id}.json").exists():
        raise ContractError("native action is cancelled or superseded")
    task_id = str(task.get("task_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
        raise ContractError("unsafe native task_id")
    current_path = root / "build/native_tasks" / f"{task_id}.json"
    current = read_json(current_path) if current_path.exists() else {}
    if current.get("action_id") != action_id or current.get("status") in {"cancelled", "superseded"}:
        raise ContractError("native action is superseded; use the current task")
    return task


def current_task_fingerprint(
    root: Path, action_id: str, page_id: str, produced_against: str, *, allowed_kinds: set[str] | None = None
) -> str:
    """Called by commit_action_result under the same lock as dispatch.

    Equal content hashes do not authorize a cancelled or replaced action.
    """
    from build.native_engine import _svg_input_fingerprint

    from workflow.actions import revision_read
    with revision_read(root, fresh=True):
        from build.native_engine import _assert_brief_conflicts_resolved
        _assert_brief_conflicts_resolved(root)
        issued_task(root, action_id, page_id, produced_against, allowed_kinds=allowed_kinds)
        return _svg_input_fingerprint(root, page_id)


def approved_blueprint(root: Path, page_id: str) -> Path | None:
    from build.native_engine import _svg_input_fingerprint
    from high_density.content import load_content_lock

    path = blueprint_path(root, page_id)
    lock = load_content_lock(root, page_id)
    if lock.get("enrichment", {}).get("framework") != "native_narrative":
        return path  # legacy approved HD chain owns its own provider receipts
    receipt_path = root / "high_density_build/blueprints" / f"{page_id}.blueprint.json"
    if not receipt_path.exists():
        return None
    receipt = read_json(receipt_path)
    from native_pptx.contracts import safe_run_path

    path = safe_run_path(root, str(receipt.get("image_ref") or ""))
    if not path.is_file():
        return None
    if receipt.get("sha256") != sha256_file(path) or receipt.get("input_content_fingerprint") != _svg_input_fingerprint(
        root, page_id, include_blueprint=False
    ):
        return None
    marker = action_applied(root, str(receipt.get("action_id") or ""))
    return path if marker and marker.get("blueprint_sha256") == receipt["sha256"] else None


def submit_blueprint(
    run_dir: Path | str,
    page_id: str,
    *,
    action_id: str,
    produced_against: str,
    image_path: Path | str,
    observation: dict[str, Any],
    expected_revision: str | None = None,
) -> dict[str, Any]:
    from build.native_engine import _svg_input_fingerprint
    from workflow.actions import stage_action_result, commit_action_result
    from native_pptx.contracts import sha256_json
    from PIL import Image
    import hashlib

    root = Path(run_dir).expanduser().resolve()
    from build.native_engine import _assert_brief_conflicts_resolved
    _assert_brief_conflicts_resolved(root)
    source = Path(image_path).expanduser().resolve()
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    existing = action_applied(root, action_id)
    if existing:
        if (
            existing.get("scope_pages") != [page_id]
            or existing.get("input_fingerprint") != produced_against
            or existing.get("blueprint_sha256") != digest
            or existing.get("observation_sha256") != sha256_json(observation)
        ):
            raise ContractError("blueprint replay has different image or observation")
        return {"status": "already_applied", "revision_id": existing["revision_id"], "page_id": page_id}
    task = issued_task(root, action_id, page_id, produced_against, allowed_kinds={"imagegen"})
    budget = check_action_budget(root, task["task_id"], max_actions=task["budget"]["max_actions"])
    if budget["exhausted"]:
        raise ContractError("native imagegen task budget exhausted")
    try:
        if produced_against != _svg_input_fingerprint(root, page_id):
            raise ContractError("blueprint result input fingerprint is stale")
        if not isinstance(observation, dict) or not all(str(observation.get(field) or "").strip() for field in ("tool", "description")):
            raise ContractError("blueprint requires host observation tool and description")
        import io

        if source.suffix.lower() == ".svg":
            import tempfile
            from xml.etree import ElementTree
            from native_pptx.canvas import image_dimensions

            document = ElementTree.fromstring(data)
            if b"<!DOCTYPE" in data.upper() or document.tag.split("}")[-1] != "svg":
                raise ContractError("blueprint SVG must be a self-contained SVG document")
            for node in document.iter():
                if node.tag.split("}")[-1] in {"script", "foreignObject"}:
                    raise ContractError("unsafe blueprint SVG element")
                for attribute, value in node.attrib.items():
                    name = attribute.split("}")[-1]
                    if name.lower().startswith("on") or (name in {"href", "src"} and not value.startswith(("#", "data:image/"))):
                        raise ContractError("blueprint SVG contains an external or executable reference")
            with tempfile.TemporaryDirectory(prefix="native-blueprint-") as tmp:
                candidate = Path(tmp) / "image.svg"
                candidate.write_bytes(data)
                width, height = image_dimensions(candidate)
            extension = ".svg"
        else:
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                width, height = image.size
                if image.format not in {"PNG", "JPEG"}:
                    raise ContractError("blueprint image must use PNG/JPEG")
                extension = ".png" if image.format == "PNG" else ".jpg"
        if min(width, height) <= 0 or abs(width / height - 16 / 9) > 0.02:
            raise ContractError("blueprint must have a valid 16:9 canvas")
        receipt = {
            "schema_version": "deck_native_blueprint_receipt.v1",
            "run_id": root.name,
            "page_id": page_id,
            "action_id": action_id,
            "sha256": digest,
            "width": width,
            "height": height,
            "input_content_fingerprint": _svg_input_fingerprint(root, page_id, include_blueprint=False),
            "observation": observation,
            "image_ref": f"high_density_build/blueprints/{page_id}{extension}",
        }
        envelope = {
            "schema_version": "deck_stage_action.v1",
            "action_id": action_id,
            "task_id": task["task_id"],
            "scope_pages": [page_id],
            "permission": "agent",
            "input_fingerprint": produced_against,
            "budget": task["budget"],
        }
        stage_action_result(root, envelope, {"image": data, "receipt": json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"})
        marker = commit_action_result(
            root,
            envelope,
            current_input_fingerprint=lambda: current_task_fingerprint(
                root, action_id, page_id, produced_against, allowed_kinds={"imagegen"}
            ),
            targets={"image": root / receipt["image_ref"], "receipt": root / "high_density_build/blueprints" / f"{page_id}.blueprint.json"},
            expected_revision=expected_revision,
            receipt_data={"blueprint_sha256": digest, "observation_sha256": sha256_json(observation)},
        )
    except Exception as exc:
        record_native_failure(root, action_id=action_id, task_id=task["task_id"], reason=str(exc))
        raise
    return {"status": "blueprint_staged", "page_id": page_id, "revision_id": marker["revision_id"], "action_id": action_id}


def approved_svg(root: Path, page_id: str) -> bool:
    """Only committed host pairs may enter the new native compile path."""
    from build.native_engine import _svg_input_fingerprint
    from high_density.content import load_content_lock
    from high_density.scene import load_scene
    from native_pptx.contracts import sha256_json

    svg = root / "high_density_build/svg" / f"{page_id}.svg"
    if not svg.exists():
        return False
    lock = load_content_lock(root, page_id)
    if lock.get("enrichment", {}).get("framework") != "native_narrative":
        return True
    try:
        scene = load_scene(root, page_id)
    except ContractError:
        return False
    if scene.get("content_lock_sha256") != lock["content_lock_sha256"]:
        return False
    for stage in ("svg", "reconstruct"):
        path = root / "build/native_tasks" / f"native_{stage}_{page_id}.json"
        if not path.exists():
            continue
        task = read_json(path)
        marker = action_applied(root, task["action_id"])
        if (
            marker
            and marker.get("input_fingerprint") == _svg_input_fingerprint(root, page_id)
            and marker.get("output_sha256") == sha256_file(svg)
            and marker.get("scene_sha256") == sha256_json(scene)
        ):
            return True
    return False
