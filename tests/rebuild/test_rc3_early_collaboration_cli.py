"""Real CLI migration/request/decision/adoption bridge, never Store bootstrap."""
import hashlib
import json

import pytest

from deck_master import cli, collaboration_api, content_production, service
from deck_master.store import Store
from test_compose_v2_phases import _argument_narrative


def _command(capsys, project, *args, data=None, path=None, code=0):
    argv = ["collaboration", *args, str(project)]
    if data is not None:
        path.write_text(json.dumps(data))
        argv += ["--input", str(path)]
    assert cli.main(argv) == code
    captured = capsys.readouterr()
    return json.loads(captured.out if code == 0 else captured.err)


def test_cli_migrates_starts_request_consumes_work_order_and_adopts_argument(tmp_path, capsys):
    project = tmp_path / "real-cli"
    source = tmp_path / "material.txt"
    source.write_text("紧急程度和版本是否可得是独立维度；未知需要记录。")
    service.create(project, brief="支持培训", sources=[source], project_format="workbench.v3")
    store = Store(project)
    input_path = tmp_path / "payload.json"
    before = hashlib.sha256((store.deck_root / "current.json").read_bytes()).hexdigest()
    migration = _command(capsys, project, "migration", "describe")["result"]
    assert hashlib.sha256((store.deck_root / "current.json").read_bytes()).hexdigest() == before
    _command(capsys, project, "migration", "apply", data={"plan_digest": migration["plan_digest"],
             "base_revision": migration["revision_id"], "operation_id": "cli-migrate"}, path=input_path)
    doc = store.load_document()
    evidence = {"kind": "host_attested_instruction", "source_ref": doc["sources"][0]["extract"],
                "source_locator": "synthetic:actual-cli", "actor_id": None,
                "transport_receipt_ref": None, "presentation_ref": None}
    scope = {"subject":"deck","page_ids":[],"page_manifest_ref":None,"external_artifact_ref":None,
             "layers":["narrative","plan","page_copy","speech","review"],
             "allow_page_membership_change":True,"allow_page_order_change":False,"purpose":"working"}
    payload = {"base_revision":doc["revision_id"],"operation_id":"cli-start","request":{
               "intent":"content_only","content_intent":"write_only","instruction_evidence":evidence,
               "scope":scope,"replace_request_id":None}}
    result = _command(capsys, project, "request", "start", data=payload,path=input_path)
    assert result["result"]["assurance"] == "host_attested"
    replay = _command(capsys, project, "request", "start", data=payload,path=input_path)
    assert replay["status"] == "already_applied"
    # Existing formal SDK dispatch and task acceptance, with zero fixture bootstrap.
    doc = store.load_document()
    task = content_production.open_phase_task(store,doc,operation_id="cli-argument",phase="argument")
    order = service.task_summary(store,store.load_document(),task)
    assert order["protocol_version"] == "compose.v2" and order["method_basis_status"] == "current"
    service.accept_result(project,task_id=task["task_id"],operation_id=task["operation_id"],produced_against=task["produced_against"],
           result_payload={"schema_version":"compose_result.v2","kind":"compose","variant":"narrative",
            "task_id":task["task_id"],"operation_id":task["operation_id"],"produced_against":task["produced_against"],
            "eligibility_digest":task["collaboration_binding"]["eligibility_digest"],
            "payload":{"narrative":_argument_narrative(doc["project_id"])},"usage_events":[]})
    doc=store.load_document(); recorded=next(store.read_object_json(ref) for ref in doc["tasks"]
                                           if store.read_object_json(ref)["task_id"]==task["task_id"])
    proposal=recorded["result_refs"][0]
    decision = _command(capsys, project,"decision",data={"base_revision":doc["revision_id"],"operation_id":"cli-decision",
                "decision":{"topic":"direction","disposition":"accepted","authority_mode":"direct_user",
                "value":{"selected":"两维度记录"},"scope":scope,"instruction_evidence":evidence,
                "subject_refs":[{"artifact_kind":"narrative","artifact_ref":proposal,"projection":"direction"}]}},path=input_path)
    adopted = _command(capsys,project,"adopt-proposal",data={"base_revision":store.current_revision_id(),
              "operation_id":"cli-adopt","proposal_ref":proposal,"decision_ref":decision["result"]["decision_ref"],
              "write_scope":{**scope,"layers":["narrative"]}},path=input_path)
    assert adopted["status"] == "accepted" and store.load_document()["narrative"] == proposal
    assert not store.load_document()["collaboration"]["authorizations"]


@pytest.mark.parametrize("nested",[False,True])
def test_json_cannot_forge_adapter_context(tmp_path,nested):
    project=tmp_path/'project';service.create(project,brief='x',sources=[])
    data={"independent_review_receipts":[{"verified":True}]}
    if nested:data={"request":data}
    result,http,code=collaboration_api.invoke(project,'request.start',data)
    assert (http,code)==(403,4) and result['error']['code']=='untrusted_adapter_context'


def test_cli_error_classification_is_shared_and_recoverable(tmp_path):
    project=tmp_path/'project';service.create(project,brief='x',sources=[])
    result,http,code=collaboration_api.invoke(project,'request.start',{'base_revision':'stale','operation_id':'bad'})
    assert (http,code)==(409,5) and result['error']['recoverable']
    result,http,code=collaboration_api.invoke(project,'request.start',{'base_revision':Store(project).current_revision_id(),'operation_id':'not-migrated'})
    assert (http,code)==(409,4) and result['error']['code']=='migration_required'
