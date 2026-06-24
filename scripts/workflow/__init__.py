"""Skill OS Workflow runtime.

Stage-contract-aware workflow state, entry/exit validation, and artifact
fingerprinting. Built on top of the canonical Skill Manifest & Stage Contract
registry (``scripts/skills/manifest.py``). The fine-grained *runtime* stage
produced by ``scripts/runtime/run_state_resolver.py`` is consumed unchanged as
``runtime_stage``; this module adds the 9-stage contract view on top.
"""
from __future__ import annotations

from .state import WorkflowStateResolver, resolve_workflow_state  # noqa: F401

__all__ = ["WorkflowStateResolver", "resolve_workflow_state"]
