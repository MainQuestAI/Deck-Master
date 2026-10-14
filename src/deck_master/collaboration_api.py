"""Minimum Host CLI adapter onto the existing collaboration Runtime.

No HTTP/UI, external-report or writer-default changes in RC3-04/early.
The shared response is retained for the complete slice's HTTP adapter.
"""
from __future__ import annotations

from . import collaboration, collaboration_migration, content_production, eligibility
from .capabilities import describe as capabilities
from .models import ModelError
from .store import Store, StoreError, ConflictError
from .operations import OperationError

WRITE_ACTIONS = {"request.start": "request.start", "request.replace": "request.start",
                 "decision": "decision.record", "adopt-proposal": "proposal.adopt", "migration.apply": "migration.apply"}
READ_ACTIONS = ("show", "migration.describe")
_FORBIDDEN = {"adapter_context", "verified_user_events", "independent_review_receipts", "human_review_receipts"}


def _reject_context(data):
    if isinstance(data, dict):
        if set(data) & _FORBIDDEN:
            raise OperationError("untrusted_adapter_context", "request", "transport evidence cannot be supplied by JSON",
                                 exit_code=4, http_status=403)
        for value in data.values():
            _reject_context(value)
    elif isinstance(data, list):
        for value in data:
            _reject_context(value)


def _response(document, *, status, result=None, error=None, operation_id=None):
    return {"schema_version": "collaboration_response.v1", "status": status,
            "project_id": document.get("project_id") if document else None,
            "artifact_revision_id": document.get("revision_id") if document else None,
            "control_revision_id": document.get("revision_id") if document else None,
            "operation_id": operation_id, "result": result, "error": error,
            "next_action": (result or {}).get("next_action") or ("resolve_the_named_gap" if error else "inspect_current_state")}


def invoke(project, action, payload=None, *, adapter_context=None):
    """Return shared response/HTTP status/CLI exit. Context is SDK-only opaque."""
    document, data = None, {}
    try:
        if payload is not None and not isinstance(payload, dict):
            raise ModelError("request", "body must be an object")
        data = dict(payload or {})
        _reject_context(data)
        if action not in READ_ACTIONS and action not in WRITE_ACTIONS:
            raise ModelError("action", "unsupported early collaboration action")
        store = Store(project)
        document = store.load_document()
        if data.get("project_id") not in (None, document["project_id"]):
            raise ModelError("project_id", "request belongs to another project")
        if action == "show":
            result = {**collaboration.describe(project), "capabilities": capabilities(adapter_context)}
        elif action == "migration.describe":
            result = collaboration_migration.describe(project)
        else:
            common = {key: data[key] for key in ("base_revision", "operation_id")}
            body = {key: value for key, value in data.items() if key not in (*common, "project_id")}
            if action.startswith("request."):
                value = body.get("request", body)
                if "request" in body:
                    value = {**value, **{key: v for key, v in body.items() if key != "request"}}
                if action == "request.replace" and not value.get("replace_request_id"):
                    raise ModelError("replace_request_id", "replace names the current request")
                result = collaboration.start_request(project, input=value, adapter_context=adapter_context, **common)
            elif action == "decision":
                result = collaboration.record_decision(project, input=body.get("decision", body), adapter_context=adapter_context, **common)
            elif action == "adopt-proposal":
                result = content_production.adopt_proposal(project, input=body, adapter_context=adapter_context, **common)
            else:
                result = collaboration_migration.apply(project, plan_digest=body["plan_digest"], **common)
            document = store.load_document()
        return _response(document, status=result.get("status", "ok"), result=result, operation_id=data.get("operation_id")), 200, 0
    except Exception as exc:
        field = getattr(exc, "path", "request")
        details = {}
        if isinstance(exc, eligibility.EligibilityBlocked):
            code, http, exit_code = exc.decision["reason_codes"][0], 409, 4
            details = exc.decision
        elif isinstance(exc, OperationError):
            code, http, exit_code = exc.error_code, exc.http_status, exc.exit_code
        elif isinstance(exc, ConflictError) or field == "base_revision":
            code, http, exit_code = "conflict", 409, 5
        elif getattr(exc, "error_code", None):
            code, http, exit_code = exc.error_code, 403, getattr(exc, "exit_code", 4)
        elif isinstance(exc, ModelError):
            migration = "migration_required" in str(exc)
            code, http, exit_code = ("migration_required", 409, 4) if migration else ("invalid_input", 400, 2)
        elif isinstance(exc, StoreError):
            code, http, exit_code = "object_not_found", 404, 2
        elif isinstance(exc, (KeyError, TypeError, ValueError)):
            code, http, exit_code = "invalid_input", 400, 2
        else:
            raise
        error = {"code": code, "path": field, "message": str(exc), "recoverable": http != 403, "details": details}
        return _response(document, status="blocked" if http == 409 else "error", error=error,
                         operation_id=data.get("operation_id")), http, exit_code
