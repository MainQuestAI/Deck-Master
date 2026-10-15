"""Method source resolution and per-task dispatch (spec v1.1 §3.4, §7.1).

There is exactly one editable method source: ``skills/deck-master/`` in this
repository. Installed builds carry a byte-identical copy under
``deck_master/resources/skill`` (the build hook copies it from canonical).
``resolve_root`` picks the right root for the running installation and never
borrows files from the current working directory.
"""

from __future__ import annotations

import re
import json
import sys
from pathlib import Path

from .errors import MethodResourceMissing
from .models import canonical_json_bytes, sha256_bytes

from . import __version__

RELATIVE_PATHS = {
    "collaboration-routing": "references/collaboration-routing.md",
    "physical-units": "references/physical-units.md",
    "style-calibration": "references/style-calibration.md",
    "candidates-and-stages": "references/candidates-and-stages.md",
    "icon-quality": "references/icon-quality.md",
    "visual-reference": "references/visual-reference.md",
    "source-reading": "references/source-reading.md",
    "content-methods": "references/content-methods.md",
    "content-examples": "references/content-examples.md",
    "content-calibration": "references/content-calibration.md",
    "input-update": "references/input-update.md",
    "blueprint-svg": "references/blueprint-svg.md",
    "review-and-repair": "references/review-and-repair.md",
}

# Task kind / intent -> method ids (spec §3.4). compose/initial may consult
# the examples; an input revision additionally reads the update method.
_INITIAL_METHODS = ("source-reading", "content-methods", "content-examples")
_INPUT_REVISION_METHODS = ("source-reading", "content-methods", "content-examples", "input-update")
_RECONSTRUCTION_METHODS = ("blueprint-svg", "physical-units")
_REVIEW_METHODS = ("review-and-repair", "physical-units")
_REPAIR_METHODS = ("review-and-repair", "content-methods", "blueprint-svg", "physical-units")

# compose.v2 phases (content collaboration v1.2 CONTRACTS §5). Each phase reads
# the shared reading discipline, its own method section, and the concrete
# examples: the four-phase content method lives in content-methods.md.
_PHASE_METHODS = {
    "framing": ("source-reading", "content-methods", "content-examples"),
    "argument": ("source-reading", "content-methods", "content-examples"),
    "page_copy": ("source-reading", "content-methods", "content-examples"),
    "speech": ("content-methods", "content-examples"),
    "design": ("content-methods", "visual-reference", "physical-units"),
    "production": ("content-methods", "visual-reference", "physical-units"),
    "review": ("review-and-repair", "content-methods", "physical-units"),
    "delivery": ("content-methods", "review-and-repair", "physical-units"),
}

_PYPROJECT_NAME_PATTERN = re.compile(r'(?m)^\s*name\s*=\s*"deck-master"\s*$')


def resolve_root() -> Path:
    """The readable method root for this installation, canonical first."""
    from importlib import resources

    import deck_master

    module_file = Path(deck_master.__file__).resolve()
    if module_file.parent.name == "deck_master" and module_file.parents[1].name == "src":
        repo = module_file.parents[2]
        pyproject = repo / "pyproject.toml"
        if pyproject.is_file() and _PYPROJECT_NAME_PATTERN.search(pyproject.read_text(encoding="utf-8")):
            canonical = repo / "skills" / "deck-master"
            if (canonical / "SKILL.md").is_file():
                return canonical
            raise MethodResourceMissing("method root", "canonical checkout Skill is missing; do not borrow packaged methods")
    packaged = Path(str(resources.files("deck_master"))).resolve() / "resources" / "skill"
    if (packaged / "SKILL.md").is_file():
        return packaged
    raise MethodResourceMissing(
        "method root",
        "no readable deck-master method source for this installation; reinstall the package",
    )


def method_ids_for(kind: str, *, intent: str | None = None,
                   phase: str | None = None) -> tuple[str, ...]:
    if kind == "review" and intent == "preproduction":
        return ("source-reading", "content-methods", "content-examples", "content-calibration", "review-and-repair")
    if kind == "style_analyze":
        return ("visual-reference",)
    if kind == "compose":
        if phase and phase in _PHASE_METHODS and intent != "input_revision":
            return _PHASE_METHODS[phase]
        return _INPUT_REVISION_METHODS if intent == "input_revision" else _INITIAL_METHODS
    if kind in ("blueprint", "reconstruct"):
        return _RECONSTRUCTION_METHODS
    if kind == "review":
        return _REVIEW_METHODS
    if kind == "repair":
        return _REPAIR_METHODS
    return ()


def method_resources(kind: str, *, intent: str | None = None,
                     phase: str | None = None) -> list[dict]:
    """Readable method entries for one task kind: id, path inside the skill, sha256."""
    root = resolve_root()
    items = []
    for method_id in method_ids_for(kind, intent=intent, phase=phase):
        relative = RELATIVE_PATHS[method_id]
        path = root / relative
        if not path.is_file():
            raise MethodResourceMissing(
                f"method_resources/{method_id}", f"declared method file is missing: {path}"
            )
        items.append(
            {
                "id": method_id,
                "relative_path": relative,
                "path": str(path),
                "sha256": sha256_bytes(path.read_bytes()),
            }
        )
    return items


def methods_sha256(items: list[dict]) -> str:
    """One digest over the dispatched method set, for method_release tracing."""
    return sha256_bytes(canonical_json_bytes([[i["relative_path"], i["sha256"]] for i in items]))


def method_release(items: list[dict]) -> dict:
    release_id = __version__
    prefix = Path(sys.prefix).resolve()
    manifest = prefix.parent / 'release.json'
    if Path(__file__).resolve().is_relative_to(prefix) and manifest.is_file():
        release_id = json.loads(manifest.read_text(encoding='utf-8'))['release_id']
    return {"release_id": release_id, "methods_sha256": methods_sha256(items)}


def read_methods(kind: str, *, intent=None, phase=None) -> list[dict]:
    """Return the exact UTF-8 bytes, with no universal-newline conversion."""
    items = method_resources(kind, intent=intent, phase=phase)
    for item in items:
        raw = Path(item["path"]).read_bytes()
        if sha256_bytes(raw) != item["sha256"]:
            raise MethodResourceMissing(item["relative_path"], "method changed while being read; retry")
        item["content"] = raw.decode("utf-8")
    return items


def read_task_methods(project, task_id: str) -> dict:
    """Load a real work order's methods; expose an old basis without relabeling it."""
    from . import service
    from .store import Store
    store = Store(Path(project).expanduser())
    document = store.load_document()
    task = next((store.read_object_json(ref) for ref in document["tasks"]
                 if store.read_object_json(ref)["task_id"] == task_id), None)
    if task is None:
        raise MethodResourceMissing("task_id", "task is not referenced by the current project")
    order = service.task_summary(store, document, task)
    items = _read_entries(order["method_resources"])
    return {"schema_version": "method_consumption.v1", "status": order["method_basis_status"],
            "project_id": document["project_id"], "task_id": task_id,
            "dispatch_revision": task.get("dispatch_revision"),
            "dispatch_method_release": task.get("method_release"),
            "current_method_release": method_release(items), "methods": items,
            "consumption": "runtime_returned_bytes", "work_order": order,
            "limitations": ["Returning method bytes does not prove the Host applied them",
                            "basis_changed does not retroactively update the dispatched task"]}


PUBLIC_SKILLS = ("deck-master", "deck-content", "deck-design", "deck-review")
ENTRY_MODES = ("named", "natural", "master", "recovery")
_ROLE_METHODS = {
    "deck-master": ("collaboration-routing", "input-update", "review-and-repair"),
    "deck-content": ("collaboration-routing", "source-reading", "content-methods", "content-examples", "input-update"),
    "deck-design": ("collaboration-routing", "visual-reference", "style-calibration", "candidates-and-stages", "blueprint-svg", "physical-units"),
    "deck-review": ("collaboration-routing", "source-reading", "content-methods", "review-and-repair", "physical-units"),
}
_ROLE_TASKS = {
    "deck-content": ("compose",),
    "deck-design": ("style_analyze", "blueprint", "reconstruct", "repair"),
    "deck-review": ("review",),
}


def route_request(text: str) -> dict:
    """Conservative responsibility suggestion; never a grant or stored Request.

    Explicit names take precedence. Unclear/mixed production stays with Master;
    the actual Host resolves meaning against the existing Runtime request.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("natural routing requires the original non-empty instruction")
    original = text.casefold()
    # Read role/sub-intent signals from affirmative clauses. The original text
    # remains the input/evidence; exclusions such as "不要讲稿" never become a
    # positive speech request merely because their noun appears in the text.
    normalized = ' '.join(re.split(
        r"不要|不需要|无需|勿|不(?=改|写|做|审|制作|生图|执行|修复)|\b(?:do\s+not|don't|without|no)\b",
        clause, maxsplit=1)[0] for clause in re.split(r'[,，。；;!！?？\n]', original))
    # Recovery is a command about this work session/project, not a substring
    # found inside the user's subject matter (e.g. recovery procedures).
    recovery = bool(re.search(
        r'^(?:请|帮我|麻烦)?\s*(?:恢复|继续|续作)(?:(?:上次|之前|原来|现有|这个|此|当前|未完成)(?:的)?)?'
        r'(?:项目|任务|会话|工作|制作|流程|ppt|演示文稿)', normalized)
        or re.search(r'^(?:please\s+)?(?:resume|continue|recover)\s+'
            r'(?:(?:the|this|our|existing|previous|current|last)\s+)*'
            r'(?:project|session|task|work|workflow|deck|presentation)\b', normalized))
    explicit = re.findall(r"(?<![a-z0-9_-])deck-(?:master|content|design|review)(?![a-z0-9_-])", normalized)
    review_command = bool(re.search(
        r'^(?:(?:请|麻烦|帮我|先|只|仅|我想|给我)\s*)*(?:只审|只读|审查|审稿|审阅|复核|审核)', normalized)
        or re.search(r'^(?:(?:please|only|just|can you|could you)\s+)*'
            r'(?:review|audit|critique|inspect)\b', normalized))
    coordination_command = bool(re.search(
        r'^(?:(?:请|麻烦|帮我|先|只|仅|我想|给我)\s*)*(?:协调|统筹|编排|衔接)', normalized)
        or re.search(r'^(?:(?:please|only|just|can you|could you)\s+)*'
            r'(?:coordinate|orchestrate)\b', normalized))
    if explicit:
        skill = explicit[0] if len(set(explicit)) == 1 else "deck-master"
    elif review_command:
        skill = "deck-review"
    elif recovery or coordination_command or any(word in normalized for word in ("完整ppt", "整套ppt", "完整作品", "full deck", "complete deck")):
        skill = "deck-master"
    elif any(word in normalized for word in ("样页", "设计方案", "视觉方案", "版式", "sample page", "design", "layout")):
        skill = "deck-design"
    elif any(word in normalized for word in ("策划", "规划", "大纲", "写稿", "逐页稿", "正文", "口播", "讲稿", "内容包", "plan", "write", "manuscript", "speech", "content")):
        skill = "deck-content"
    else:
        skill = "deck-master"
    content_intent = None
    if skill == "deck-content":
        if any(word in normalized for word in ("完整内容", "内容包", "content_full", "content package")):
            content_intent = "content_full"
        elif any(word in normalized for word in ("口播", "讲稿", "speech", "speaker notes")):
            content_intent = "speech_only"
        elif any(word in normalized for word in ("写稿", "逐页稿", "正文", "write", "manuscript")):
            content_intent = "write_only"
        else:
            content_intent = "plan_only"
    return {"skill": skill, "content_intent": content_intent, "explicit_name": bool(explicit),
            "authority": "routing_suggestion_only"}


def route_skill(text: str) -> str:
    return route_request(text)["skill"]


def _read_entries(entries) -> list[dict]:
    """Read exactly the actual workorder/manifest list; no extra fifth method."""
    root = resolve_root().resolve()
    items = []
    seen = set()
    for entry in entries:
        method_id = entry.get("id")
        relative = entry.get("relative_path")
        if method_id not in RELATIVE_PATHS or RELATIVE_PATHS[method_id] != relative or method_id in seen:
            raise MethodResourceMissing(str(relative), "unknown or duplicate declared method resource")
        seen.add(method_id)
        path = Path(entry["path"])
        if path.resolve() != root / relative or not path.is_file():
            raise MethodResourceMissing(relative, "declared method is missing or outside this installation")
        raw = path.read_bytes()
        if sha256_bytes(raw) != entry["sha256"]:
            raise MethodResourceMissing(relative, "declared method bytes changed; re-read the workorder")
        items.append({**entry, "content": raw.decode("utf-8")})
    return items


def _read_ids(ids) -> list[dict]:
    root = resolve_root()
    entries = []
    for method_id in dict.fromkeys(ids):
        relative = RELATIVE_PATHS[method_id]
        path = root / relative
        if not path.is_file():
            raise MethodResourceMissing(relative, "declared shared method is missing")
        entries.append({"id": method_id, "relative_path": relative, "path": str(path),
                        "sha256": sha256_bytes(path.read_bytes())})
    return _read_entries(entries)


def read_skill_methods(skill: str, *, entry_mode="named", project=None, task_id=None, text=None) -> dict:
    """Read one responsibility's actual bytes plus current, read-only context.

    This does not create a project, dispatch a Task, grant scope, claim independent
    identity or execute a model. A role can finish independently of full_deck.
    """
    if skill not in PUBLIC_SKILLS:
        raise ValueError("unknown public Skill")
    if entry_mode not in ENTRY_MODES:
        raise ValueError("unknown Skill entry mode")
    route = route_request(text) if entry_mode == "natural" else None
    if route and route["skill"] != skill:
        raise ValueError(f"instruction routes to {route['skill']}; preserve its responsibility")
    if entry_mode in ("master", "recovery") and project is None:
        raise ValueError("Master handoff/recovery requires the existing project")
    if task_id is not None and project is None:
        raise ValueError("task method consumption requires its real project")
    context = None
    dispatch = None
    if project is not None:
        from . import content_production, service
        from .store import Store
        store = Store(Path(project).expanduser())
        document = store.load_document()
        request = (document.get("collaboration") or {}).get("request")
        context = {"project_id": document["project_id"], "artifact_revision_id": document["revision_id"],
                   "request": request,
                   "completion": content_production.completion_status(store, document)}
        if task_id is not None:
            task = next((item for ref in document["tasks"]
                         if (item := store.read_object_json(ref))["task_id"] == task_id), None)
            if task is None:
                raise MethodResourceMissing("task_id", "task is not referenced by the current project")
            if skill != "deck-master" and task["kind"] not in _ROLE_TASKS[skill]:
                raise ValueError(f"{skill} does not execute {task['kind']}; hand off to the responsible role")
            order = service.task_summary(store, document, task)
            dispatch_items = _read_entries(order["method_resources"])
            dispatch = {"task_id": task_id, "work_order": order, "status": order["method_basis_status"],
                        "dispatch_method_release": task.get("method_release"),
                        "current_method_release": method_release(dispatch_items), "methods": dispatch_items}
    # A Task consumes its actual manifest verbatim, including a declared missing
    # calibration error. Role entry guidance is separate and never adds a
    # calibration file to an A/B content-method control.
    items = dispatch["methods"] if dispatch else _read_ids(_ROLE_METHODS[skill])
    entry_methods = _read_ids(("collaboration-routing",)) if dispatch else []
    return {"schema_version": "skill_method_consumption.v1", "skill": skill, "entry_mode": entry_mode,
            "route": route, "context": context, "dispatch": dispatch,
            "method_release": method_release(items), "methods": items, "entry_methods": entry_methods,
            "consumption": "runtime_returned_bytes", "host_application": "not_recorded",
            "limitations": ["Returned bytes are not evidence of model application or independent review",
                            "Routing and Skill names never create authorization or independent identity"]}
