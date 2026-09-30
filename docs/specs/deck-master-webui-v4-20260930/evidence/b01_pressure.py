"""B01 warm summary pressure probe on a synthetic 300x5x3 project.

Builds a temporary project with 300 pages, 5 recorded candidates per page and
3 generation attempts per page (no model calls, no Host), then measures warm
``workbench_summary`` latency. The recorded fixture is synthetic evidence for
the read model only; it is not a production run and not real Host acceptance.
"""
import copy
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from deck_master import generation, tasks, workbench  # noqa: E402
from deck_master.models import (bump_revision, canonical_json_bytes, content_identity,  # noqa: E402
                                require_writer, sha256_bytes, validate_schema)
from deck_master.pipeline import artifact  # noqa: E402
from deck_master.samples import create_sample  # noqa: E402
from deck_master.store import Store  # noqa: E402

PAGES = 300
CANDIDATES_PER_PAGE = 5
ATTEMPTS_PER_PAGE = 3
WARM_RUNS = 120
P95_BUDGET_MS = 250.0


def build(tmp):
    from PIL import Image
    project = Path(tmp) / "pressure-300x5x3"
    create_sample(project, page_count=PAGES, readonly=False)
    store = Store(project)
    png = Path(tmp) / "synthetic.png"
    Image.new("RGB", (32, 18), "#224466").save(png)

    doc = copy.deepcopy(store.load_document())
    now_ms = time.time_ns() // 1_000_000
    candidate_refs, adoption_records = [], []
    for entry in doc["pages"]:
        page_id = entry["page_id"]
        task_id = "task-" + page_id
        prompt = f"synthetic pressure prompt for {page_id}"
        prepared_ref = store.put_json_object(
            {"schema_version": "deck_blueprint_request.v1", "page_id": page_id,
             "prompt": prompt, "prompt_sha256": sha256_bytes(prompt.encode("utf-8"))})
        task = tasks.new_task(task_id=task_id, operation_id=f"op-{task_id}", kind="blueprint",
                              scope_pages=[page_id], instruction="synthetic pressure task",
                              inputs=[entry["page"], prepared_ref], dependencies=[],
                              dispatch_revision=doc["revision_id"], produced_against=content_identity(doc),
                              call_allowances=[{"allowance_id": f"call-{index}", "state": "consumed",
                                                "execution_ref": "synthetic-pressure-host",
                                                "invocation_ref": None, "evidence": []}
                                               for index in range(ATTEMPTS_PER_PAGE)])
        task.update(generation.protocol_fields(doc))
        base_input = generation.prepared_input(store, doc, task)
        request_refs, attempt_refs = [], []
        for index in range(ATTEMPTS_PER_PAGE):
            value = copy.deepcopy(base_input)
            value["prompt"] = f"{prompt} variant {index}"
            request = {"schema_version": "generation_request.v1", "request_id": f"req-{page_id}-{index}",
                       "task_id": task_id, "project_id": doc["project_id"], "operation_id": f"op-{task_id}",
                       "input_hash": sha256_bytes(canonical_json_bytes(value)), "input": value,
                       "created_at_ms": now_ms + index}
            validate_schema("generation_request", request)
            request_refs.append(store.put_json_object(request))
            attempt = {"schema_version": "generation_attempt.v1", "attempt_id": f"att-{page_id}-{index}",
                       "task_id": task_id, "project_id": doc["project_id"], "request_ref": request_refs[-1],
                       "allowance_id": f"call-{index}", "execution_ref": "synthetic-pressure-host",
                       "started_at_ms": now_ms + index, "previous_ref": attempt_refs[-1] if attempt_refs else None,
                       "observations": [], "output_refs": []}
            validate_schema("generation_attempt", attempt)
            attempt_refs.append(store.put_json_object(attempt))
        page_candidates = []
        for index in range(CANDIDATES_PER_PAGE):
            result_ref = artifact(store, png, "blueprint", page_id=page_id,
                                  dependencies=[{"kind": "content", "identity": "page:" + page_id,
                                                 "sha256": entry["page"]["sha256"]}])
            candidate = {"schema_version": "candidate.v1", "candidate_id": f"candidate-{page_id}-{index}",
                         "project_id": doc["project_id"], "task_id": task_id,
                         "created_at": tasks._utc_now_iso(), "page_id": page_id, "stage": "blueprint",
                         "base_revision": doc["revision_id"],
                         "generation_basis": {"page_ref": entry["page"], "input_digest": "0" * 64,
                                              "design_digest": "0" * 64, "blueprint_ref": None},
                         "request_ref": request_refs[0], "attempt_ref": attempt_refs[0],
                         "target_ref": entry.get("blueprint"), "result_ref": result_ref, "status": "available"}
            validate_schema("candidate", candidate)
            ref = store.put_json_object(candidate)
            page_candidates.append(ref)
            candidate_refs.append(ref)
        task["status"] = "completed"
        task["generation_requests"] = request_refs
        task["generation_attempts"] = attempt_refs
        task["candidate_refs"] = page_candidates
        task["result_refs"] = [*page_candidates]
        # adopt candidate 0 exactly like the writer does: move the slot and
        # append the adoption record the summary counts decided candidates from
        entry["blueprint"] = store.read_object_json(page_candidates[0])["result_ref"]
        adoption_records.append({"candidate_id": f"candidate-{page_id}-0", "candidate_ref": page_candidates[0],
                                 "page_id": page_id, "stage": "blueprint",
                                 "result_ref": entry["blueprint"], "revision_id": doc["revision_id"]})
        doc["tasks"] = [*doc["tasks"], store.put_json_object(task)]
    doc["candidates"] = candidate_refs
    doc["candidate_adoptions"] = adoption_records
    require_writer(doc, "candidates.v1")
    updated = bump_revision(doc, {"operation_id": "synthetic-pressure-fixture", "kind": "task_update",
                                  "description": "300x5x3 synthetic pressure fixture; no model calls", "read_set": []})
    store.commit_change(base_revision=doc["revision_id"], document=updated, operation_id="synthetic-pressure-fixture")
    return project, store


def run():
    with tempfile.TemporaryDirectory(prefix="dm-b01-pressure-") as tmp:
        started = time.perf_counter()
        project, store = build(tmp)
        build_seconds = time.perf_counter() - started
        object_count = sum(1 for path in (Path(project) / ".deckmaster" / "objects").rglob("*") if path.is_file())

        cold = time.perf_counter()
        summary = workbench.workbench_summary(project)
        cold_ms = (time.perf_counter() - cold) * 1000.0

        # the projection must stay honest on the pressure graph itself
        pending_total = PAGES * (CANDIDATES_PER_PAGE - 1)
        assert summary["page_count"] == PAGES
        assert summary["candidates"] == {"status": "recorded", "count": PAGES * CANDIDATES_PER_PAGE,
                                         "pending_count": pending_total,
                                         "adopted_count": PAGES, "unreadable_count": 0}
        compare = [a for a in summary["next_actions"]["actions"] if a["kind"] == "compare_candidates"]
        assert len(compare) == 1 and len(compare[0]["page_ids"]) == PAGES
        assert len(compare[0]["source_refs"]) == pending_total * 2
        frozen = [page["prompt_summary"]["frozen"] for page in summary["pages"]]
        assert all(record["status"] == "recorded" and record["count"] == ATTEMPTS_PER_PAGE for record in frozen)
        prepared = [page["prompt_summary"]["prepared"] for page in summary["pages"]]
        assert all(record["status"] == "recorded" and record["count"] == 1 for record in prepared)
        assert "synthetic pressure prompt for p001" not in json.dumps(summary)

        timings = []
        for _ in range(WARM_RUNS):
            mark = time.perf_counter()
            workbench.workbench_summary(project)
            timings.append((time.perf_counter() - mark) * 1000.0)
        timings.sort()
        return {
            "probe": "b01_pressure",
            "synthetic": True,
            "real_host_calls": 0,
            "production_acceptance": False,
            "sample": {"pages": PAGES, "candidates_per_page": CANDIDATES_PER_PAGE,
                       "attempts_per_page": ATTEMPTS_PER_PAGE,
                       "candidate_total": PAGES * CANDIDATES_PER_PAGE,
                       "attempt_total": PAGES * ATTEMPTS_PER_PAGE,
                       "metadata_objects": object_count,
                       "build_seconds": round(build_seconds, 2)},
            "budget_ms": P95_BUDGET_MS,
            "cold_first_read_ms": round(cold_ms, 2),
            "warm_runs": WARM_RUNS,
            "warm_p50_ms": round(statistics.median(timings), 2),
            "warm_p95_ms": round(timings[int(0.95 * len(timings))], 2),
            "warm_max_ms": round(timings[-1], 2),
            "p95_within_budget": timings[int(0.95 * len(timings))] <= P95_BUDGET_MS,
            "temporary_project_cleaned": True,
        }


if __name__ == "__main__":
    value = run()
    Path(sys.argv[1]).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"warm_p95_ms": value["warm_p95_ms"], "p95_within_budget": value["p95_within_budget"],
                      "warm_runs": value["warm_runs"]}))
