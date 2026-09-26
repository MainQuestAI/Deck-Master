#!/usr/bin/env python3
"""Reproducible W01 reads against a temporary, explicitly synthetic project.

PYTHONPATH=src python examples/workbench/w01_lineage.py --out /tmp/w01-evidence
Add --pages 300 for a base-size sample, or --serve for manual browser checks.
No Host/model runs. No Candidate/Attempt pressure claim. Never edits a user run.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import platform
import signal
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

from deck_master import editing, service, workbench
from deck_master.models import bump_revision, sha256_bytes
from deck_master.pipeline import artifact
from deck_master.store import Store
from deck_master.view import project_view
from deck_master.web import WorkbenchServer


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def create_fixture(root, page_count, browser_fixture=False):
    project = root / "synthetic-project"
    title = '<img src=x onerror="window.__w01_xss=true">' if browser_fixture else "Synthetic page 1"
    draft = {"pages": [{"schema_version": "deck_page_package.v2", "page_id": f"p{i:03}",
                       "customer_visible": {"title": title if i == 1 else f"Synthetic page {i}", "body_blocks": []},
                       "visual_spec": {"intent": "W01 synthetic example", "reference_mode": "new_design"}}
                      for i in range(1, page_count + 1)]}
    service.create(project, brief="W01 synthetic read-only example", draft=draft, page_limit=page_count)
    store = Store(project)
    doc = store.load_document()
    service.open_blueprint_task(store, doc, doc["pages"][0])
    doc = copy.deepcopy(store.load_document())
    png = root / "synthetic.png"
    Image.new("RGB", (320, 180), "#224466").save(png)
    svg = root / "synthetic.svg"
    attack = '<script>window.__w01_svg=true;document.documentElement.setAttribute("data-executed","yes")</script>' if browser_fixture else ""
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">' + attack
                   + '<rect width="320" height="180" fill="#224466"/></svg>', encoding="utf-8")
    for i, entry in enumerate(doc["pages"]):
        if i % 4 == 3:
            continue
        deps = [{"kind": "content", "identity": "page:" + entry["page_id"], "sha256": entry["page"]["sha256"]}]
        entry["blueprint"] = artifact(store, png, "blueprint", page_id=entry["page_id"], dependencies=deps)
        if i % 4 == 0:
            entry["svg"] = artifact(store, svg, "svg", page_id=entry["page_id"], dependencies=deps, derived_from=[entry["blueprint"]])
            entry["svg_preview"] = artifact(store, png, "svg_preview", page_id=entry["page_id"], dependencies=deps, derived_from=[entry["svg"]])
    # Clearly synthetic old-format submitted text; no provider observation claim.
    first = doc["pages"][0]
    blueprint = store.read_object_json(first["blueprint"])
    blueprint["provenance"]["submitted_prompt"] = store.put_blob(b"Synthetic stored Host-reported text; not a live invocation", ext="txt")
    first["blueprint"] = store.put_json_object(blueprint)
    updated = bump_revision(doc, {"operation_id": "synthetic-stages", "kind": "task_update",
                                  "description": "Synthetic W01 fixture only", "read_set": []})
    store.commit_change(base_revision=doc["revision_id"], document=updated, operation_id="synthetic-stages")
    return project, store, draft


def exercise(project, store, base_url, out, count, browser_fixture):
    # IDs are taken from real service results, never invented sample hashes.
    initial = project_view(project)
    revision, page_id = initial["revision_id"], initial["pages"][0]["page_id"]
    query = "?" + urllib.parse.urlencode({"revision": revision})
    routes = ["/api/view", "/api/view/summary", f"/api/pages/{page_id}/lineage", "/api/tasks", "/api/reviews"]
    responses = {route: request(base_url + route + query) for route in routes}
    assert all(status == 200 for status, payload in responses.values())
    assert responses["/api/view/summary"][1] == workbench.workbench_summary(project, revision=revision)
    detail = responses[f"/api/pages/{page_id}/lineage"][1]
    assert detail["prompts"]["prepared"] and detail["prompts"]["submitted"]["observer"] == "host_reported"
    # A genuine later core edit; a pinned read must remain byte-equivalent JSON.
    doc = store.load_document()
    second = doc["pages"][1]  # preserve the first browser attack fixture title
    page = store.read_object_json(second["page"])
    page["customer_visible"]["title"] = "Synthetic later content edit"
    editing.edit_page(project, page=page, base_revision=doc["revision_id"],
                      page_hash=second["page"]["sha256"], operation_id="synthetic-later-edit")
    before = (store.deck_root / "current.json").read_bytes()
    assert {route: request(base_url + route + query) for route in routes} == responses
    assert (store.deck_root / "current.json").read_bytes() == before
    missing = request(base_url + "/api/workbench?revision=not-committed")
    assert missing[0] == 404 and missing[1]["error"]["code"] == "revision_not_found"
    for _ in range(5):
        assert request(base_url + "/api/view/summary")[0] == 200
    samples = []
    for _ in range(100):
        start = time.perf_counter()
        status, summary = request(base_url + "/api/view/summary")
        samples.append((time.perf_counter() - start) * 1000)
        assert status == 200 and summary["page_count"] == count
    write_json(out / "fixed-responses.json", responses)
    write_json(out / "current-summary.json", summary)
    write_json(out / "missing-revision.json", missing)
    metrics = {"synthetic": True, "evidence": "W01 base-size core/HTTP sample",
               "pages": count, "candidate_count": 0, "attempt_count": 0, "concurrent_updates_during_sampling": False,
               "warmup": 5, "samples_ms": samples, "p95_ms": sorted(samples)[math.ceil(len(samples) * .95) - 1],
               "measurement": "client request start through JSON parse; loopback; current summary",
               "environment": {"python": platform.python_version(), "os": platform.platform(), "machine": platform.machine()},
               "full_W01_AC01": "open: requires 300 pages x 5 Candidates x 3 Attempts with background updates"}
    write_json(out / "measurements.json", metrics)
    svg = store.read_object_json(doc["pages"][0]["svg"])["file"]
    manifest = {"synthetic": True, "browser_fixture": browser_fixture, "project_id": initial["project_id"],
                "fixed_revision": revision, "current_revision": store.current_revision_id(), "page_id": page_id,
                "history_read_did_not_write": True, "pointer_sha256": sha256_bytes(before),
                "svg_file_route": "/api/file?" + urllib.parse.urlencode(svg),
                "source_command": "PYTHONPATH=src python examples/workbench/w01_lineage.py --out <new-directory> --pages " + str(count)}
    write_json(out / "manifest.json", manifest)
    print(json.dumps({"status": "passed", "url": base_url, "page_count": count,
                      "p95_ms": metrics["p95_ms"], "AC01": "open"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="new directory for synthetic input/response evidence")
    parser.add_argument("--pages", type=int, default=24)
    parser.add_argument("--serve", action="store_true", help="keep synthetic server alive until Ctrl-C for browser safety checks")
    args = parser.parse_args()
    if args.pages < 2:
        parser.error("at least two pages are needed for the historical-read example")
    args.out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="deck-master-w01-") as scratch:
        project, store, draft = create_fixture(Path(scratch), args.pages, args.serve)
        write_json(args.out / "synthetic-draft.json", draft)
        server = WorkbenchServer(project)
        try:
            url = server.start().rstrip("/")
            exercise(project, store, url, args.out, args.pages, args.serve)
            if args.serve:
                while True:
                    signal.pause()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()


if __name__ == "__main__":
    main()
