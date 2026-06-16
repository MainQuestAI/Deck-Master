from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_master_import_log.v1"
IMPORTS_DIR = "imports"
IMPORT_LOG_NAME = "import_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_import_log(
    run_dir: str | Path,
    *,
    import_type: str,
    source: str,
    status: str,
    source_path: str | Path | None = None,
    canonical_refs: list[str] | None = None,
    legacy_refs: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    imports_dir = root / IMPORTS_DIR
    imports_dir.mkdir(parents=True, exist_ok=True)

    source_ref = ""
    source_hash = ""
    if source_path:
        src = Path(source_path).expanduser()
        if src.exists() and src.is_file():
            resolved = src.resolve()
            source_ref = str(resolved)
            source_hash = _sha256(resolved)
        else:
            source_ref = str(src)

    entry = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": _utc_now(),
        "import_type": import_type,
        "source": source,
        "status": status,
        "source_path": source_ref,
        "source_sha256": source_hash,
        "canonical_refs": canonical_refs or [],
        "legacy_refs": legacy_refs or [],
        "warnings": warnings or [],
        "errors": errors or [],
        "payload": payload or {},
    }
    with (imports_dir / IMPORT_LOG_NAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_import_log(run_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(run_dir).expanduser().resolve() / IMPORTS_DIR / IMPORT_LOG_NAME
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def summarize_import_log(run_dir: str | Path) -> dict[str, Any]:
    entries = read_import_log(run_dir)
    by_type: dict[str, dict[str, int]] = {}
    for entry in entries:
        import_type = str(entry.get("import_type") or "unknown")
        status = str(entry.get("status") or "unknown")
        by_type.setdefault(import_type, {})
        by_type[import_type][status] = by_type[import_type].get(status, 0) + 1
    return {
        "schema_version": "deck_master_import_summary.v1",
        "total": len(entries),
        "by_type": by_type,
        "latest": entries[-1] if entries else None,
    }
