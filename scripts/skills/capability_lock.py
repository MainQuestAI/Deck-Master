"""SC-1 managed capability lock support.

Extends the release capability lock (``deck_capability_lock.v1``, additive)
with pinned per-component records so that the same lock can be verified and
re-installed reproducibly:

- ``components``: bundled capability packages shipped inside the release tree,
  each with a deterministic ``content_sha256`` over the component directory.
- ``runtime_components``: managed production components installed outside the
  release tree (``~/.deck-master/backends/<name>/<sha>/``), such as the
  PPT Master backend package and the PPT Library CLI executable.

The lock never records floating versions ("latest") or machine-specific
absolute paths; managed roots are addressed through the ``current`` pointer
inside ``~/.deck-master``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from skills.installer import CAPABILITY_LOCK_NAME, _repo_root, _suite_version as _installer_suite_version, _utc_now
except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
    from scripts.skills.installer import (
        CAPABILITY_LOCK_NAME,
        _repo_root,
        _suite_version as _installer_suite_version,
        _utc_now,
    )

LOCK_COMPONENTS_KEY = "components"
LOCK_RUNTIME_COMPONENTS_KEY = "runtime_components"
CAPABILITY_PACKAGE_NAMES = ("ppt-master", "ppt-library", "ppt-deck-pro-max", "ppt-quality-gate")
MANAGED_ROOT_NAME = "backends"
MANAGED_POINTER_NAME = "current"
DEFAULT_LICENSE = "Apache-2.0"
COMPONENT_OWNERSHIP = "deck_master_managed"


def _utc_now_local() -> str:
    try:
        return _utc_now()
    except Exception:  # pragma: no cover - installer helper always available in practice.
        return datetime.now(timezone.utc).isoformat()


def component_content_sha256(root: Path) -> str:
    """Deterministic sha256 over a component directory's file contents."""

    digest = hashlib.sha256()
    base = root.resolve()
    entries: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for filename in filenames:
            entries.append(Path(dirpath) / filename)
    for path in sorted(entries, key=lambda item: item.relative_to(base).as_posix()):
        rel = path.relative_to(base).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _suite_version() -> str:
    try:
        return _installer_suite_version()
    except Exception:  # pragma: no cover - defensive; installer provides the real value.
        return ""


def bundled_component_records(release_root: Path) -> list[dict[str, Any]]:
    """Pin the bundled ppt-* capability packages shipped in the release tree."""

    records: list[dict[str, Any]] = []
    capabilities_root = release_root / "capabilities"
    for name in CAPABILITY_PACKAGE_NAMES:
        component_dir = capabilities_root / name
        if not component_dir.is_dir():
            continue
        records.append(
            {
                "name": name,
                "kind": "capability_package",
                "path": f"capabilities/{name}",
                "source_kind": "bundled_release_tree",
                "version": _suite_version(),
                "license": DEFAULT_LICENSE,
                "ownership": COMPONENT_OWNERSHIP,
                "content_sha256": component_content_sha256(component_dir),
            }
        )
    return records


def managed_component_root(name: str) -> Path:
    return Path.home() / ".deck-master" / MANAGED_ROOT_NAME / name


def managed_component_current(name: str) -> Path | None:
    pointer = managed_component_root(name) / MANAGED_POINTER_NAME
    if pointer.exists():
        return pointer.resolve()
    return None


def _runtime_component_record(name: str) -> dict[str, Any]:
    current = managed_component_current(name)
    record: dict[str, Any] = {
        "name": name,
        "kind": "managed_runtime_component",
        "managed_root": f"~/.deck-master/{MANAGED_ROOT_NAME}/{name}",
        "source_kind": "managed_release",
        "ownership": COMPONENT_OWNERSHIP,
        "installed": bool(current and current.is_dir()),
        "version": "",
        "content_sha256": "",
    }
    if current and current.is_dir():
        manifest_path = current / "managed_component_manifest.json"
        version = ""
        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                version = str(payload.get("version") or "")
            except (json.JSONDecodeError, OSError):
                version = ""
        record["version"] = version
        record["content_sha256"] = component_content_sha256(current)
    return record


def runtime_component_records() -> list[dict[str, Any]]:
    return [_runtime_component_record(name) for name in ("ppt-master", "ppt-library")]


def augment_capability_lock(lock_payload: dict[str, Any], release_root: Path) -> dict[str, Any]:
    """Add pinned component records to an existing capability lock payload."""

    payload = dict(lock_payload)
    payload[LOCK_COMPONENTS_KEY] = bundled_component_records(release_root)
    payload[LOCK_RUNTIME_COMPONENTS_KEY] = runtime_component_records()
    payload["pinning_policy"] = {
        "floating_versions_allowed": False,
        "dev_absolute_paths_recorded": False,
        "managed_root": f"~/.deck-master/{MANAGED_ROOT_NAME}",
        "reinstall_strategy": "same_lock_reproduces_same_tree",
    }
    return payload


def verify_capability_lock(release_root: Path) -> dict[str, Any]:
    """Recompute pinned hashes and report drift. Fail-closed on missing lock."""

    lock_path = release_root / CAPABILITY_LOCK_NAME
    result: dict[str, Any] = {
        "lock_path": str(lock_path),
        "exists": lock_path.exists(),
        "verified": False,
        "components": [],
        "runtime_components": [],
        "failures": [],
    }
    if not lock_path.exists():
        result["failures"].append("capability lock is missing")
        return result
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result["failures"].append(f"capability lock is unreadable: {exc}")
        return result

    for record in payload.get(LOCK_COMPONENTS_KEY) or []:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name") or "")
        component_path = release_root / str(record.get("path") or "")
        item = {"name": name, "status": "pass", "expected_sha256": record.get("content_sha256")}
        if not component_path.is_dir():
            item["status"] = "missing"
            result["failures"].append(f"component {name} is missing from the release tree")
        else:
            actual = component_content_sha256(component_path)
            item["actual_sha256"] = actual
            if str(record.get("content_sha256") or "") != actual:
                item["status"] = "drift"
                result["failures"].append(f"component {name} content hash drifted")
        result["components"].append(item)

    for record in payload.get(LOCK_RUNTIME_COMPONENTS_KEY) or []:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name") or "")
        current = managed_component_current(name)
        item = {"name": name, "status": "pass" if record.get("installed") else "not_installed"}
        if record.get("installed") and current and current.is_dir():
            actual = component_content_sha256(current)
            item["actual_sha256"] = actual
            if str(record.get("content_sha256") or "") != actual:
                item["status"] = "drift"
                result["failures"].append(f"managed component {name} content hash drifted")
        elif not record.get("installed"):
            item["status"] = "not_installed"
        result["runtime_components"].append(item)

    result["verified"] = not result["failures"]
    return result


def _source_version(name: str, source: Path) -> str:
    if name == "ppt-library":
        try:
            result = subprocess.run([str(source / "bin/ppt-lib"), "--version"], capture_output=True, text=True, timeout=15)
            match = re.fullmatch(r"ppt-lib\s+(\S+)", result.stdout.strip())
            if result.returncode == 0 and match:
                return match.group(1)
        except (OSError, subprocess.TimeoutExpired):
            pass
    for filename in ("managed_component_manifest.json", "package.json", "capability.json"):
        path = source / filename
        if path.is_file():
            try:
                value = json.loads(path.read_text()).get("version")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            except (OSError, ValueError):
                pass
    return "unknown"


def install_managed_component(name: str, source_dir: str | Path) -> dict[str, Any]:
    """Install a component copy under the managed root and flip the current pointer.

    Layout: ``~/.deck-master/backends/<name>/<content_sha>/`` with a
    ``managed_component_manifest.json`` and a ``current`` symlink. Installing
    the same content twice is idempotent (same sha directory, pointer rewrite).
    """

    if name not in CAPABILITY_PACKAGE_NAMES and name not in {"ppt-master", "ppt-library"}:
        raise ValueError(f"Unknown managed component: {name}")
    source = Path(source_dir).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"Managed component source is not a directory: {source}")
    content_sha = component_content_sha256(source)
    component_version = _source_version(name, source)
    target_root = managed_component_root(name)
    target = target_root / content_sha
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target_root / f".staging-{content_sha[:12]}"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(source, staging)
        (staging / "managed_component_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "deck_managed_component_manifest.v1",
                    "name": name,
                    "version": component_version,
                    "content_sha256": content_sha,
                    "source_kind": "managed_release",
                    "ownership": COMPONENT_OWNERSHIP,
                    "license": DEFAULT_LICENSE,
                    "installed_at": _utc_now_local(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        staging.rename(target)
    # Correct metadata from earlier installers that recorded the suite version.
    manifest_path = target / "managed_component_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("version") != component_version:
        manifest["version"] = component_version
        replacement = target / ".managed_component_manifest.json.tmp"
        replacement.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        os.replace(replacement, manifest_path)
    pointer = target_root / MANAGED_POINTER_NAME
    if pointer.is_symlink() or pointer.exists():
        pointer.unlink()
    pointer.symlink_to(target)
    return {
        "name": name,
        "installed_path": str(target),
        "content_sha256": content_sha,
        "version": component_version,
    }
