"""Read actual native tool events; Host-supplied observer labels confer no trust.

The Codex adapter trusts the current user's local runtime event store, not a
provider signature. It reads only one identified completion, never reasoning
or conversation text. Unrecorded fields remain unknown.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .errors import TypedServiceError
from .models import sha256_bytes, validate_schema

UUID = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z")
ITEM = re.compile(r"exec-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z")
MAX_RECORD_BYTES = 64 * 1024 * 1024


def _literal_image_call(code):
    """Recognize one narrowly defined executed call, without evaluating JS.

    Arbitrary exec source and variables are not evidence of actual arguments.
    This profile accepts only a single awaited native call with a JSON literal
    and its direct generatedImage return. The matching native completion AND
    same-call output image are required separately below.
    """
    if not isinstance(code, str):
        return None
    if code.startswith("// @exec:"):
        code = code.partition("\n")[2]
    match = re.fullmatch(r"\s*const\s+result\s*=\s*await\s+tools\.image_gen__imagegen\((.+)\);\s*generatedImage\(result\);\s*", code, re.S)
    if not match:
        return None
    try:
        args = json.loads(match[1])
        if (not isinstance(args, dict) or set(args) != {"prompt", "transparent_background"}
                or not isinstance(args["prompt"], str) or not isinstance(args["transparent_background"], bool)):
            return None
        return args
    except (ValueError, TypeError):
        return None


class ObservationUnavailable(TypedServiceError):
    error_code = "tool_observation_unavailable"


def _unavailable(message):
    return ObservationUnavailable("observation/source", message)


def _session_root():
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser() / "sessions"


def _owned_file(path, root):
    """Reject symlinks and files outside this runtime's current-user directory."""
    try:
        relative = path.relative_to(root)
        parts = [root, *(root.joinpath(*relative.parts[:n]) for n in range(1, len(relative.parts) + 1))]
        if any(p.is_symlink() for p in parts) or path.resolve().is_relative_to(root.resolve()) is False:
            raise _unavailable("runtime event source is not a regular local file")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        handle = os.fdopen(fd, "rb")
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            handle.close()
            raise _unavailable("runtime event source is not owned by the current user")
        return handle
    except (OSError, ValueError) as exc:
        raise _unavailable("runtime event source cannot be read") from exc


@dataclass(frozen=True)
class CollectedObservation:
    metadata: dict
    output_bytes: bytes


def collect_codex_image(selector, *, minimum_started_at_ms=None):
    """Resolve identities in Codex's runtime store; no arbitrary JSON path input.

    Native image completions record revisedPrompt, transparentBackground and
    PNG bytes. They do not record attachments, model, seed or all provider
    parameters. A restricted, executed JSON-literal call with its same-call PNG
    return can additionally prove reference arguments were omitted. Arbitrary
    exec source, Host reports, image pixels and defaults confer no such proof.
    """
    allowed = {"source", "thread_id", "turn_id", "item_id"}
    if not isinstance(selector, dict) or set(selector) != allowed or selector.get("source") != "codex_session.v1":
        raise _unavailable("provide only source, thread_id, turn_id and item_id for a native Codex event")
    if (not all(isinstance(selector[k], str) and UUID.fullmatch(selector[k]) for k in ("thread_id", "turn_id"))
            or not isinstance(selector["item_id"], str) or not ITEM.fullmatch(selector["item_id"])):
        raise _unavailable("invalid runtime event identity")
    root = _session_root()
    try:
        candidates = list(root.glob(f"*/*/*/rollout-*-{selector['thread_id']}.jsonl"))
        if len(candidates) != 1:
            raise _unavailable("one matching local runtime session is required")
        found, session = None, None
        active_call, matched_call, literal_proof = None, None, None
        with _owned_file(candidates[0], root) as handle:
            limit = os.fstat(handle.fileno()).st_size
            line_number = 0
            while handle.tell() < limit:
                offset = handle.tell()
                raw = handle.readline(min(MAX_RECORD_BYTES + 1, limit - offset))
                line_number += 1
                if len(raw) > MAX_RECORD_BYTES:
                    raise _unavailable("runtime event exceeds the supported record size")
                if not raw.endswith(b"\n"):
                    break  # appending a completion is not a completed record
                record = json.loads(raw)
                payload = record.get("payload", {})
                if record.get("type") == "response_item" and payload.get("type") == "custom_tool_call":
                    literal = _literal_image_call(payload.get("input")) if payload.get("name") == "exec" else None
                    active_call = {"arguments": literal, "call_id": payload.get("call_id"), "record_sha256": sha256_bytes(raw)} if literal else None
                if (matched_call and record.get("type") == "response_item" and payload.get("type") == "custom_tool_call_output"
                        and payload.get("call_id") == matched_call["call_id"] and isinstance(payload.get("output"), list)):
                    images = [part.get("image_url", "") for part in payload["output"] if isinstance(part, dict) and part.get("type") == "input_image"]
                    if len(images) == 1 and images[0].startswith("data:image/png;base64,"):
                        returned = base64.b64decode(images[0].partition(",")[2], validate=True)
                        literal_proof = {**matched_call, "output_record_sha256": sha256_bytes(raw), "output_sha256": sha256_bytes(returned)}
                if record.get("type") == "session_meta":
                    if session is not None or payload.get("id") != selector["thread_id"]:
                        raise _unavailable("runtime session identity does not match")
                    session = payload
                    continue
                if record.get("type") != "event_msg" or payload.get("type") != "item_completed":
                    continue
                item = payload.get("item")
                if not isinstance(item, dict) or item.get("id") != selector["item_id"]:
                    continue
                if (payload.get("thread_id") != selector["thread_id"] or payload.get("turn_id") != selector["turn_id"]
                        or item.get("type") != "Extension" or item.get("kind") != "image_gen.generation"):
                    raise _unavailable("identity is not the selected native image completion")
                if found is not None:
                    raise _unavailable("ambiguous duplicate native completion")
                found = (payload, item, sha256_bytes(raw), line_number, offset)
                matched_call = active_call
        if not session or not found:
            raise _unavailable("native image completion is not yet available in this session")
        payload, item, record_hash, line_number, offset = found
        started, completed = payload.get("started_at_ms"), payload.get("completed_at_ms")
        if (not isinstance(started, int) or isinstance(started, bool) or not isinstance(completed, int)
                or isinstance(completed, bool) or completed < started
                or minimum_started_at_ms is not None and started < minimum_started_at_ms):
            raise _unavailable("native completion predates this attempt or has invalid timestamps")
        if item.get("status") != "completed" or item.get("failure") is not None:
            raise _unavailable("native image generation has no successful completion")
        if not isinstance(item.get("revisedPrompt"), str) or not item["revisedPrompt"]:
            raise _unavailable("native completion does not expose its recorded prompt")
        output = base64.b64decode(item["result"], validate=True)
        with Image.open(io.BytesIO(output)) as image:
            if image.format != "PNG":
                raise _unavailable("native completion is not a supported PNG output")
            dimensions = list(image.size)
            image.verify()
        generated_root = root.parent / "generated_images"
        expected_file = generated_root / selector["thread_id"] / (selector["item_id"] + ".png")
        if item.get("savedPath") != str(expected_file):
            raise _unavailable("native output is not bound to its runtime-generated file")
        with _owned_file(expected_file, generated_root) as handle:
            if sha256_bytes(handle.read()) != sha256_bytes(output):
                raise _unavailable("runtime event bytes and saved output differ")
    except ObservationUnavailable:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _unavailable("native completion is malformed or its output is unreadable") from exc
    transparent = item.get("transparentBackground")
    parameters = {"transparent_background": transparent} if isinstance(transparent, bool) else {}
    literal_verified = bool(literal_proof and literal_proof["output_sha256"] == sha256_bytes(output)
                            and literal_proof["arguments"] == {"prompt": item["revisedPrompt"], "transparent_background": transparent})
    metadata = {
        "schema_version": "tool_observation.v1", "observer": "tool_observed", "collector": "codex-session-image.v1",
        "source": {**selector, "session_cli_version": session.get("cli_version"), "record_sha256": record_hash,
                   "line_number": line_number, "byte_offset": offset},
        "invocation_ref": selector["item_id"], "started_at_ms": started, "completed_at_ms": completed,
        "submitted": {"prompt": item["revisedPrompt"], "references": [] if literal_verified else None, "parameters": parameters,
                      "model": None, "seed": None},
        "coverage": {"prompt": "native.revisedPrompt", "references": "unknown", "model": "unknown", "seed": "unknown",
                     "parameters": {key: "native.transparentBackground" for key in parameters}, "output": "native.result"},
        "output": {"sha256": sha256_bytes(output), "media_type": "image/png", "dimensions": dimensions},
        "trust_scope": "current-user local Codex runtime; not a provider signature",
    }
    if literal_verified:
        metadata["source"]["literal_call"] = {k: v for k, v in literal_proof.items() if k != "arguments"}
        metadata["coverage"]["references"] = "native completion + executed literal call + same-call PNG return; reference arguments omitted"
    validate_schema("tool_observation", metadata)
    return CollectedObservation(metadata=metadata, output_bytes=output)
