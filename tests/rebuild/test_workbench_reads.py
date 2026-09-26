"""W01 synthetic core/HTTP regression evidence; not real Host acceptance."""
import copy
import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from deck_master import cli, editing, service, workbench
from deck_master.models import bump_revision
from deck_master.pipeline import artifact
from deck_master.store import Store
from deck_master.view import project_view
from deck_master.web import WorkbenchServer


def make_project(root, count=24):
    root.mkdir(parents=True, exist_ok=True)
    project = root / "project"
    pages = [{"schema_version": "deck_page_package.v2", "page_id": f"p{i:02}",
              "customer_visible": {"title": f"Synthetic page {i}", "body_blocks": []},
              "visual_spec": {"intent": "W01 synthetic read test", "reference_mode": "new_design"}}
             for i in range(1, count + 1)]
    service.create(project, brief="W01 synthetic evidence", draft={"pages": pages})
    return project, Store(project)


def commit(store, doc, operation):
    current = store.load_document()
    updated = bump_revision({**doc, "revision_id": current["revision_id"]},
                            {"operation_id": operation, "kind": "task_update", "description": "test fixture", "read_set": []})
    store.commit_change(base_revision=current["revision_id"], document=updated, operation_id=operation)
    return updated


def mixed_project(root):
    project, store = make_project(root)
    doc = copy.deepcopy(store.load_document())
    png = root / "synthetic.png"
    from PIL import Image
    Image.new("RGB", (32, 18), "#224466").save(png)
    svg = root / "synthetic.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 18"><rect width="32" height="18"/></svg>')
    for i, entry in enumerate(doc["pages"][:3]):
        dep = [{"kind": "content", "identity": "page:" + entry["page_id"], "sha256": entry["page"]["sha256"]}]
        entry["blueprint"] = artifact(store, png, "blueprint", page_id=entry["page_id"], dependencies=dep)
        if i == 0:
            entry["svg"] = artifact(store, svg, "svg", page_id=entry["page_id"], dependencies=dep, derived_from=[entry["blueprint"]])
            entry["svg_preview"] = artifact(store, png, "svg_preview", page_id=entry["page_id"], dependencies=dep, derived_from=[entry["svg"]])
    commit(store, doc, "mixed-slots")
    return project, store


@pytest.fixture()
def live(tmp_path):
    project, store = mixed_project(tmp_path)
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        yield project, store, url
    finally:
        server.stop()


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_summary_real_order_mixed_layers_and_detail_contract(live):
    project, store, url = live
    summary = get(url + "/api/view/summary")[1]
    assert summary == workbench.workbench_summary(project)
    assert summary == get(url + "/api/workbench")[1]
    assert [p["page_id"] for p in summary["pages"]] == [f"p{i:02}" for i in range(1, 25)]
    assert summary["pages"][0]["stages"]["svg_preview"]["preview_of"]["scope"] == "per_page"
    assert summary["pages"][0]["stages"]["ppt_preview"]["existence"] == "not_generated"
    assert summary["pages"][3]["stages"]["blueprint"]["existence"] == "not_generated"
    assert "page" not in summary["pages"][0]  # no content bodies in polling payload
    lineage = get(url + "/api/pages/p01/lineage")[1]
    assert lineage == workbench.page_lineage(project, "p01")
    assert lineage["page"]["page_id"] == "p01"
    assert lineage["prompts"]["submitted"]["state"] == "not_recorded"
    for name, payload in (("workbench-summary", summary), ("page-lineage", lineage)):
        folder = Path(workbench.__file__).parent / "resources/contracts"
        schema = json.loads((folder / (name + ".v1.schema.json")).read_text())
        shared = json.loads((folder / "workbench-summary.v1.schema.json").read_text())
        registry = Registry().with_resource(shared["$id"], Resource.from_contents(shared))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, registry=registry).validate(payload)


def test_every_related_route_pins_history_and_reads_do_not_write(live):
    project, store, url = live
    before = store.load_document()
    revision = before["revision_id"]
    routes = ["/api/view", "/api/view/summary", "/api/workbench", "/api/pages/p01", "/api/pages/p01/lineage", "/api/tasks", "/api/reviews"]
    baseline = {route: get(url + route + "?revision=" + revision)[1] for route in routes}
    page = store.read_object_json(before["pages"][0]["page"])
    page["customer_visible"]["title"] = "New title after fixed read"
    editing.edit_page(project, page=page, base_revision=revision, page_hash=before["pages"][0]["page"]["sha256"], operation_id="new-title")
    pointer = (store.deck_root / "current.json").read_bytes()
    revisions = sorted(store.revisions_dir.iterdir())
    for route in routes:
        status, payload = get(url + route + "?revision=" + revision)
        assert status == 200
        assert payload == baseline[route]
        assert payload["revision_id"] == revision
    assert (store.deck_root / "current.json").read_bytes() == pointer
    assert sorted(store.revisions_dir.iterdir()) == revisions
    current = workbench.workbench_summary(project)
    assert current["pages"][0]["title"] == "New title after fixed read"
    assert current["pages"][0]["stages"]["blueprint"]["applicability"]["status"] == "basis_changed"
    assert current["pages"][1]["stages"]["blueprint"]["applicability"]["status"] == "current"


@pytest.mark.parametrize("revision", ["not-found", "", "../current", "/tmp/private", "x" * 129])
def test_invalid_history_never_falls_back_or_exposes_paths(live, revision):
    project, store, url = live
    query = urllib.parse.urlencode({"revision": revision})
    for route in ("/api/view", "/api/workbench", "/api/pages/p01", "/api/pages/p01/lineage", "/api/tasks", "/api/reviews"):
        status, payload = get(url + route + "?" + query)
        assert status in (400, 404)
        assert payload["error"]["code"] in ("invalid_revision", "revision_not_found")
        assert str(project) not in json.dumps(payload)
        assert "/tmp/private" not in json.dumps(payload)


@pytest.mark.parametrize("mode", ["copied_foreign", "symlinked_foreign", "orphan", "symlinked_ancestor"])
def test_foreign_or_uncommitted_snapshots_are_not_public(live, tmp_path, mode):
    project, store, url = live
    _, other = make_project(tmp_path / "other", 1)
    rid = other.current_revision_id()
    if mode == "copied_foreign":
        shutil.copy2(other.revisions_dir / (rid + ".json"), store.revisions_dir / (rid + ".json"))
    elif mode == "symlinked_foreign":
        (store.revisions_dir / (rid + ".json")).symlink_to(other.revisions_dir / (rid + ".json"))
    elif mode == "orphan":
        orphan = bump_revision(store.load_document(), {"operation_id": "not-committed", "kind": "task_update", "description": "orphan", "read_set": []})
        store.save_revision(orphan)
        rid = orphan["revision_id"]
    else:
        rid = store.load_document()["parent_revision_id"]
        target = store.revisions_dir / (rid + ".json")
        external = tmp_path / "external-revision.json"
        shutil.copy2(target, external)
        target.unlink()
        target.symlink_to(external)
    status, payload = get(url + "/api/workbench?revision=" + rid)
    assert status == 404
    assert str(tmp_path) not in json.dumps(payload)
    with pytest.raises(workbench.ReadModelError):
        project_view(project, revision=rid)


def test_broken_page_and_artifact_are_local_even_after_warm_cache(live):
    project, store, url = live
    doc = store.load_document()
    workbench.workbench_summary(project)
    refs = [doc["pages"][0]["page"], doc["pages"][1]["blueprint"]]
    for ref in refs:
        (project / ref["path"]).write_bytes(b"corrupted after cache warmed")
    status, payload = get(url + "/api/workbench")
    assert status == 200
    assert payload["pages"][0]["stages"]["content"]["existence"] == "unreadable"
    assert payload["pages"][0]["stages"]["svg"]["existence"] == "recorded"
    assert payload["pages"][1]["stages"]["blueprint"]["existence"] == "unreadable"
    assert payload["pages"][2]["title"] == "Synthetic page 3"
    assert str(project) not in json.dumps(payload)


def test_corrupt_quality_with_ppt_does_not_crash_or_pass(live, tmp_path):
    project, store, url = live
    doc = store.load_document()
    ppt = tmp_path / "synthetic-container.pptx"
    ppt.write_bytes(b"Synthetic corruption fixture, not a real rendered PPT")
    doc["outputs"]["pptx"] = artifact(store, ppt, "pptx")
    ref = store.put_json_object({"synthetic": "will be corrupted"})
    doc["reviews"] = [ref]
    commit(store, doc, "corrupt-review-fixture")
    (project / ref["path"]).write_bytes(b"corrupted")
    status, payload = get(url + "/api/view")
    assert status == 200
    assert payload["quality_error"]["code"] == "object_unreadable"
    assert payload["view_status"] != "ready_for_export"
    assert len(payload["pages"]) == 24


def test_stored_prompts_not_recomputed_or_guessed_as_same_invocation(tmp_path, monkeypatch):
    project, store = make_project(tmp_path, 1)
    doc = store.load_document()
    task = service.open_blueprint_task(store, doc, doc["pages"][0])
    doc = copy.deepcopy(store.load_document())
    task_ref = doc["tasks"][-1]
    request = next(store.read_object_json(r) for r in task["inputs"]
                   if store.read_object_json(r).get("schema_version") == "deck_blueprint_request.v1")
    png = tmp_path / "synthetic.png"
    from PIL import Image
    Image.new("RGB", (16, 9)).save(png)
    ref = artifact(store, png, "blueprint", page_id="p01")
    obj = store.read_object_json(ref)
    obj["provenance"]["submitted_prompt"] = store.put_blob(b"Actual Host-reported text differs", ext="txt")
    obj["provenance"]["generated_from_page"] = doc["pages"][0]["page"]
    doc["pages"][0]["blueprint"] = store.put_json_object(obj)
    commit(store, doc, "synthetic-unlinked-output")
    monkeypatch.setattr("deck_master.production.project_prompt", lambda *a: pytest.fail("must never reconstruct historical prompts"))
    lineage = workbench.page_lineage(project, "p01")
    assert lineage["prompts"]["prepared"][0]["text"] == request["prompt"]
    assert lineage["prompts"]["prepared"][0]["task_ref"] == task_ref
    assert lineage["prompts"]["prepared"][0]["output_relation"] == "unknown"
    assert lineage["prompts"]["submitted"]["text"] == "Actual Host-reported text differs"
    assert lineage["prompts"]["submitted"]["observer"] == "host_reported"
    assert lineage["prompts"]["parameters"]["status"] == "not_recorded"
    assert "permitted_asset_files" not in json.dumps(lineage)
    (project / obj["file"]["path"]).unlink()
    missing_image = workbench.page_lineage(project, "p01")
    assert missing_image["stages"]["blueprint"]["existence"] == "unreadable"
    assert missing_image["prompts"]["submitted"] == lineage["prompts"]["submitted"]
    (project / store.load_document()["pages"][0]["blueprint"]["path"]).write_bytes(b"broken metadata")
    assert workbench.page_lineage(project, "p01")["prompts"]["submitted"]["state"] == "unreadable"


def test_whole_deck_order_and_preview_relationship_is_derived(live, tmp_path):
    project, store, url = live
    doc = copy.deepcopy(store.load_document())
    # A two-page synthetic deck with known ordered SVG dependencies.
    doc["pages"] = doc["pages"][:2]
    doc["pages"][1]["svg"] = artifact(store, tmp_path / "synthetic.svg", "svg", page_id="p02")
    deps = [{"kind": "svg", "identity": e["page_id"], "sha256": e["svg"]["sha256"]} for e in doc["pages"]]
    ppt = tmp_path / "synthetic.pptx"
    ppt.write_bytes(b"synthetic test container")
    doc["outputs"]["pptx"] = artifact(store, ppt, "pptx", dependencies=deps)
    png = tmp_path / "synthetic.png"
    doc["pages"][0]["ppt_preview"] = artifact(store, png, "ppt_preview", page_id="p01", dependencies=deps, derived_from=[doc["pages"][0]["svg"]])
    fixed = commit(store, doc, "whole-deck-fixture")
    lineage = workbench.page_lineage(project, "p01", revision=fixed["revision_id"])
    assert [p["page_id"] for p in lineage["deck_output"]["ordered_pages"]] == ["p01", "p02"]
    assert lineage["deck_output"]["applicability"] == "current"
    assert lineage["stages"]["ppt_preview"]["preview_of"]["relation"] == "derived"
    doc["pages"].reverse()
    commit(store, doc, "synthetic-stale-order")
    assert workbench.workbench_summary(project)["outputs"]["pptx"]["applicability"] == "basis_changed"
    assert workbench.page_lineage(project, "p01", revision=fixed["revision_id"]) == lineage


def test_cli_http_correspondence_and_legacy_service_status(live, capsys):
    project, store, url = live
    rid = store.current_revision_id()
    for flags, route in [(["--summary"], "/api/workbench"), (["--page-id", "p01", "--lineage"], "/api/pages/p01/lineage"), ([], "/api/view")]:
        assert cli.main(["view", "--project", str(project), "--revision", rid, *flags, "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == get(url + route + "?revision=" + rid)[1]
    assert cli.main(["view", "--project", str(project), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["view_status"] == "running"
    for flags in (["--lineage"], ["--summary", "--open"], ["--summary", "--page-id", "p01"], ["--page-id", ""]):
        assert cli.main(["view", "--project", str(project), *flags]) == 2
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_input"
    assert cli.main(["view", "--project", str(project), "--revision", "missing"]) == 2
    assert json.loads(capsys.readouterr().err) == get(url + "/api/view?revision=missing")[1]


def test_new_gets_keep_host_boundary_and_no_read_token(live):
    project, store, url = live
    for route in ("/api/workbench", "/api/view/summary", "/api/pages/p01/lineage"):
        assert get(url + route)[0] == 200
        assert get(url + route, {"Host": "attacker.example"})[0] == 403
    assert get(url + "/api/workbench?revision=&revision=missing")[0] == 400
    assert get(url + "/api/pages/no-such-page/lineage")[0] == 404


def test_schema_invalid_objects_stay_local_and_cannot_turn_quality_green(live, tmp_path):
    project, store, url = live
    doc = copy.deepcopy(store.load_document())
    page = store.read_object_json(doc["pages"][0]["page"])
    page["customer_visible"] = ["malformed, but a valid JSON object and hash"]
    doc["pages"][0]["page"] = store.put_json_object(page)
    ppt = tmp_path / "synthetic.pptx"
    ppt.write_bytes(b"not a real PPT")
    doc["outputs"]["pptx"] = artifact(store, ppt, "pptx")
    doc["reviews"] = [store.put_json_object({"schema_version": "deck_review.v1", "status": "pass", "reviewer": []})]
    commit(store, doc, "schema-invalid-fixtures")
    summary = get(url + "/api/workbench")[1]
    assert summary["pages"][0]["stages"]["content"]["existence"] == "unreadable"
    assert summary["pages"][1]["title"] == "Synthetic page 2"
    for route in ("/api/view", "/api/reviews", "/api/pages/p01/lineage", "/api/pages/p01"):
        assert get(url + route)[0] == 200
    view = get(url + "/api/view")[1]
    assert view["reviews"][0]["status"] == "unreadable"
    assert view["view_status"] != "ready_for_export"


def test_project_missing_is_typed_and_projection_cannot_mutate_cache(tmp_path):
    with pytest.raises(workbench.ReadModelError) as error:
        workbench.workbench_summary(tmp_path / "missing")
    assert error.value.error_code == "project_unavailable"
    project, store = make_project(tmp_path, 1)
    doc = store.load_document()
    service.open_blueprint_task(store, doc, doc["pages"][0])
    expected = workbench.page_lineage(project, "p01")
    changed = workbench.page_lineage(project, "p01")
    changed["tasks"][0]["scope_pages"].append("p99")
    changed["tasks"][0]["result_refs"].append({"path": "poison"})
    changed["page"]["customer_visible"]["title"] = "poison"
    assert workbench.page_lineage(project, "p01") == expected


def test_wrong_page_artifact_does_not_supply_a_prompt_or_preview(live):
    project, store, url = live
    doc = copy.deepcopy(store.load_document())
    doc["pages"][0]["blueprint"] = doc["pages"][1]["blueprint"]
    commit(store, doc, "wrong-page-fixture")
    lineage = get(url + "/api/pages/p01/lineage")[1]
    assert lineage["page_id"] == "p01"
    assert lineage["stages"]["blueprint"]["existence"] == "unreadable"
    assert lineage["prompts"]["submitted"]["state"] == "unreadable"
    assert lineage["prompts"]["submitted"]["text"] is None
    assert get(url + "/api/pages/p02/lineage")[1]["stages"]["blueprint"]["existence"] == "recorded"


def test_invalid_document_reference_never_echoes_a_private_path(live):
    project, store, url = live
    doc = store.load_document()
    doc["pages"][0]["blueprint"] = {"path": "/private/unrelated-project/private.png", "sha256": "b" * 64}
    (store.revisions_dir / (doc["revision_id"] + ".json")).write_text(json.dumps(doc))
    for route in ("/api/workbench", "/api/view", "/api/pages/p01", "/api/pages/p01/lineage", "/api/tasks", "/api/reviews"):
        status, payload = get(url + route)
        assert status == 404
        assert payload["error"]["code"] == "revision_unavailable"
        assert "/private/" not in json.dumps(payload)
