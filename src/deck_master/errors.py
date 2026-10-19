"""Typed use-case failures carrying their CLI error code and exit code.

Spec v1.1 §9 fixes the code/exit pairs; every error also carries the
offending path (StoreError.path), the current state in its message, and the
caller-facing recovery in the CLI mapping.
"""

from __future__ import annotations

from .store import StoreError


class TypedServiceError(StoreError):
    """A use-case failure with a fixed error code and CLI exit code."""

    error_code = "invalid_input"
    exit_code = 2


class TaskFieldConflict(TypedServiceError):
    """Task facts conflict between CLI flags and --task-file (exit 2)."""

    error_code = "task_field_conflict"
    exit_code = 2


class SourceUnreadable(TypedServiceError):
    """An explicitly named material file cannot be read (exit 2)."""

    error_code = "source_unreadable"
    exit_code = 2


class SourceUnsupported(TypedServiceError):
    """An explicitly named material file has no declared reader (exit 2)."""

    error_code = "source_unsupported"
    exit_code = 2


class InputRevisionConflict(TypedServiceError):
    """Stale base revision, or a reused operation id with different content (exit 5)."""

    error_code = "input_revision_conflict"
    exit_code = 5

    http_status = 409

    def __init__(self, path, detail, *, cause='stale_base', operation_id=None):
        super().__init__(path, detail)
        self.cause, self.operation_id = cause, operation_id

    def payload(self):
        return {'error': {'code': self.error_code, 'message': self.detail, 'field': self.path,
                         'cause': self.cause, 'operation_id': self.operation_id,
                         'next_action': 'inspect the original operation; preserve its request and base'}}


class InputReconciliationPending(TypedServiceError):
    """Delivery/handoff refused while the deck awaits input reconciliation (exit 3)."""

    error_code = "input_reconciliation_pending"
    exit_code = 3


class MethodResourceMissing(TypedServiceError):
    """No readable method source exists for this installation (exit 4)."""

    error_code = "method_resource_missing"
    exit_code = 4


class HostSkillConflict(TypedServiceError):
    """The Codex skill path is occupied by something this installer does not own (exit 5)."""

    error_code = "host_skill_conflict"
    exit_code = 5


class InstallationTransactionError(TypedServiceError):
    """Installation control-plane failure, independent of project writers."""

    def __init__(self, code, message, *, transaction_id=None, state=None, details=None):
        super().__init__("installation", message)
        self.error_code = code
        self.exit_code = (130 if code == "installation_interrupted" else
                          2 if code == "invalid_transaction_id" else
                          4 if code in ("installation_recovery_unavailable", "installation_failed") else 5)
        self.transaction_id = transaction_id
        self.transaction_state = state
        self.details = details or {}

    def payload(self):
        return {"error": {"code": self.error_code, "message": str(self),
                          "transaction_id": self.transaction_id,
                          "transaction_state": self.transaction_state,
                          "next_action": "retry the original request with its transaction ID; preserve conflicting paths and backups for inspection",
                          **self.details}}


NEXT_ACTIONS_BY_CODE = {
    "narrative_disconnected": "connect relevant nodes with genuine support, explanation or qualification relations; move unrelated material out instead of adding meaningless edges",
    "basis_changed": "run continue to supersede the old execution contract and obtain a new Task with frozen methods and policy",
    "content_plan_invalid": "use the compose.v1 schema; preserve goal IDs and cite exact stored source versions/locators or record the missing basis",
    "legacy_run_format": "use the documented legacy import into a separate project; never initialize an old run in place",
    "needs_tool": "install or restore the named reader dependency in this CLI environment, then retry the same command",
    "task_field_conflict": "remove one of the conflicting task-fact sources and retry",
    "source_unreadable": "fix or replace the named file, or drop it from --source",
    "source_unsupported": "convert the file to a supported format or drop it from --source",
    "input_revision_conflict": "re-read inputs show, then retry with the current revision",
    "stale_input_context": "run continue for a fresh task; late results are refused",
    "input_reconciliation_pending": "run inputs update and the dispatched input_revision task first",
    "method_resource_missing": "reinstall the package; the method source is missing or unreadable",
    "host_skill_conflict": "remove or rename the occupant path, or choose another Codex skill root",
    "host_protocol_unsupported": "use a Host declaring the task's required protocol and capabilities; read the bundled Skill",
    "generation_request_required": "freeze the exact tool input, then begin with the returned request_id",
    "generation_attempt_required": "use the attempt_id returned by the same call begin",
    "generation_request_invalid": "read the task's generation_input and fix the named field",
    "generation_binding_conflict": "read the original request and attempt; do not reuse an allowance for different input",
    "generation_input_mismatch": "inspect the preserved actual input; create a new request for changed input",
    "generation_evidence_incomplete": "settle with a native event covering the required inputs and exact output; usage is retained",
    "generation_object_not_found": "read the task's request and attempt references in the selected revision",
    "tool_observation_unavailable": "check the native event identities and local runtime output; do not invent a receipt",
    "operation_payload_conflict": "replay the original payload or use a new operation ID for a different request",
}


class SourceNeedsTool(TypedServiceError):
    """A selected source cannot be read until its dependency is restored."""

    error_code = "needs_tool"
    exit_code = 3


class ImportRequiresPhasedPath(TypedServiceError):
    """A draft import on a collaboration.v1 project has no legal legacy task (exit 4).

    The legacy import envelope writes Pages, ordering and a Plan in one step
    with no work request, no collaboration binding and no phased write scope.
    On a collaboration.v1 project that would be an unbound production task, so
    the import is refused with the concrete recovery path instead.
    """

    error_code = "import_requires_phased_path"
    exit_code = 4
