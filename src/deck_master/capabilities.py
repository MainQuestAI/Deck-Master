"""Read actual installed methods and transport capabilities without writing state.

An untrusted CLI/HTTP payload cannot advertise an identity or review channel.
The default transport has only Host-attested instructions. Trusted adapters may
provide their context to the Python boundary; no adapter is invented here.
"""

from __future__ import annotations
import json
import re
from importlib import metadata
from pathlib import Path
import subprocess
import sys

from . import __version__
from .content_review import reviewer_capabilities
from .method_resources import RELATIVE_PATHS, resolve_root, method_release
from .models import sha256_bytes
from .review_evidence import context_payload, current_registry

RUNTIME_PROTOCOL_CAPABILITIES = ('collaboration.v1', 'rc3-entry.v1', 'business-framing.v1', 'business-review.v1')


def installation_identity():
    """Observed source/package/install identity; no cwd or other release lookup."""
    import deck_master
    module = Path(deck_master.__file__).resolve()
    root = resolve_root()
    info = {"module_path": str(module), "module_sha256": sha256_bytes(module.read_bytes()),
            "python_executable": sys.executable, "python_prefix": sys.prefix,
            "method_root": str(root), "method_source": "packaged", "source": None, "install": None}
    try:
        info["metadata_version"] = metadata.version("deck-master")
    except metadata.PackageNotFoundError:
        info["metadata_version"] = None
    if module.parent.name == "deck_master" and module.parents[1].name == "src":
        repo = module.parents[2]
        info["method_source"] = "canonical_checkout"
        try:
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                                      text=True, timeout=3).stdout.strip()
            # One fresh observation for both immutable identities; status is
            # still queried afresh, never inferred from cached source metadata.
            sha, tree = git("rev-parse", "HEAD", "HEAD^{tree}").splitlines()
            if not all(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) for value in (sha, tree)):
                raise ValueError("invalid Git object identity")
            info["source"] = {"sha": sha, "tree": tree, "dirty": bool(git("status", "--porcelain"))}
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    prefix = Path(sys.prefix).resolve()
    manifest = prefix.parent / "release.json"
    if module.is_relative_to(prefix) and manifest.is_file():
        record = json.loads(manifest.read_text("utf-8"))
        info["install"] = {key: record.get(key) for key in
                           ("release_id", "source_sha", "source_tree", "source_dirty", "package_version", "wheel_sha256", "status")}
    return info


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
    from .review_channels import describe as review_channels
    registry = current_registry()
    context = context_payload(registry.channel_context() if adapter_context is None else adapter_context)
    return {
        "schema_version": "host_capabilities.v1",
        "package_version": __version__,
        "protocol_capabilities": list(RUNTIME_PROTOCOL_CAPABILITIES),
        "review_subjects": {"outline": {"capability": "outline_review.v1", "units": ["argument", "progression"]}},
        "summary_protocols": ["workbench_summary.v1", "workbench_summary.v2"],
        "read_protocols": [{"protocol": "work_context.v2", "body_modes": ["full", "delta", "manifest"],
                            "default_body_mode": "full", "cache_offer_requires_observed_context": True}],
        "task_response_protocols": [{"protocol": "task_receipt.v1",
                                     "operations": ["task start", "task accept", "task cancel"],
                                     "opt_in": True, "context_ready": False,
                                     "full_context_protocol": "work_context.v2"}],
        "installation_identity": installation_identity(),
        "status": "ready" if all(r["available"] for r in resources) else "needs_tool",
        **available,
        "adapter_version": context.get("adapter_version"),
        "providers": registry.describe()["providers"],
        "evidence_kinds": kinds,
        "assurance": "host_attested",
        "methods": resources,
        "method_release": method_release(resources),
        "review_channels": review_channels(adapter_context=adapter_context),
        "review_channel_status_scope": "registered_receipts_only; see review_channels for native and stage-specific entries",
        "review_channel_status": "available"
        if any(available[k] for k in ("independent_review_receipts", "human_review_receipts"))
        else "needs_reviewer",
        "limitations": [
            "Host-attested instructions do not verify human identity",
            "Method availability does not prove a Host read or applied the method",
            "No strict identity/review channel is implied by a CLI call",
        ],
    }
