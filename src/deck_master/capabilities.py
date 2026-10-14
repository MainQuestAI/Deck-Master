"""Read actual installed methods and transport capabilities without writing state.

An untrusted CLI/HTTP payload cannot advertise an identity or review channel.
The default transport has only Host-attested instructions. Trusted adapters may
provide their context to the Python boundary; no adapter is invented here.
"""

from __future__ import annotations

from . import __version__
from .content_review import reviewer_capabilities
from .method_resources import RELATIVE_PATHS, resolve_root, method_release
from .models import sha256_bytes


def describe(adapter_context=None):
    root = resolve_root()
    resources = []
    for identity, relative in RELATIVE_PATHS.items():
        path = root / relative
        resources.append(
            {
                "id": identity,
                "relative_path": relative,
                "sha256": sha256_bytes(path.read_bytes()) if path.is_file() else None,
                "available": path.is_file(),
            }
        )
    available = reviewer_capabilities(adapter_context)
    kinds = ["host_attested_instruction"]
    if available["verified_user_events"]:
        kinds.append("user_event")
    if available["independent_review_receipts"]:
        kinds.append("independent_execution_receipt")
    if available["human_review_receipts"]:
        kinds.append("human_identity_receipt")
    context = adapter_context or {}
    return {
        "schema_version": "host_capabilities.v1",
        "package_version": __version__,
        "status": "ready" if all(r["available"] for r in resources) else "needs_tool",
        **available,
        "adapter_version": context.get("adapter_version"),
        "evidence_kinds": kinds,
        "assurance": "host_attested",
        "methods": resources,
        "method_release": method_release(resources),
        "review_channel_status": "available"
        if any(available[k] for k in ("independent_review_receipts", "human_review_receipts"))
        else "needs_reviewer",
        "limitations": [
            "Host-attested instructions do not verify human identity",
            "Method availability does not prove a Host read or applied the method",
            "No strict identity/review channel is implied by a CLI call",
        ],
    }
