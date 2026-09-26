#!/usr/bin/env python3
"""Two-phase real Host example; the Host executes ImageGen between phases.

prepare --out <new-dir> --thread-id <actual-id> --turn-id <actual-id>
complete --out <same-dir> --item-id <actual-native-image-item-id>

Uses a clearly synthetic project and actual CLI responses. It never invokes
a provider, fakes a tool receipt, or treats a fixture as real acceptance.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

from deck_master import generation, service
from deck_master.models import canonical_json_bytes, sha256_bytes
from deck_master.store import Store


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cli(out, name, *args, allowed=(0,)):
    result = subprocess.run([sys.executable, "-m", "deck_master", *map(str, args)], capture_output=True, text=True, check=False)
    save(out / (name + "-process.json"), {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode not in allowed:
        raise RuntimeError(f"{name} failed; inspect its saved process result")
    value = json.loads(result.stdout)
    save(out / (name + ".json"), value)
    return value


def prepare(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    project = out / "synthetic-project"
    draft = {"pages": [{"schema_version": "deck_page_package.v2", "page_id": "traceable-generation",
             "customer_visible": {"title": "一次生成，保留可核对的记录", "subtitle": "合成验证样例",
              "body_blocks": [{"id": "steps", "type": "bullets", "heading": "每一步都有明确依据", "items": [
                  {"id": "request", "text": "调用前冻结准确提示词"},
                  {"id": "observation", "text": "调用后核对工具原生记录"},
                  {"id": "output", "text": "按图片字节绑定生成结果"}]}]},
             "visual_spec": {"intent": "A clean three-step business slide, synthetic software verification sample.", "reference_mode": "new_design"}}]}
    save(out / "synthetic-draft.json", draft)
    # Local setup uses the same create service; all Host handoff actions below
    # use the public CLI. This avoids opening a UI for an isolated core example.
    service.create(project, brief="Synthetic W02 real Host binding verification", draft=draft, project_format="workbench.v3")
    continued = cli(out, "continue", "continue", "--project", project, allowed=(0, 3))
    task = next(t for t in continued["pending_tasks"] if t["kind"] == "blueprint")
    execution = f"codex:{args.thread_id}:{args.turn_id}"
    claimed = cli(out, "start", "task", "start", "--project", project, "--task-id", task["task_id"],
                  "--execution-ref", execution, "--supported-protocol", generation.PROTOCOL,
                  *(arg for cap in generation.CAPABILITIES for arg in ("--capability", cap)))
    value = task["generation_input"]
    value["parameters"] = {"transparent_background": False}
    save(out / "request-input.json", value)
    frozen = cli(out, "freeze", "requests", "freeze", "--project", project, "--task-id", task["task_id"],
                 "--input", out / "request-input.json", "--base-revision", claimed["revision_id"], "--operation-id", str(uuid.uuid4()))
    allowance = next(c["allowance_id"] for c in task["call_allowances"] if c["state"] == "reserved")
    begun = cli(out, "begin", "task", "call", "begin", "--project", project, "--task-id", task["task_id"],
                "--allowance-id", allowance, "--execution-ref", execution, "--request-id", frozen["request_id"])
    save(out / "handoff.json", {"synthetic": True, "thread_id": args.thread_id, "turn_id": args.turn_id,
         "task_id": task["task_id"], "operation_id": task["operation_id"], "produced_against": task["produced_against"],
         "page_id": task["scope_pages"][0], "request_id": frozen["request_id"], "input_hash": frozen["input_hash"],
         "attempt_id": begun["attempt_id"], "allowance_id": allowance})
    print(json.dumps({"status": "awaiting_real_host", "request_id": frozen["request_id"], "attempt_id": begun["attempt_id"],
                      "instruction": "Pass freeze.json input.prompt exactly to the built-in ImageGen tool with transparent_background=false. No reference images. Then complete using its actual native item ID."}))


def complete(args):
    out = args.out
    handoff = json.loads((out / "handoff.json").read_bytes())
    project = out / "synthetic-project"
    selector = {"source": "codex_session.v1", "thread_id": handoff["thread_id"], "turn_id": handoff["turn_id"], "item_id": args.item_id}
    save(out / "observation-selector.json", selector)
    cli(out, "settle", "task", "call", "settle", "--project", project, "--task-id", handoff["task_id"],
        "--allowance-id", handoff["allowance_id"], "--attempt-id", handoff["attempt_id"], "--outcome", "consumed",
        "--report", out / "observation-selector.json")
    shown = cli(out, "attempt", "attempts", "show", "--project", project, "--attempt-id", handoff["attempt_id"])
    store = Store(project)
    output_ref = shown["attempt"]["output_refs"][-1]
    raw = store.read_object_bytes(output_ref)
    stage = store.staging_dir / handoff["operation_id"]
    stage.mkdir(exist_ok=True)
    (stage / "native-output.png").write_bytes(raw)
    result = {"kind": "blueprint", "generation_result": {"request_id": handoff["request_id"], "attempt_id": handoff["attempt_id"]},
              "files": [{"file_id": "native-output", "path": "native-output.png", "media_type": "image/png"}],
              "artifact_specs": [{"role": "blueprint", "page_id": handoff["page_id"], "file_id": "native-output",
                                  "provenance": {"source_type": "host_generated", "tool": "image_gen"},
                                  "limitations": ["Synthetic protocol verification; no customer or professional acceptance."]}]}
    save(out / "result-envelope.json", result)
    accepted = cli(out, "accept", "task", "accept", "--project", project, "--task-id", handoff["task_id"],
                   "--operation-id", handoff["operation_id"], "--produced-against", handoff["produced_against"], "--result", out / "result-envelope.json")
    lineage = cli(out, "lineage", "view", "--project", project, "--page-id", handoff["page_id"], "--lineage",
                  "--revision", accepted["revision_id"])
    record = lineage["generation"]["adopted_observation"]
    request = lineage["generation"]["requests"][0]
    assert sha256_bytes(canonical_json_bytes(request["input"])) == request["input_hash"] == handoff["input_hash"]
    assert record["submitted"]["prompt"] == request["input"]["prompt"]
    assert record["output"]["sha256"] == sha256_bytes(raw) == lineage["stages"]["blueprint"]["file"]["sha256"]
    assert len(lineage["generation"]["attempts"]) == 1
    assert lineage["generation"]["attempts"][0]["call"]["state"] == "consumed"
    status = cli(out, "task-status", "task", "status", "--project", project, "--task-id", handoff["task_id"])
    assert len(status["pending_tasks"][0]["call_allowances"]) == 1
    (out / "native-output.png").write_bytes(raw)
    compared = generation.comparison(request, record)
    checks = {"status": "passed", "synthetic_content": True, "real_host_call": True,
              "input_hash": handoff["input_hash"], "output_sha256": sha256_bytes(raw),
              "request_id": handoff["request_id"], "attempt_id": handoff["attempt_id"], "invocation_ref": args.item_id,
              "adopted_revision": accepted["revision_id"], "allowance_count": 1, "consumed_count": 1,
              "observer": "tool_observed", "coverage": record["coverage"],
              "full_actual_input_match": compared,
              "W02_AC07": "real_requested_input_output_binding_verified" if compared["status"] == "match"
              else "partial: real prompt/output binding verified; complete submitted-input coverage remains open",
              "provider_model_and_seed": "unknown; not requested or independently observed"}
    save(out / "checks.json", checks)
    print(json.dumps(checks, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--out", type=Path, required=True)
    prep.add_argument("--thread-id", required=True)
    prep.add_argument("--turn-id", required=True)
    finish = commands.add_parser("complete")
    finish.add_argument("--out", type=Path, required=True)
    finish.add_argument("--item-id", required=True)
    args = parser.parse_args()
    (prepare if args.command == "prepare" else complete)(args)


if __name__ == "__main__":
    main()
