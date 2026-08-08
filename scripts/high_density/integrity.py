from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path
from typing import Any

from .contracts import ContractError, canonical_json, sha256_bytes, sha256_json

KEY_ENV = "DECK_MASTER_RUNTIME_INTEGRITY_KEY"
KEY_FILE_ENV = "DECK_MASTER_RUNTIME_INTEGRITY_KEY_FILE"
DEFAULT_KEY_PATH = Path("~/.deck-master/security/runtime-integrity.key")


def _key_path() -> Path:
    configured = os.environ.get(KEY_FILE_ENV)
    return Path(configured).expanduser().resolve() if configured else DEFAULT_KEY_PATH.expanduser().resolve()


def _decode_env_key(value: str) -> bytes:
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise ContractError(f"{KEY_ENV} must be a 64-character hexadecimal key") from exc
    if len(key) != 32:
        raise ContractError(f"{KEY_ENV} must encode exactly 32 bytes")
    return key


def _runtime_key() -> bytes:
    configured = os.environ.get(KEY_ENV)
    if configured:
        return _decode_env_key(configured)

    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.parent.chmod(0o700)
    except OSError as exc:
        raise ContractError(f"cannot secure Runtime integrity directory: {path.parent}") from exc
    try:
        encoded = path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        encoded = secrets.token_hex(32)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            encoded = path.read_text(encoding="ascii").strip()
        else:
            with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                handle.write(encoded + "\n")
    key = _decode_env_key(encoded)
    try:
        path.chmod(0o600)
    except OSError as exc:
        raise ContractError(f"cannot secure Runtime integrity key: {path}") from exc
    return key


def sign_runtime_payload(purpose: str, payload: dict[str, Any]) -> dict[str, str]:
    if not purpose:
        raise ContractError("Runtime integrity purpose is required")
    key = _runtime_key()
    signed = {"purpose": purpose, "payload": payload}
    return {
        "algorithm": "hmac-sha256",
        "key_id": sha256_bytes(key)[:16],
        "payload_sha256": sha256_json(payload),
        "signature": hmac.new(key, canonical_json(signed), hashlib.sha256).hexdigest(),
    }


def verify_runtime_payload(purpose: str, payload: dict[str, Any], integrity: dict[str, Any]) -> None:
    if not isinstance(integrity, dict):
        raise ContractError(f"Runtime integrity receipt is missing for {purpose}")
    key = _runtime_key()
    expected = sign_runtime_payload(purpose, payload)
    for field in ("algorithm", "key_id", "payload_sha256"):
        if str(integrity.get(field) or "") != expected[field]:
            raise ContractError(f"Runtime integrity {field} is stale for {purpose}")
    if not hmac.compare_digest(str(integrity.get("signature") or ""), expected["signature"]):
        raise ContractError(f"Runtime integrity signature is invalid for {purpose}")


__all__ = ["sign_runtime_payload", "verify_runtime_payload"]
