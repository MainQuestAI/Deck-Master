"""Normal installed native review: execute, observe, bind, and accept once.

No persistent issuer permission is installed. The private provider lives only
inside this owned execution; CLI/HTTP callers cannot submit receipt claims.
Committed standard Review/Task/receipt facts remain usable after it exits.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
from jsonschema import Draft202012Validator, ValidationError

from . import content_review, method_resources, models, review_evidence, service, tasks
from .native_review_transport import CodexReviewSession
from .store import Store, StoreError

PROVIDER_ID = "codex-native-review"


class _ObservedProvider:
    provider_id = PROVIDER_ID
    adapter_version = "codex-native-review.v1"
    authentication = "protected_transport"
    channels = ("independent_review_receipts",)

    def __init__(self, session):
        self.session = session
        self.raw = None
        self.claims = None

    def health(self):
        return self.session.ready

    def fetch(self, event_id):
        if not self.claims or event_id != self.claims["event_id"]:
            raise ValueError("no observed completion")
        return self.raw

    def verify(self, raw):
        if self.raw is None or raw != self.raw or not self.claims:
            raise ValueError("not this native completion")
        return deepcopy(self.claims)


def _judgment_schema(units):
    review = models.load_schema("review_v2")
    finding = deepcopy(review["properties"]["findings"]["items"])
    finding["required"] = list(finding["properties"])
    row = {"type": "object", "additionalProperties": False,
           "required": ["kind", "status", "observations", "findings", "replaces"],
           "properties": {"kind": {"enum": list(units)},
               **{key: deepcopy(review["properties"][key]) for key in
                  ("status", "observations", "replaces")},
               "findings": {"type": "array", "items": finding}}}
    result = {"type": "object", "additionalProperties": False, "required": ["reviews"],
              "properties": {"reviews": {"type": "array", "items": row}}}
    def explicit_types(value):
        if isinstance(value, dict):
            if "enum" in value and all(isinstance(item, str) for item in value["enum"]):
                value.setdefault("type", "string")
            for child in value.values():
                explicit_types(child)
        elif isinstance(value, list):
            for child in value:
                explicit_types(child)
    explicit_types(result)
    return result


def _packet(store, task):
    packets = []
    for ref in task["inputs"]:
        try:
            value = store.read_object_json(ref)
        except (ValueError, UnicodeError, StoreError):
            continue  # Other Task inputs may be original binary/text material.
        if isinstance(value, dict) and value.get("schema_version") == "content_review_packet.v1":
            packets.append(value)
    if len(packets) != 1:
        raise review_evidence.EvidenceRejected("native_review/packet", "one fixed complete review packet is required")
    return packets[0]


def _envelope(store, document, task, session, observation, units):
    try:
        judgments = json.loads(observation["raw_final_message"])
        Draft202012Validator(_judgment_schema(units)).validate(judgments)
    except (ValueError, ValidationError) as exc:
        raise review_evidence.EvidenceRejected("native_review/output", "native final output is not a valid complete review judgment") from exc
    rows = judgments["reviews"]
    if len(rows) != len(units) or {row["kind"] for row in rows} != set(units):
        raise review_evidence.EvidenceRejected("native_review/units", "native output must cover every required unit exactly once")
    subjects = [document[key] for key in ("narrative", "content_plan") if document.get(key)]
    pages = [entry for entry in document["pages"] if entry["page_id"] in task["scope_pages"]]
    subjects += [entry["page"] for entry in pages]
    deps = [{"kind": "content", "identity": key, "sha256": document[key]["sha256"]}
            for key in ("narrative", "content_plan") if document.get(key)]
    deps += [{"kind": "content", "identity": "page:" + entry["page_id"], "sha256": entry["page"]["sha256"]} for entry in pages]
    deps += [{"kind": "source", "identity": source["source_id"], "sha256": source["extract"]["sha256"]}
             for source in document.get("sources") or [] if source.get("extract")]
    previous = {(ref["path"], ref["sha256"]): store.read_object_json(ref)
                for ref in document.get("reviews") or []}
    evidence_ref = store.put_json_object(observation)
    reviews = []
    for row in rows:
        review_id = task["task_id"] + "-" + row["kind"]
        if row["replaces"]:
            ref = row["replaces"]
            prior = previous.get((ref["path"], ref["sha256"]))
            if not prior or prior.get("kind") != row["kind"] or prior.get("review_stage") != "preproduction":
                raise review_evidence.EvidenceRejected("native_review/replaces", "replacement must name an actual prior review of the same unit")
            review_id = prior["review_id"]
        reviews.append({**row, "schema_version": "deck_review.v2", "review_stage": "preproduction",
                "review_id": review_id,
                "subjects": subjects, "dependencies": deps,
                "reviewer": {"type": "independent_host", "id": session.execution_ref,
                             "execution_ref": session.execution_ref, "independence_confirmed": True,
                             "identity_receipt": None, "assurance": "host_attested", "evidence_ref": evidence_ref},
                "created_at": datetime.now(timezone.utc).isoformat()})
    return {"kind": "review", "pages": [], "page_order": [], "artifact_specs": [],
            "reviews": reviews, "usage_events": [], "notes": "Actual native independent preproduction review"}


def _failure(store, task, executor, exc):
    """A failed execution is terminal; retry is a new explicit native run."""
    document = store.load_document()
    current = tasks._lookup_task(document, task["task_id"], store)
    if current["status"] == "running" and current.get("execution_ref") == executor:
        updated = {**current, "status": "failed", "updated_at": service._utc_now_iso(),
                   "error": {"code": "native_review_failed", "message": str(getattr(exc, "detail", type(exc).__name__))[:500],
                             "next_action": "inspect the failure; explicitly run native review again"}}
        service._commit_task_update(store, document, current, updated, "native independent review failed")


def run(project, *, task_id=None):
    """Run actual native review; project and an optional Task ID are the only inputs."""
    store = Store(Path(project).expanduser())
    # A derived operation lock prevents double-clicks/reconnects from issuing a
    # second native call. It grants no policy or receipt authority.
    handle = os.open(store.deck_root / "native-review.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise review_evidence.EvidenceRejected("native_review/lock", "operation lock must be a regular file")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "running", "next_action": "read current task status; do not launch another native review"}
        return _run(store, task_id=task_id)
    finally:
        os.close(handle)


def _run(store, *, task_id):
    document = store.load_document()
    gate = content_review.preproduction_status(store, document)
    if gate["status"] == "pass":
        return {"status": "already_reviewed", "preproduction": gate}
    candidates = [task for ref in document["tasks"] if
                  (task := store.read_object_json(ref)).get("kind") == "review"
                  and task.get("review_stage") == "preproduction"
                  and task["status"] in ("awaiting_host", "running", "queued")]
    if task_id:
        task = tasks._lookup_task(document, task_id, store)
        if task not in candidates:
            raise review_evidence.EvidenceRejected("native_review/task_id", "select a live preproduction review task")
    elif len(candidates) > 1:
        raise review_evidence.EvidenceRejected("native_review/task_id", "select one of the existing preproduction review tasks")
    else:
        task = candidates[0] if candidates else None
    if task and task["status"] == "running":
        return {"status": "running", "task_id": task["task_id"],
                "next_action": "inspect the existing execution; cancel it explicitly if interrupted before retrying"}
    with CodexReviewSession() as session:
        provider = _ObservedProvider(session)
        registry = review_evidence.ProviderRegistry()
        registry.register(provider)
        with review_evidence.ProviderRuntime(registry).bound():
            if task is None:
                dispatched = content_review.dispatch_preproduction_review(store.project_root,
                    adapter_context=registry.channel_context())
                task = dispatched["task"]
            document = store.load_document()
            if not tasks.task_inputs_current(store, document, task):
                raise tasks.StaleInputContext("native_review/task", "review inputs changed; run continue to retire and reissue the task")
            methods = method_resources.read_task_methods(store.project_root, task["task_id"])
            if methods["status"] != "current":
                raise tasks.StaleInputContext("native_review/methods", "frozen methods changed; run continue to retire and reissue the task")
            packet = _packet(store, task)
            units = packet["required_units"]
            subjects = [document[key] for key in ("narrative", "content_plan") if document.get(key)]
            subjects += [entry["page"] for entry in document["pages"] if entry["page_id"] in task["scope_pages"]]
            authors = content_review.author_execution_refs(store, document, subjects)
            if session.execution_ref in authors:
                raise review_evidence.EvidenceRejected("native_review/executor", "reviewer is an author of this manuscript")
            service.task_start(store.project_root, task_id=task["task_id"], execution_ref=session.execution_ref,
                supported_protocols=[task["protocol_version"]] if task.get("protocol_version") else [],
                capabilities=task.get("required_capabilities") or [])
            try:
                prior = [{"ref": ref, "review": value} for ref in document.get("reviews") or []
                         if (value := store.read_object_json(ref)).get("review_stage") == "preproduction"]
                prompt = ("Independently review the complete manuscript against the task, materials, and frozen methods below. "
                          "Return exactly one judgment for each required unit. Do not edit the draft. Cite concrete pages/atoms "
                          "and evidence for findings. Re-check prior findings against the current manuscript; preserve finding IDs "
                          "and use replaces only when actually verifying the corresponding previous review. Never fabricate "
                          "human/professional approval or claim unobserved evidence. JSON input follows:\n" +
                          json.dumps({"packet": packet, "methods": methods["methods"], "prior_reviews": prior}, ensure_ascii=False))
                observation = session.review(prompt, _judgment_schema(units))
                if (observation.get("thread_id") != session.thread_id or observation.get("turn_id") != session.turn_id
                        or observation.get("status") != "completed"):
                    raise review_evidence.EvidenceRejected("native_review/completion", "completion does not match the owned native execution")
                # Bind to the dispatched manuscript, never silently rebase a
                # judgment onto content changed during the native call.
                envelope = _envelope(store, document, task, session, observation, units)
                binding = review_evidence.review_binding(store, document, task, envelope)
                issued = datetime.now(timezone.utc)
                provider.raw = models.canonical_json_bytes(observation)
                provider.claims = {**binding, "provider_id": PROVIDER_ID,
                    "event_id": "native-" + models.sha256_bytes(provider.raw)[:40],
                    "channel": "independent_review_receipts", "issued_at": issued.isoformat(),
                    "expires_at": (issued + timedelta(minutes=30)).isoformat(),
                    "executor_ref": session.execution_ref, "reviewer_id": session.execution_ref,
                    "assurance": "host_attested", "observation_kind": "owned_native_process_completion",
                    "model_output_bytes_sha256": models.sha256_bytes(observation["raw_final_message"].encode()),
                    "method_release": task.get("method_release"),
                    "evidence_scope": "native independent content review; not human or professional approval"}
                current = store.load_document()
                claimed = tasks._lookup_task(current, task["task_id"], store)
                context = registry.review_context(store, current, claimed, envelope,
                    {"provider_id": PROVIDER_ID, "event_id": provider.claims["event_id"]})
                accepted = service.accept_result(store.project_root, task_id=task["task_id"],
                    operation_id=task["operation_id"], produced_against=task["produced_against"],
                    result_payload=envelope, adapter_context=context)
                return {"status": "reviewed", "task_id": task["task_id"], "execution_ref": session.execution_ref,
                        "acceptance": accepted, "preproduction": content_review.preproduction_status(store, store.load_document())}
            except Exception as exc:
                try:
                    _failure(store, task, session.execution_ref, exc)
                except Exception:
                    pass  # Never mask cancellation/CAS/failure evidence with a second error.
                raise
