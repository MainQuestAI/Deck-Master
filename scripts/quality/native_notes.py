"""Resolve exact business notes from the current immutable native inputs.

This is a content binding, not a safety exemption: the delivery scanner still
checks every note for internal text, paths, commands and forbidden terms.
"""
from __future__ import annotations

import json
from pathlib import Path

from native_pptx.contracts import sha256_file, sha256_json


def current_native_notes(run_dir: str | Path | None, artifact: str | Path) -> dict[int, str]:
    if run_dir is None:
        return {}
    from workflow.actions import revision_read, read_revision_state

    root = Path(run_dir).resolve()
    artifact = Path(artifact).resolve()
    try:
        if not artifact.is_relative_to(root):
            return {}
        with revision_read(root) as revision:
            if not revision:
                return {}
            state = read_revision_state(root, revision)
            result = json.loads((root / "build/native_compile_result.json").read_text())
            output = result["outputs"]["deck_pptx"]
            if (result["engine_id"] != "deck_native" or result["status"] != "compiled"
                    or result.get("run_id") != root.name
                    or result["build_revision"] != revision
                    or Path(output["path"]).is_absolute() or ".." in Path(output["path"]).parts
                    or (root / output["path"]).resolve() != artifact
                    or output["sha256"] != sha256_file(artifact)):
                return {}
            packages = [json.loads(data) for name, data in state.items()
                        if Path(name).parent.as_posix() == "page_packages" and name.endswith(".json")
                        and name != "page_packages/index.json"]
            packages.sort(key=lambda package: package["order"])
            expected = [{"page_id": p["page_id"], "order": p["order"]} for p in packages]
            actual = [{"page_id": p["page_id"], "order": p["order"]} for p in result["pages"]]
            if not expected or expected != actual or len({p["page_id"] for p in packages}) != len(packages):
                return {}
            notes = {}
            for index, package in enumerate(packages, 1):
                page_id = package["page_id"]
                if package["status"] not in {"ready", "ready_for_build"} or package.get("run_id") != root.name:
                    return {}
                key = f"high_density_build/content_locks/{page_id}.content_lock.json"
                lock = json.loads(state.get(key, state.get(f"high_density_build/content_locks/{page_id}.json", b"{}")))
                value = str(package.get("speaker_notes") or "").strip()
                if (lock.get("page_id") != page_id or lock.get("run_id") != package.get("run_id")
                        or lock.get("page_package_sha256") != sha256_json(package)
                        or str(lock.get("speaker_notes") or "").strip() != value):
                    return {}
                notes[index] = value
            return notes
    except Exception:  # Any invalid binding keeps all notes subject to the default rejection.
        return {}
