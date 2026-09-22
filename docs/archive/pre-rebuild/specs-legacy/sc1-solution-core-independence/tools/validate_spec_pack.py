#!/usr/bin/env python3
"""Validate this development SPEC PACK, not the Deck Master implementation.

Checks target schemas, seven synthetic samples, selected semantic counterexamples,
and the planned acceptance ledger. It does not call models, install backends,
run the repository tests, or claim product/UAT readiness.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
except ImportError as exc:
    raise SystemExit("Requires jsonschema (already a Deck Master dependency); install in your approved environment.") from exc

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
DIMS = {
    "customer_specificity", "solution_validity", "evidence_quality",
    "decision_logic", "implementation_specificity", "expression_quality",
}
PAIRS = {
    "plan": ("capability-execution-plan.v1.schema.json", "capability_execution_plan.json"),
    "context": ("context-pack.v2.schema.json", "context_pack.json"),
    "research": ("research-task.v1.schema.json", "research_task.json"),
    "model": ("solution-model.v1.schema.json", "solution_model.json"),
    "view": ("diagram-view.v1.schema.json", "diagram_view.json"),
    "review": ("external-quality-review.v2.schema.json", "external_quality_review.json"),
    "narrative": ("narrative-plan.v3.schema.json", "narrative_plan.json"),
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path.name}")
    return value


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_sample_path(ref: str) -> Path:
    raw = Path(ref)
    require(not raw.is_absolute() and ".." not in raw.parts, "unsafe sample reference")
    target = (EXAMPLES / raw).resolve()
    require(target.is_relative_to(EXAMPLES.resolve()), "reference escapes samples")
    require(target.is_file(), f"missing sample file: {ref}")
    return target


def common(payload: dict[str, Any]) -> None:
    require(payload["run_id"] == "synthetic_sc1", "cross-run result in sample")
    require(payload["run_mode"] == "fixture", "sample must not pretend to be production")
    refs = payload["based_on"]["input_refs"]
    for ref in refs:
        require(digest(safe_sample_path(ref["ref"]).read_bytes()) == ref["sha256"], "stale sample input hash")
    canonical = json.dumps(refs, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    require(digest(canonical) == payload["based_on"]["input_fingerprint"], "sample input fingerprint mismatch")


def evidence_ids(ctx: dict[str, Any]) -> set[str]:
    return {f"{s['source_id']}#{e['evidence_id']}" for s in ctx["sources"] for e in s["evidence_candidates"]}


def validate_context(ctx: dict[str, Any]) -> None:
    sids = [s["source_id"] for s in ctx["sources"]]
    require(len(sids) == len(set(sids)), "duplicate source id")
    for source in ctx["sources"]:
        content = safe_sample_path(source["origin_ref"]).read_bytes()
        require(digest(content) == source["file_sha256"], "source hash mismatch")
        ex = source["extraction"]
        require(ex["read_units"] <= ex["total_units"], "read coverage exceeds total")
        if ex["status"] == "complete":
            require(ex["read_units"] == ex["total_units"] and not ex["unread_regions"], "false complete extraction")
        evs = [e["evidence_id"] for e in source["evidence_candidates"]]
        require(len(evs) == len(set(evs)), "duplicate evidence id within source")
        for ev in source["evidence_candidates"]:
            pos = ev["source_position"]
            require(pos["end"] >= pos["start"], "reversed source range")
            require(digest(ev["quote"]) == ev["quote_sha256"], "quote hash mismatch")
            if pos["unit_type"] == "line":
                lines = content.decode("utf-8").splitlines()
                require(1 <= pos["start"] <= pos["end"] <= len(lines), "line range out of bounds")
                quoted = "\n".join(lines[pos["start"] - 1:pos["end"]])
                require(quoted == ev["quote"], "quote does not match actual source lines")
    for conflict in ctx["conflicts"]:
        require(set(conflict["evidence_refs"]) <= evidence_ids(ctx), "conflict evidence not found")


def model_nodes(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {obj["id"]: obj for group in ("problems", "capabilities", "components", "implementation_phases") for obj in model[group]}


def validate_model(model: dict[str, Any], ctx: dict[str, Any]) -> None:
    all_lists = [model[k] for k in ("problems", "capabilities", "components", "relations", "implementation_phases", "alternatives", "assumptions")]
    ids = [x["id"] for group in all_lists for x in group]
    require(len(ids) == len(set(ids)), "duplicate model id")
    nodes = model_nodes(model)
    evidence = evidence_ids(ctx)
    problems = {x["id"] for x in model["problems"]}
    components = {x["id"] for x in model["components"]}
    for group in (model["problems"], model["components"], model["relations"]):
        for row in group:
            require(set(row["evidence_refs"]) <= evidence, "unresolvable evidence key")
    for cap in model["capabilities"]:
        require(set(cap["problem_refs"]) <= problems, "capability references unknown problem")
    for relation in model["relations"]:
        require(relation["from_id"] in nodes and relation["to_id"] in nodes, "dangling model relation")
    phases = {p["id"]: p for p in model["implementation_phases"]}
    for phase in phases.values():
        require(set(phase["component_refs"]) <= components, "phase references unknown component")
        require(set(phase["depends_on"]) <= set(phases), "phase depends on unknown phase")
    visiting: set[str] = set()
    done: set[str] = set()
    def visit(pid: str) -> None:
        require(pid not in visiting, "cyclic implementation dependency")
        if pid in done:
            return
        visiting.add(pid)
        for parent in phases[pid]["depends_on"]:
            visit(parent)
        visiting.remove(pid)
        done.add(pid)
    for pid in phases:
        visit(pid)
    require(model["recommended_alternative_id"] in {a["id"] for a in model["alternatives"]}, "unknown recommended alternative")
    if len(model["alternatives"]) == 1:
        require(bool(model["single_viable_reason"].strip()), "single alternative requires rationale")


def validate_view(view: dict[str, Any], model: dict[str, Any]) -> None:
    require(digest(safe_sample_path(view["model_ref"]).read_bytes()) == view["model_sha256"], "stale model hash")
    models = model_nodes(model)
    nodes = {x["id"]: x for x in view["nodes"]}
    require(len(nodes) == len(view["nodes"]), "duplicate view node")
    relations = {x["id"]: x for x in model["relations"]}
    for node in nodes.values():
        require(set(node["model_refs"]) <= set(models), "view references unknown model node")
        if len(node["model_refs"]) > 1:
            require(bool(node["aggregation_reason"].strip()), "aggregation requires explanation")
    for edge in view["edges"]:
        require(edge["from_node_id"] in nodes and edge["to_node_id"] in nodes, "unknown view endpoint")
        require(edge["relation_ref"] in relations, "unknown model relation")
        relation = relations[edge["relation_ref"]]
        require(relation["from_id"] in nodes[edge["from_node_id"]]["model_refs"] and relation["to_id"] in nodes[edge["to_node_id"]]["model_refs"], "view/model direction mismatch")


def validate_review(review: dict[str, Any]) -> None:
    required = set(review["coverage"]["required_page_ids"])
    reviewed = set(review["coverage"]["reviewed_page_ids"])
    require(required <= reviewed and not review["coverage"]["skipped"], "review coverage incomplete")
    require({o["dimension"] for o in review["observations"]} >= DIMS, "missing review dimension")
    for ref in review["reviewed_inputs"]:
        require(digest(safe_sample_path(ref["ref"]).read_bytes()) == ref["sha256"], "review bound to stale input")
    if review["review_kind"] == "independent":
        require(review["reviewer_session_id"] != review["producer_session_id"], "same session cannot be an independent review")
    if any(f["severity"] in {"P0", "P1"} for f in review["findings"]):
        require(review["summary"]["reported_status"] == "rework_required", "summary cannot erase blocker")


def validate_plan(plan: dict[str, Any]) -> None:
    expected = all(c["status"] == "verified" for c in plan["capabilities"] if c["required"]) and not plan["blockers"]
    require(plan["task_ready"] is expected, "false task readiness")
    if plan["library_mode"] == "none":
        require(not any(c["required"] for c in plan["capabilities"] if c["capability_id"] == "historical-corpus"), "none must not require corpus")


def validate_narrative(narr: dict[str, Any], model: dict[str, Any], ctx: dict[str, Any]) -> None:
    require(digest(safe_sample_path(narr["solution_ref"]).read_bytes()) == narr["solution_sha256"], "stale solution model hash")
    cand_ids = [c["id"] for c in narr["candidates"]]
    require(len(cand_ids) == len(set(cand_ids)), "duplicate narrative candidate id")
    require(narr["recommended_candidate_id"] in cand_ids, "unknown recommended candidate")
    selected = narr["selected_candidate_id"]
    if selected is not None:
        require(selected in cand_ids, "unknown selected candidate")
    evidence = evidence_ids(ctx)
    for cand in narr["candidates"]:
        require(set(cand["evidence_refs"]) <= evidence, "candidate evidence not found")
    issues = {i["id"] for i in narr["issue_tree"]}
    require(len(issues) == len(narr["issue_tree"]), "duplicate issue id")
    for issue in narr["issue_tree"]:
        parent = issue.get("parent_id")
        if parent:
            require(parent in issues, "issue parent not found")
    by_issue = {i["id"]: i for i in narr["issue_tree"]}
    visiting: set[str] = set()
    done: set[str] = set()

    def visit_issue(iid: str) -> None:
        require(iid not in visiting, "cyclic issue dependency")
        if iid in done:
            return
        visiting.add(iid)
        parent = by_issue[iid].get("parent_id")
        if parent:
            visit_issue(parent)
        visiting.remove(iid)
        done.add(iid)

    for iid in issues:
        visit_issue(iid)
    beat_ids = {b["beat_id"] for b in narr["beats"]}
    require(len(beat_ids) == len(narr["beats"]), "duplicate beat id")
    resolvable = set(model_nodes(model)) | {x["id"] for x in model["relations"]} | {x["id"] for x in model["alternatives"]} | {x["id"] for x in model["assumptions"]}
    components = {c["id"] for c in model["components"]}
    for beat in narr["beats"]:
        require(set(beat["dependencies"]) <= beat_ids, "unknown beat dependency")
        require(set(beat["evidence_refs"]) <= evidence, "beat evidence not found")
        require(set(beat["solution_refs"]) <= resolvable, "beat references unknown solution object")
        require(set(beat["required_components"]) <= components, "beat references unknown component")
    by_beat = {b["beat_id"]: b for b in narr["beats"]}
    visiting.clear()
    done.clear()

    def visit_beat(bid: str) -> None:
        require(bid not in visiting, "cyclic beat dependency")
        if bid in done:
            return
        visiting.add(bid)
        for dep in by_beat[bid]["dependencies"]:
            visit_beat(dep)
        visiting.remove(bid)
        done.add(bid)

    for bid in beat_ids:
        visit_beat(bid)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Optional local output file for SPEC PACK validation results")
    args = parser.parse_args()
    data = {name: load(EXAMPLES / sample) for name, (_, sample) in PAIRS.items()}
    validators = {}
    for name, (schema_file, _) in PAIRS.items():
        definition = load(ROOT / "contracts" / schema_file)
        Draft202012Validator.check_schema(definition)
        validators[name] = Draft202012Validator(definition)

    def check(name: str, value: dict[str, Any]) -> None:
        validators[name].validate(value)
        common(value)
        if name == "context": validate_context(value)
        elif name == "model": validate_model(value, data["context"])
        elif name == "view": validate_view(value, data["model"])
        elif name == "review": validate_review(value)
        elif name == "plan": validate_plan(value)
        elif name == "narrative": validate_narrative(value, data["model"], data["context"])

    for name, sample in data.items():
        check(name, sample)

    negative: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = [
        ("wrong_boolean_type", "plan", lambda p: p.__setitem__("task_ready", "yes")),
        ("false_task_ready", "plan", lambda p: p.__setitem__("task_ready", True)),
        ("duplicate_source", "context", lambda p: p["sources"].append(copy.deepcopy(p["sources"][0]))),
        ("supported_without_review", "context", lambda p: p["sources"][0]["evidence_candidates"][0].__setitem__("review_status", "supported")),
        ("quote_tampering", "context", lambda p: p["sources"][0]["evidence_candidates"][0].__setitem__("quote", "not in source")),
        ("false_complete_read", "context", lambda p: p["sources"][0]["extraction"].__setitem__("read_units", 1)),
        ("zero_research_budget", "research", lambda p: p["limits"].__setitem__("max_rounds_per_question", 0)),
        ("existing_without_evidence", "model", lambda p: p["components"][1].__setitem__("evidence_refs", [])),
        ("orphan_problem_ref", "model", lambda p: p["capabilities"][0].__setitem__("problem_refs", ["UNKNOWN"])),
        ("dangling_model_relation", "model", lambda p: p["relations"][0].__setitem__("to_id", "UNKNOWN")),
        ("cyclic_phase_dependency", "model", lambda p: p["implementation_phases"][0].__setitem__("depends_on", ["PHASE-01"])),
        ("view_direction_mismatch", "view", lambda p: p["edges"][0].update({"from_node_id": "NODE-02", "to_node_id": "NODE-01"})),
        ("stale_model_hash", "view", lambda p: p.__setitem__("model_sha256", "0" * 64)),
        ("empty_review_observations", "review", lambda p: p.__setitem__("observations", [])),
        ("summary_hides_blocker", "review", lambda p: p["summary"].__setitem__("reported_status", "pass")),
        ("same_independent_session", "review", lambda p: p.__setitem__("reviewer_session_id", p["producer_session_id"])),
        ("unsafe_input_path", "research", lambda p: p["based_on"]["input_refs"][0].__setitem__("ref", "../outside.json")),
        ("stale_action_input", "plan", lambda p: p["based_on"]["input_refs"][0].__setitem__("sha256", "0" * 64)),
        ("narrative_stale_model_hash", "narrative", lambda p: p.__setitem__("solution_sha256", "0" * 64)),
        ("narrative_unknown_selected_candidate", "narrative", lambda p: p.__setitem__("selected_candidate_id", "UNKNOWN")),
        ("cyclic_beat_dependency", "narrative", lambda p: p["beats"][0].__setitem__("dependencies", ["P002"])),
    ]
    rejected = []
    for case_id, name, mutate in negative:
        value = copy.deepcopy(data[name])
        mutate(value)
        try:
            check(name, value)
        except (ValueError, ValidationError) as exc:
            # ValidationError is third-party; retaining its name makes rejection evidence explicit.
            rejected.append({"id": case_id, "rejected_by": type(exc).__name__})
        else:
            raise AssertionError(f"Counterexample was not rejected: {case_id}")

    cases = load(ROOT / "acceptance" / "cases.json")["cases"]
    require(len({c["id"] for c in cases}) == len(cases), "duplicate acceptance ID")
    require(all(c["status"] == "not_run" for c in cases), "spec pack must not claim product acceptance execution")
    report = {
        "scope": "spec_pack_only_not_product_tests",
        "schemas_validated": len(validators),
        "synthetic_positive_samples_passed": len(data),
        "selected_counterexamples_rejected": len(rejected),
        "counterexamples": rejected,
        "planned_product_acceptance_cases": len(cases),
        "product_tests_executed": False,
        "real_uat_executed": False,
        "status": "passed",
        "limitations": [
            "Structural/sample consistency checks do not prove current repository support.",
            "Distinct reviewer IDs do not prove real independent host execution.",
            "This script does not verify real provider receipts or objective factual support.",
        ],
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
