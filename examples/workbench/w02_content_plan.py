#!/usr/bin/env python3
"""Runnable synthetic ContentPlan example; no model or production acceptance.

Create/start and replay/read use the public CLI. The first adoption uses the
same Service without opening a browser, so this core example is self-contained.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from deck_master import content_plan, service
from deck_master.models import sha256_bytes
from deck_master.store import Store


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def cli(out, name, *args, allowed=(0,)):
    completed = subprocess.run([sys.executable, "-m", "deck_master", *map(str, args)], capture_output=True, text=True)
    save(out / (name + "-process.json"), {"exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
    if completed.returncode not in allowed:
        raise RuntimeError(f"{name} failed; inspect its saved process result")
    value = json.loads(completed.stdout)
    save(out / (name + ".json"), value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out / "synthetic-material.md"
    source.write_text("# 合成协议样例\n流程依次为登记、核对、归档。\n材料没有提供节省时间或产出提升数据。\n")
    project = out / "synthetic-project"
    created = cli(out, "create", "create", "--out", project, "--brief", "说明三个步骤及证据缺口",
                  "--source", source, "--project-format", "workbench.v3", "--no-open")
    task = next(t for t in created["pending_tasks"] if t["kind"] == "compose")
    cli(out, "start", "task", "start", "--project", project, "--task-id", task["task_id"],
        "--execution-ref", "synthetic-content-plan-example", "--supported-protocol", content_plan.PROTOCOL,
        *(arg for cap in content_plan.CAPABILITIES for arg in ("--capability", cap)))
    binding = task["content_plan_contract"]["sources"][0]
    plan = {"schema_version": "content_plan_input.v1", "input_summary": "流程步骤有明确依据，成效尚无实测数据。",
            "chapters": [{"chapter_id": "workflow", "title": "流程与依据", "goal_ids": ["explain", "verify"]}],
            "goals": [{"goal_id": "explain", "page_id": "steps", "purpose": "解释登记、核对、归档的顺序",
                       "source_links": [{**binding, "locator": "L2"}], "unresolved_facts": []},
                      {"goal_id": "verify", "page_id": "evidence", "purpose": "指出成效尚待实测",
                       "source_links": [{**binding, "locator": "L3"}], "unresolved_facts": ["需实际测量节省时间。"]}],
            "unresolved_facts": ["不能由三个步骤推定成效。"]}
    envelope = {"kind": "compose", "page_order": ["steps", "evidence"], "content_plan": plan,
                "pages": [{"schema_version": "deck_page_package.v2", "page_id": pid,
                           "customer_visible": {"title": title, "body_blocks": [{"id": "body", "type": "paragraph", "text": body}]},
                           "visual_spec": {"intent": "Synthetic traceability example", "reference_mode": "new_design"}}
                          for pid, title, body in [("steps", "先登记，再核对，最后归档", "材料列明登记、核对、归档三个步骤。"),
                                                   ("evidence", "成效需要另行测量", "当前材料没有节省时间或提升产出的实测数据。")]]}
    save(out / "result-envelope.json", envelope)
    accepted = service.accept_result(project, result_payload=envelope,
                                     **{k: task[k] for k in ("task_id", "operation_id", "produced_against")})
    save(out / "accepted.json", accepted)
    store = Store(project)
    doc = store.load_document()
    save(out / "stored-plan.json", store.read_object_json(doc["content_plan"]))
    replayed = cli(out, "replay", "task", "accept", "--project", project, "--task-id", task["task_id"],
                   "--operation-id", task["operation_id"], "--produced-against", task["produced_against"],
                   "--result", out / "result-envelope.json")
    before = (store.deck_root / "current.json").read_bytes()
    shown = cli(out, "outline", "view", "--project", project, "--content-plan", "--revision", doc["revision_id"])
    lineage = cli(out, "lineage", "view", "--project", project, "--page-id", "steps", "--lineage", "--revision", doc["revision_id"])
    assert replayed["status"] == "already_applied" and doc["content_plan"] in replayed["result_refs"]
    assert shown["content_plan"]["applicability"] == "current"
    assert lineage["content_plan"]["goals"][0]["page_ref"] == doc["pages"][0]["page"]
    assert before == (store.deck_root / "current.json").read_bytes()
    save(out / "checks.json", {"status": "passed", "synthetic": True, "evidence_level": "core/CLI", "host_calls": 0,
         "task_id": task["task_id"], "revision_id": doc["revision_id"], "plan_ref": doc["content_plan"],
         "page_count": 2, "chapter_count": 1, "goal_count": 2, "source_hash": sha256_bytes(source.read_bytes()),
         "unresolved_fact_recorded": True, "same_operation_replay": True,
         "pointer_unchanged_sha256": sha256_bytes(before), "cli_read_exit_codes": [0, 0]})
    print(json.dumps({"status": "passed", "evidence_level": "core/CLI", "host_calls": 0, "pages": 2, "goals": 2}))


if __name__ == "__main__":
    main()
