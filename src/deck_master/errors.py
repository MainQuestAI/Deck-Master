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


class StaleInputContext(TypedServiceError):
    """A result arrived after the task inputs moved on (exit 5)."""

    error_code = "stale_input_context"
    exit_code = 5


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
