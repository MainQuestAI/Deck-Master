"""Method source resolution and per-task dispatch (spec v1.1 §3.4, §7.1).

There is exactly one editable method source: ``skills/deck-master/`` in this
repository. Installed builds carry a byte-identical copy under
``deck_master/resources/skill`` (the build hook copies it from canonical).
``resolve_root`` picks the right root for the running installation and never
borrows files from the current working directory.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import MethodResourceMissing
from .models import canonical_json_bytes, sha256_bytes

METHOD_RELEASE_ID = "flow-quality-v1.1"

RELATIVE_PATHS = {
    "source-reading": "references/source-reading.md",
    "content-methods": "references/content-methods.md",
    "content-examples": "references/content-examples.md",
    "input-update": "references/input-update.md",
    "blueprint-svg": "references/blueprint-svg.md",
    "review-and-repair": "references/review-and-repair.md",
}

# Task kind / intent -> method ids (spec §3.4). compose/initial may consult
# the examples; an input revision additionally reads the update method.
_INITIAL_METHODS = ("source-reading", "content-methods", "content-examples")
_INPUT_REVISION_METHODS = ("source-reading", "content-methods", "content-examples", "input-update")
_RECONSTRUCTION_METHODS = ("blueprint-svg",)
_REVIEW_METHODS = ("review-and-repair",)
_REPAIR_METHODS = ("review-and-repair", "content-methods", "blueprint-svg")

_PYPROJECT_NAME_PATTERN = re.compile(r'(?m)^\s*name\s*=\s*"deck-master"\s*$')


def resolve_root() -> Path:
    """The readable method root for this installation, canonical first."""
    from importlib import resources

    import deck_master

    packaged = Path(str(resources.files("deck_master"))).resolve() / "resources" / "skill"
    if (packaged / "SKILL.md").is_file():
        return packaged
    module_file = Path(deck_master.__file__).resolve()
    if module_file.parent.name == "deck_master" and module_file.parents[1].name == "src":
        repo = module_file.parents[2]
        pyproject = repo / "pyproject.toml"
        if pyproject.is_file() and _PYPROJECT_NAME_PATTERN.search(pyproject.read_text(encoding="utf-8")):
            canonical = repo / "skills" / "deck-master"
            if (canonical / "SKILL.md").is_file():
                return canonical
    raise MethodResourceMissing(
        "method root",
        "no readable deck-master method source for this installation; reinstall the package",
    )


def method_ids_for(kind: str, *, intent: str | None = None) -> tuple[str, ...]:
    if kind == "compose":
        return _INPUT_REVISION_METHODS if intent == "input_revision" else _INITIAL_METHODS
    if kind in ("blueprint", "reconstruct"):
        return _RECONSTRUCTION_METHODS
    if kind == "review":
        return _REVIEW_METHODS
    if kind == "repair":
        return _REPAIR_METHODS
    return ()


def method_resources(kind: str, *, intent: str | None = None) -> list[dict]:
    """Readable method entries for one task kind: id, path inside the skill, sha256."""
    root = resolve_root()
    items = []
    for method_id in method_ids_for(kind, intent=intent):
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
    return {"release_id": METHOD_RELEASE_ID, "methods_sha256": methods_sha256(items)}
