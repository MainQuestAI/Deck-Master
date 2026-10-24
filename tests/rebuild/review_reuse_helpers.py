"""Synthetic immutable local objects for RP-27; no reviewer execution claim."""

from deck_master import editing, pipeline, review
from deck_master.models import bump_revision
from deck_master.samples import create_sample
from deck_master.store import Store


def assembled_inputs(project, n):
    create_sample(project, page_count=n, readonly=False)
    store = Store(project)
    doc = store.load_document()
    for entry in doc["pages"]:
        original = store.read_object_json(entry["blueprint"])["file"]
        svg = store.put_blob(
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" '
                f'data-blueprint-sha256="{original["sha256"]}"><rect width="960" height="540"/></svg>'
            ).encode(),
            ext="svg",
        )
        entry["svg"] = pipeline.artifact(store, store.project_root / svg["path"], "svg", page_id=entry["page_id"])
        entry["svg_preview"] = pipeline.artifact(
            store, store.project_root / original["path"], "svg_preview", page_id=entry["page_id"], derived_from=[entry["svg"]]
        )
    artifacts = editing._current_artifact_digests(store, doc)
    for entry in doc["pages"]:
        pid = entry["page_id"]
        deps = [
            {"kind": k.split(":", 1)[0], "identity": k.split(":", 1)[1], "sha256": artifacts[k]}
            for k in (f"content:page:{pid}", f"blueprint:{pid}", f"artifact:svg:{pid}", f"style:{pid}")
        ]
        for kind in review.PAGE_VISUAL_KINDS:
            obj = {
                "schema_version": "deck_review.v2",
                "review_id": f"synthetic-{pid}-{kind}",
                "kind": kind,
                "review_stage": "page_visual",
                "status": "pass",
                "subjects": [entry[k] for k in ("page", "blueprint", "svg", "svg_preview")],
                "dependencies": deps,
                "reviewer": {
                    "type": "host_self",
                    "id": "L1-synthetic",
                    "execution_ref": "synthetic-fixture",
                    "independence_confirmed": False,
                },
                "observations": ["Synthetic dependency interpretation, not actual visual approval."],
                "findings": [],
                "created_at": "2026-10-22T00:00:00Z",
                "replaces": None,
            }
            doc["reviews"].append(store.put_json_object(obj))
    # N historical snapshots of the same fixed content, no external production.
    for i in range(n):
        base = store.load_document()
        new = bump_revision(
            doc, {"operation_id": f"history-{i}", "kind": "task_update", "description": "Synthetic fixed graph history", "read_set": []}
        )
        new["parent_revision_id"] = base["revision_id"]
        store.commit_change(base_revision=base["revision_id"], document=new, operation_id=f"history-{i}")
        doc = new
    return store, doc
