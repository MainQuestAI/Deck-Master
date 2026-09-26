#!/usr/bin/env python3
"""Crash after a synthetic task commit, then recover through the public CLI.

PYTHONPATH=src python examples/workbench/w02_recovery.py --out /tmp/w02-recovery
No Host/model runs and no user project changes. The output directory must be new.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from deck_master import service, tasks
from deck_master.models import bump_revision, sha256_bytes
from deck_master.store import Store


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def crash_child(project, task_file, result_file):
    task = json.loads(task_file.read_bytes())
    # Fault injection at the real post-pointer publication boundary. This exits
    # the child process without unwinding Python frames or returning a response.
    tasks.write_operation_journal = lambda *args, **kwargs: os._exit(77)
    service.accept_result(project, result_payload=json.loads(result_file.read_bytes()),
                          **{key: task[key] for key in ("task_id", "operation_id", "produced_against")})
    raise AssertionError("the child did not reach the injected crash")


def exercise(out):
    with tempfile.TemporaryDirectory(prefix="deck-master-w02-recovery-") as scratch:
        root = Path(scratch)
        project = root / "synthetic-project"
        source = root / "synthetic.md"
        source.write_text("Synthetic recovery demonstration. No customer facts.", encoding="utf-8")
        service.create(project, brief="W02 recovery demonstration", sources=[source])
        task = service.continue_project(project)["pending_tasks"][0]
        result = {"kind": "compose", "page_order": ["synthetic-page"], "pages": [{"schema_version": "deck_page_package.v2",
                  "page_id": "synthetic-page", "customer_visible": {"title": "Recovery demonstration", "body_blocks": []},
                  "visual_spec": {"intent": "Synthetic example", "reference_mode": "new_design"}}]}
        task_file, result_file = root / "task.json", root / "result.json"
        write_json(task_file, task)
        write_json(result_file, result)
        write_json(out / "synthetic-result.json", result)
        binding = {key: task[key] for key in ("task_id", "operation_id", "produced_against")}
        write_json(out / "request-binding.json", binding)
        crashed = subprocess.run([sys.executable, __file__, "--crash-child", str(project), str(task_file), str(result_file)],
                                 capture_output=True, text=True, check=False)
        assert crashed.returncode == 77, crashed.stderr
        store = Store(project)
        applied = store.load_document()
        receipt = applied["change"]["operation_receipt"]
        cache = store.deck_root / "operations" / (task["operation_id"] + ".json")
        assert not cache.exists()
        later = bump_revision(applied, {"operation_id": "synthetic-later-progress", "kind": "task_update",
                                       "description": "Independent later progress", "read_set": []})
        store.commit_change(base_revision=applied["revision_id"], document=later, operation_id="synthetic-later-progress")
        pointer_before = (store.deck_root / "current.json").read_bytes()
        command = [sys.executable, "-m", "deck_master", "task", "accept", "--project", str(project),
                   "--task-id", task["task_id"], "--operation-id", task["operation_id"],
                   "--produced-against", task["produced_against"], "--result", str(result_file)]
        replayed = subprocess.run(command, capture_output=True, text=True, check=False)
        assert replayed.returncode == 0, replayed.stdout + replayed.stderr
        replay = json.loads(replayed.stdout)
        assert replay["status"] == "already_applied"
        assert replay["operation_result"] == receipt["response"]
        assert replay["revision_id"] == applied["revision_id"]
        assert replay["current_revision_id"] == later["revision_id"]
        assert cache.is_file()
        assert (store.deck_root / "current.json").read_bytes() == pointer_before
        write_json(out / "committed-receipt.json", receipt)
        write_json(out / "cli-replay.json", replay)
        write_json(out / "rebuilt-cache.json", json.loads(cache.read_bytes()))
        write_json(out / "checks.json", {"status": "passed", "synthetic": True, "evidence_level": "core/CLI/process-fault",
                   "crash_exit": crashed.returncode, "replay_exit": replayed.returncode,
                   "applied_revision": applied["revision_id"], "current_revision": later["revision_id"],
                   "pointer_unchanged_sha256": sha256_bytes(pointer_before), "operation_result_unchanged": True,
                   "receipt_cache_rebuilt": True, "host_calls": 0,
                   "environment": {"python": platform.python_version(), "os": platform.platform()},
                   "source_command": "PYTHONPATH=src python examples/workbench/w02_recovery.py --out <new-directory>"})
        print(json.dumps({"status": "passed", "crash_exit": 77, "replay_exit": 0, "current_unchanged": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--crash-child", nargs=3, type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.crash_child:
        crash_child(*args.crash_child)
    if not args.out:
        parser.error("--out is required")
    args.out.mkdir(parents=True, exist_ok=False)
    exercise(args.out)


if __name__ == "__main__":
    main()
