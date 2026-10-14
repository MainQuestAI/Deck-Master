"""CLI/HTTP transport for the existing collaboration service; no second state."""

from __future__ import annotations
from urllib.parse import unquote, urlparse

from . import capabilities, collaboration, collaboration_migration, content_production, eligibility
from .local_state import project_path
from .models import ModelError
from .snapshots import load_snapshot
from .store import Store, StoreError, ConflictError
from .operations import OperationError

READ_ROUTES = {"/api/collaboration": "show", "/api/collaboration/migration": "migration.describe", "/api/capabilities": "capabilities"}
WRITE_ROUTES = {
    "/api/collaboration/requests": "request.start",
    "/api/collaboration/decisions": "decision",
    "/api/collaboration/authorizations": "grant",
    "/api/collaboration/proposal-adoptions": "adopt-proposal",
    "/api/collaboration/request/pause": "pause",
    "/api/collaboration/request/resume": "resume",
    "/api/collaboration/migration": "migration.apply",
    "/api/eligibility": "eligibility",
    "/api/reviews/evaluate": "review.evaluate",
    "/api/reviews/import": "review.import",
}
WRITE_ACTIONS = {
    "request.start": "request.start",
    "decision": "decision.record",
    "grant": "authorization.grant",
    "adopt-proposal": "proposal.adopt",
    "pause": "request.pause",
    "resume": "request.resume",
    "revoke": "authorization.revoke",
    "migration.apply": "migration.apply",
    "review.import": "review.record",
}


def route(path, document=None, *, method):
    path = urlparse(path).path
    parts = path.split("/")
    if len(parts) >= 5 and parts[:3] == ["", "api", "projects"]:
        if document is not None and unquote(parts[3]) != document["project_id"]:
            raise ModelError("project_id", "route belongs to another project")
        path = "/api/" + "/".join(parts[4:])
    routes = READ_ROUTES if method == "GET" else WRITE_ROUTES
    if path in routes:
        return routes[path], {}
    parts = path.split("/")
    if method == "POST" and len(parts) == 6 and parts[1:4] == ["api", "collaboration", "authorizations"] and parts[5] == "revoke":
        return "revoke", {"authorization_id": unquote(parts[4])}
    return None


def _result(document, control, status, *, result=None, error=None, operation_id=None):
    return {
        "schema_version": "collaboration_response.v1",
        "status": status,
        "project_id": control.get("project_id") if control else None,
        "artifact_revision_id": document.get("revision_id") if document else None,
        "control_revision_id": control.get("revision_id") if control else None,
        "operation_id": operation_id,
        "result": result,
        "error": error,
        "next_action": (result or {}).get("next_action") or ("resolve_the_named_gap" if error else "inspect_current_state"),
    }


def invoke(project, action, payload=None, *, adapter_context=None):
    """Return (body, HTTP status, CLI exit); context comes only from transport."""
    data = {}
    document = control = None
    try:
        if payload is not None and not isinstance(payload, dict):
            raise ModelError("request", "request body must be an object")
        data = dict(payload or {})
        if any(k in data for k in ("adapter_context", "verified_user_events", "independent_review_receipts", "human_review_receipts")):
            raise OperationError(
                "untrusted_adapter_context", "body", "transport evidence cannot be supplied by JSON", exit_code=4, http_status=403
            )
        if action == "review.evaluate":
            from .external_review import evaluate

            result = evaluate(
                data["source"], **{k: data[k] for k in ("persistence", "report_output", "source_sha256", "scope") if k in data}
            )
            return _result(None, None, result["status"], result=result), 200, 0
        store = Store(project_path(project))
        control = store.load_document()
        if data.get("project_id") not in (None, control["project_id"]):
            raise ModelError("project_id", "request belongs to another project")
        document = load_snapshot(store, data.get("artifact_revision")) if data.get("artifact_revision") else control
        if action == "capabilities":
            result = capabilities.describe(adapter_context)
        elif action == "show":
            result = {**collaboration.describe(store.project_root), "capabilities": capabilities.describe(adapter_context)}
        elif action == "migration.describe":
            result = collaboration_migration.describe(store.project_root)
        elif action == "eligibility":
            if "context" in data:
                raise ModelError("context", "query only declared targets; transport context is not JSON input")
            result = eligibility.evaluate(store, document, control, data["action"], context={"targets": data.get("targets") or {}})
        else:
            common = {key: data[key] for key in ("base_revision", "operation_id")}
            body = {
                key: value for key, value in data.items() if key not in ("base_revision", "operation_id", "project_id", "artifact_revision")
            }
            if action in ("request.start", "request.replace"):
                value = body.get("request", body)
                if "request" in body:
                    value = {**value, **{k: v for k, v in body.items() if k != "request"}}
                if action == "request.replace" and not value.get("replace_request_id"):
                    raise ModelError("replace_request_id", "replace names the current request explicitly")
                result = collaboration.start_request(store.project_root, input=value, adapter_context=adapter_context, **common)
            elif action == "decision":
                result = collaboration.record_decision(
                    store.project_root, input=body.get("decision", body), adapter_context=adapter_context, **common
                )
            elif action == "grant":
                result = collaboration.grant(
                    store.project_root, input=body.get("authorization", body), adapter_context=adapter_context, **common
                )
            elif action == "adopt-proposal":
                result = content_production.adopt_proposal(store.project_root, input=body, adapter_context=adapter_context, **common)
            elif action in ("pause", "resume"):
                current = (control.get("collaboration") or {}).get("request") or {}
                if body.get("request_id") not in (None, current.get("request_id")):
                    raise ConflictError("request_id", "current request changed")
                if action == "pause":
                    result = collaboration.pause_request(
                        store.project_root,
                        reason=body.get("reason", ""),
                        instruction_evidence=body.get("evidence", body.get("instruction_evidence")),
                        adapter_context=adapter_context,
                        **common,
                    )
                else:
                    result = collaboration.resume_request(
                        store.project_root,
                        instruction_evidence=body.get("evidence", body.get("instruction_evidence")),
                        adapter_context=adapter_context,
                        **common,
                    )
            elif action == "revoke":
                result = collaboration.revoke_authorization(
                    store.project_root,
                    authorization_id=body["authorization_id"],
                    reason=body.get("reason", ""),
                    instruction_evidence=body.get("evidence", body.get("instruction_evidence")),
                    adapter_context=adapter_context,
                    **common,
                )
            elif action == "migration.apply":
                result = collaboration_migration.apply(store.project_root, plan_digest=body["plan_digest"], **common)
            elif action == "review.import":
                from .external_review import import_report

                result = import_report(store.project_root, input=body, **common)
            else:
                raise ModelError("action", "unknown collaboration action")
            control = store.load_document()
            document = control
        return _result(document, control, result.get("status", "ok"), result=result, operation_id=data.get("operation_id")), 200, 0
    except Exception as exc:
        if isinstance(exc, OperationError):
            error = exc.payload()["error"]
            http = exc.http_status
            code = exc.exit_code
            if http == 422 and code == 2:
                http = 400
        elif isinstance(exc, ConflictError) or getattr(exc, "error_code", None) == "conflict":
            error = {"code": "conflict", "path": getattr(exc, "path", None), "message": str(exc)}
            http, code = 409, 5
        elif isinstance(exc, eligibility.EligibilityBlocked):
            error = {"code": exc.decision["reason_codes"][0], "path": "eligibility", "message": str(exc), "details": exc.decision}
            http, code = 409, 4
        elif isinstance(exc, StoreError):
            path = getattr(exc, "path", getattr(exc, "field", "project"))
            stale = str(path) == "base_revision"
            error = {"code": "conflict" if stale else "object_not_found", "path": path, "message": str(exc)}
            http, code = (409, 5) if stale else (404, 2)
        elif isinstance(exc, ModelError) and getattr(exc, "path", "").split("/")[0] == "migration_required":
            error = {"code": "migration_required", "path": exc.path, "message": str(exc)}
            http, code = 409, 4
        elif isinstance(exc, (KeyError, TypeError, ValueError, ModelError)):
            error = {"code": "invalid_input", "path": getattr(exc, "path", getattr(exc, "field", "request")), "message": str(exc)}
            http, code = 400, 2
        else:
            raise
        error.setdefault("recoverable", http != 403)
        error.setdefault("details", {})
        return (
            _result(document, control, "blocked" if http == 409 else "error", error=error, operation_id=data.get("operation_id")),
            http,
            code,
        )
