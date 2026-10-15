"""Explicit synthetic RC3 test inputs; never a product gate bypass.

Historical fixtures initialize old data, public fixtures call current services.
No autouse monkeypatch and no implicit authorization is provided.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import uuid

from deck_master import collaboration, service
from deck_master.content import check_page
from deck_master.models import new_document, require_writer
from deck_master.store import Store


def _handle(project, response=None, *, scenario):
    store = Store(project)
    doc = store.load_document()
    return {"project": Path(project), "revision_id": doc["revision_id"],
            "request_id": ((doc.get("collaboration") or {}).get("request") or {}).get("request_id"),
            "refs": {"pages": [p["page"] for p in doc["pages"]], "plan": doc.get("content_plan")},
            "response": response, "scenario_manifest": {"scenario": scenario,
                "evidence_level": "L1_SYNTHETIC", "human_or_native_evidence": False}}


def historical_snapshot(tmp_path, *, scenario, pages=(), minimum_writer=None, task=None):
    project = Path(tmp_path) / ("historical-" + uuid.uuid4().hex[:8])
    store = Store(project)
    store.ensure_layout()
    doc = new_document(project_id=project.name, task=task or {"brief": scenario},
                       operation_id="historical-fixture")
    for page in pages:
        page = check_page(page)
        doc["pages"].append({"page_id": page["page_id"], "page": store.put_json_object(page),
                             "blueprint": None, "svg": None, "svg_preview": None, "ppt_preview": None})
    if minimum_writer is not None:
        require_writer(doc, minimum_writer)
    store.init_project(doc, operation_id="historical-fixture")
    return _handle(project, scenario=scenario)


def public_project(tmp_path, *, create_input, request_input=None, manuscript=None):
    project = Path(tmp_path) / ("rc3-" + uuid.uuid4().hex[:8])
    values = dict(create_input)
    if request_input is not None:
        values["request_input"] = request_input
    if manuscript is not None:
        values["draft"] = manuscript
    response = service.create(project, **values)
    return _handle(project, response, scenario="public current RC3 service")


def evidence_for(project, *, text, locator):
    store = Store(project)
    ref = store.put_blob(text.encode("utf-8"), ext="txt")
    return {"kind": "host_attested_instruction", "source_ref": ref,
            "source_locator": locator, "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def authorize_scope(project, *, actions, scope, max_external_calls,
                    max_candidate_count, adoption_policy, evidence):
    store = Store(project)
    return collaboration.grant(project, input={"mode": "execute", "actions": list(actions),
        "scope": scope, "max_external_calls": max_external_calls,
        "max_candidate_count": max_candidate_count, "adoption_policy": adoption_policy,
        "instruction_evidence": evidence}, base_revision=store.load_document()["revision_id"],
        operation_id=str(uuid.uuid4()))


def submit_host_fixture(project, *, task_id, result_payload, execution_ref, host_declaration):
    store = Store(project)
    task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                if store.read_object_json(ref)["task_id"] == task_id)
    service.task_start(project, task_id=task_id, execution_ref=execution_ref,
        supported_protocols=host_declaration["supported_protocols"],
        capabilities=host_declaration["capabilities"])
    return service.accept_result(project, task_id=task_id, operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload=result_payload)


def read_request_completion(project):
    from deck_master.content_production import completion_status
    store = Store(project)
    return completion_status(store, store.load_document())


def source_snapshot(root):
    root = Path(root)
    rows = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows[relative] = {"link": str(path.readlink())}
        elif path.is_file():
            rows[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def call_facts(project):
    store = Store(project)
    doc = store.load_document()
    return {"revision_id": doc["revision_id"], "tasks": [
        {"task_id": task["task_id"], "status": task["status"],
         "allowances": task.get("call_allowances", []),
         "attempts": task.get("generation_attempts", [])}
        for ref in doc["tasks"] for task in [store.read_object_json(ref)]]}


def claim_fixture_task(project, task, *, execution_ref="synthetic-l1-host"):
    """An explicit L1 Host claim using this actual public workorder contract."""
    service.task_start(project, task_id=task["task_id"], execution_ref=execution_ref,
        supported_protocols=[task["protocol_version"]] if task.get("protocol_version") else [],
        capabilities=task.get("required_capabilities", []))
    return task


def claimed_phase_task(store, document, **kwargs):
    from deck_master import content_production
    task = content_production.open_phase_task(store, document, **kwargs)
    return claim_fixture_task(store.project_root, task)
