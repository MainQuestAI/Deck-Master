"""Read-side design inputs and bounded initial trials; no implied authority."""

from . import changes, eligibility, operations
from .local_state import project_path
from .production import resolve_generation_design
from .snapshots import load_snapshot
from .store import Store


def describe_plan(project, result):
    """Project the same fixed inputs and scope that changes.commit revalidates."""
    store = Store(project_path(project))
    plan = result["plan"]
    value = plan["input"]
    document = load_snapshot(store, plan["base_revision"])
    control = store.load_document()
    actions = plan["actions"]
    context = {
        "external_call_page_ids": [a["page_id"] for a in actions if a["max_calls"] > 0],
        "count": plan["max_calls"],
        "candidate_count": sum(a.get("mode") == "trial" for a in actions),
        "targets": {"page_ids": [a["page_id"] for a in actions], "layers": changes._plan_layers(plan)},
    }
    entries = {e["page_id"]: e for e in document["pages"]}
    basis = []
    for action in actions:
        entry = entries[action["page_id"]]
        resolved = resolve_generation_design(store, document, entry, recipe_ref=value.get("style_recipe_ref"))
        references, target_reference = changes._trial_references(store, document, entry, value)
        for image in resolved.get('asset_inputs', {}).get('images', []):
            attachment = {'file': image['file'], 'role': 'reference'}
            if attachment not in references:
                references.append(attachment)
        basis.append(
            {
                "page_id": entry["page_id"],
                "page_ref": entry["page"],
                "recipe_ref": value.get("style_recipe_ref"),
                "resolved_design_context": resolved,
                "references": references,
                "target_reference_ref": target_reference,
                "original_image_recorded": bool(entry.get("blueprint")),
            }
        )
    return {**result, "production_basis": basis, "eligibility": eligibility.evaluate(store, document, control, "change.commit", context)}


@operations.public
def initial_plan(project, *, input):
    if not isinstance(input, dict) or set(input) != {"page_id", "base_revision", "instruction"}:
        raise operations.OperationError("design_input", "input", "select one page, its revision and a concrete instruction")
    store = Store(project_path(project))
    document = load_snapshot(store)
    entry = next((e for e in document["pages"] if e["page_id"] == input["page_id"]), None)
    if entry is None or entry.get("blueprint"):
        raise operations.OperationError(
            "design_input",
            "page_id",
            "initial design requires a current page without an original; use its existing direction or a repair trial otherwise",
        )
    value = {
        "schema_version": "change_intent.v1",
        "project_id": document["project_id"],
        "base_revision": input["base_revision"],
        "intent": "initial_design",
        "instruction": input["instruction"],
        "annotation_refs": [],
        "max_calls": 1,
        "mode": "trial",
        "references": [],
        "targets": [
            {"page_id": entry["page_id"], "page_ref": entry["page"], "layer": "original_image", "stage": "blueprint", "artifact_ref": None}
        ],
    }
    return describe_plan(project, changes.plan(project, input=value))
