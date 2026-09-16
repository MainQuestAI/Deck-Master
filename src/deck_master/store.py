"""Atomic project store for the rebuilt core.

Layout (spec 03.2)::

    <project>/.deckmaster/
      current.json            # {format, revision_id}; the only current pointer
      revisions/<rev>.json    # immutable Document snapshots
      objects/<sha2>/<sha>.<ext>
      staging/<operation_id>/ # scratch; never becomes current directly
      write.lock

``commit_change`` runs inside an advisory file lock: re-read the pointer,
verify the declared read_set against current objects, honor cancellation,
stage writes, write the new Document snapshot, and atomically swap the
pointer last. At any crash point the project is either fully old or fully
new (AC-S01); bad bytes can never overwrite existing objects (AC-S02).
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterator

from .models import (
    ModelError,
    canonical_json_bytes,
    sha256_bytes,
    validate_document_semantics,
    validate_ref,
)

CURRENT_FORMAT = "deckmaster-current.v1"
DECKMASTER_DIR = ".deckmaster"
OPERATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class StoreError(RuntimeError):
    """Storage-layer failure with the offending path."""

    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.detail = detail


class ConflictError(StoreError):
    """Base revision moved or read_set no longer matches; caller must rebase."""


class OperationCancelled(StoreError):
    """The cancelled_task_check reported cancellation before the swap."""


class Store:
    def __init__(self, project_root: Path | str) -> None:
        self.project_root = Path(project_root).resolve()
        self.deck_root = self.project_root / DECKMASTER_DIR
        self.objects_dir = self.deck_root / "objects"
        self.revisions_dir = self.deck_root / "revisions"
        self.staging_dir = self.deck_root / "staging"
        self.lock_path = self.deck_root / "write.lock"

    # ---------- setup ----------

    def ensure_layout(self) -> None:
        for directory in (
            self.deck_root,
            self.objects_dir,
            self.revisions_dir,
            self.staging_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def init_project(self, document: dict[str, Any], operation_id: str | None = None) -> str:
        """First commit: writes the create Document and points current at it."""
        self.ensure_layout()
        validate_document_semantics(document)
        with self._locked():
            if (self.deck_root / "current.json").exists():
                raise StoreError("current.json", "project already initialised")
            return self._commit_locked(
                base_revision=None,
                document=document,
                blobs=[],
                operation_id=operation_id or document["change"]["operation_id"],
                cancelled_task_check=None,
            )

    # ---------- object storage ----------

    def put_blob(
        self,
        data: bytes,
        *,
        ext: str,
        operation_id: str | None = None,
    ) -> dict[str, str]:
        """Store immutable bytes content-addressed; identical bytes reuse the object."""
        if not isinstance(data, (bytes, bytearray)):
            raise StoreError("(blob)", "data must be bytes")
        data = bytes(data)
        ext = self._check_ext(ext)
        digest = sha256_bytes(data)
        rel_path = f".deckmaster/objects/{digest[:2]}/{digest}.{ext}"
        target = self._resolve_object_path(rel_path)
        if target.exists() or target.is_symlink():
            if target.is_symlink():
                raise StoreError(rel_path, "existing symlink at object path; refusing to write")
            if sha256_bytes(target.read_bytes()) == digest:
                return {"path": rel_path, "sha256": digest}
            raise StoreError(rel_path, "existing object has different bytes; refusing overwrite")
        stage_dir = self._stage_dir(operation_id)
        stage_dir.mkdir(parents=True, exist_ok=True)
        staged = stage_dir / f"{digest}.{ext}"
        _atomic_write_bytes(staged, data)
        target.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileExistsError):
            os.link(staged, target)
        if not target.exists():
            _atomic_write_bytes(target, data)
        staged.unlink(missing_ok=True)
        if sha256_bytes(target.read_bytes()) != digest:
            raise StoreError(rel_path, "object bytes do not match digest after write")
        return {"path": rel_path, "sha256": digest}

    def put_json_object(self, obj: Any, *, operation_id: str | None = None) -> dict[str, str]:
        return self.put_blob(canonical_json_bytes(obj), ext="json", operation_id=operation_id)

    def _check_ext(self, ext: str) -> str:
        if not isinstance(ext, str) or not ext or not ext.isalnum() or ext != ext.lower():
            raise StoreError(f"(ext {ext!r})", "extension must be lowercase alphanumeric")
        return ext

    def _resolve_object_path(self, rel_path: str) -> Path:
        candidate = (self.project_root / rel_path).resolve()
        objects_root = self.objects_dir.resolve()
        if not candidate.is_relative_to(objects_root):
            raise StoreError(rel_path, "path escapes .deckmaster/objects")
        walked = self.deck_root
        for part in Path(rel_path).parts[1:]:
            walked = walked / part
            if walked.is_symlink():
                raise StoreError(rel_path, f"symlink component {part!r} in object path")
        return candidate

    def read_object_bytes(self, ref: dict[str, str]) -> bytes:
        try:
            validate_ref(ref, where="(read ref)")
        except ModelError as exc:
            raise StoreError(exc.path, exc.detail) from exc
        target = self._resolve_object_path(ref["path"])
        if not target.is_file():
            raise StoreError(ref["path"], "object file missing")
        data = target.read_bytes()
        if sha256_bytes(data) != ref["sha256"]:
            raise StoreError(ref["path"], "object bytes do not match declared sha256")
        return data

    def read_object_json(self, ref: dict[str, str]) -> Any:
        data = self.read_object_bytes(ref)
        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StoreError(ref["path"], f"object is not valid JSON: {exc}") from exc

    # ---------- documents ----------

    def current_revision_id(self) -> str | None:
        pointer = self.read_current()
        if pointer is None:
            return None
        return pointer["revision_id"]

    def read_current(self) -> dict[str, Any] | None:
        pointer_path = self.deck_root / "current.json"
        if not pointer_path.is_file():
            return None
        try:
            pointer = json.loads(pointer_path.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError("current.json", f"unreadable pointer: {exc}") from exc
        if pointer.get("format") != CURRENT_FORMAT:
            raise StoreError("current.json", f"unknown pointer format {pointer.get('format')!r}")
        return pointer

    def load_document(self, revision_id: str | None = None) -> dict[str, Any]:
        revision_id = revision_id or self.current_revision_id()
        if revision_id is None:
            raise StoreError("(document)", "no current revision")
        path = self.revisions_dir / f"{revision_id}.json"
        if not path.is_file():
            raise StoreError(f"revisions/{revision_id}.json", "revision snapshot missing")
        document = json.loads(path.read_text("utf-8"))
        if document.get("revision_id") != revision_id:
            raise StoreError(
                f"revisions/{revision_id}.json",
                "snapshot content revision_id does not match its file name",
            )
        return document

    def save_revision(self, document: dict[str, Any]) -> Path:
        validate_document_semantics(document)
        revision_id = document["revision_id"]
        self.revisions_dir.mkdir(parents=True, exist_ok=True)
        path = self.revisions_dir / f"{revision_id}.json"
        if path.exists():
            if path.read_bytes() != canonical_json_bytes(document):
                raise StoreError(
                    f"revisions/{revision_id}.json",
                    "revision file exists with different content; revision ids are immutable",
                )
            return path
        _atomic_write_bytes(path, canonical_json_bytes(document))
        return path

    # ---------- commit ----------

    def commit_change(
        self,
        *,
        base_revision: str | None,
        document: dict[str, Any],
        operation_id: str,
        read_set: list[dict[str, str]] | None = None,
        cancelled_task_check: Callable[[], bool] | None = None,
    ) -> str:
        """Atomic change commit; returns the new revision id.

        ``read_set`` entries must match current object bytes. The Document is
        written first and the pointer swaps last, so a crash leaves either
        the complete old or the complete new state (AC-S01).
        """
        self.ensure_layout()
        with self._locked():
            return self._commit_locked(
                base_revision=base_revision,
                document=document,
                blobs=[],
                operation_id=operation_id,
                read_set=read_set,
                cancelled_task_check=cancelled_task_check,
            )

    def _commit_locked(
        self,
        *,
        base_revision: str | None,
        document: dict[str, Any],
        blobs: list[dict[str, str]],
        operation_id: str | None = None,
        read_set: list[dict[str, str]] | None = None,
        cancelled_task_check: Callable[[], bool] | None = None,
    ) -> str:
        if cancelled_task_check is not None and cancelled_task_check():
            raise OperationCancelled("(commit)", "operation cancelled before pointer swap")
        effective_read_set = read_set
        if effective_read_set is None:
            effective_read_set = (document.get("change") or {}).get("read_set") or []
        for entry in effective_read_set:
            self._verify_read_set_entry(entry)
        for ref in blobs:
            self.read_object_bytes(ref)
        validate_document_semantics(document)
        change = document.get("change") or {}
        change_operation = operation_id or change.get("operation_id") or ""
        _validate_operation_id(change_operation)
        if change.get("operation_id") != change_operation:
            change["operation_id"] = change_operation
            document["change"] = change
        current = self.read_current()
        if current is not None:
            try:
                current_document = self.load_document(current["revision_id"])
            except StoreError:
                current_document = None
            current_operation = (current_document or {}).get("change", {}).get("operation_id")
            if current_operation == change_operation:
                # Idempotent replay of an already-committed operation.
                if current_document is not None and current_document["revision_id"] == document.get("revision_id"):
                    return current["revision_id"]
                raise StoreError(
                    "current.json",
                    f"operation {change_operation} already committed with a different result; "
                    "re-running the same operation must reproduce the same revision",
                )
        if current is not None and base_revision is not None and current["revision_id"] != base_revision:
            raise ConflictError(
                "current.json",
                f"base {base_revision!r} is not current (now {current['revision_id']!r}); rebase required",
            )
        self.save_revision(document)
        pointer = {"format": CURRENT_FORMAT, "revision_id": document["revision_id"]}
        _atomic_write_bytes(self.deck_root / "current.json", canonical_json_bytes(pointer))
        return document["revision_id"]

    # ---------- locks and staging ----------

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        self.ensure_layout()
        handle = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            os.close(handle)

    def _verify_read_set_entry(self, entry: dict[str, Any]) -> None:
        """Object-path entries must match current bytes; other identities are opaque."""
        identity = entry.get("identity") if isinstance(entry, dict) else None
        sha = entry.get("sha256") if isinstance(entry, dict) else None
        if not isinstance(identity, str) or not identity.startswith(".deckmaster/objects/"):
            return
        try:
            self.read_object_bytes({"path": identity, "sha256": sha})
        except StoreError as exc:
            raise ConflictError(identity, f"read_set entry no longer matches: {exc.detail}") from exc

    def _stage_dir(self, operation_id: str | None) -> Path:
        name = operation_id or "anonymous"
        _validate_operation_id(name)
        return self.staging_dir / name

    def clean_staging(self, operation_id: str | None = None) -> None:
        target = self._stage_dir(operation_id) if operation_id else self.staging_dir
        if target.exists():
            shutil.rmtree(target)


def _validate_operation_id(operation_id: str) -> None:
    if not isinstance(operation_id, str) or not OPERATION_ID_PATTERN.fullmatch(operation_id):
        raise StoreError(
            f"(operation_id {operation_id!r})",
            "operation ids must match [A-Za-z0-9][A-Za-z0-9_.-]*",
        )


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp-")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        tmp.unlink(missing_ok=True)


def open_store(project_root: Path | str) -> Store:
    return Store(project_root)
