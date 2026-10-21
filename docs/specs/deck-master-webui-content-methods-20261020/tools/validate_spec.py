"""Validate this planning bundle only; never executes product code or tasks."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    trace = json.loads((ROOT / "traceability.json").read_text())
    baseline = json.loads((ROOT / "baseline.json").read_text())
    tasks = trace["tasks"]
    criteria = trace["acceptance"]
    by_task = {row["id"]: row for row in tasks}
    by_ac = {row["id"]: row for row in criteria}
    assert len(tasks) == len(by_task) == 9
    assert len(criteria) == len(by_ac) == 50
    assert set(by_task) == {f"WU{i:02d}" for i in range(9)}
    assert set(by_ac) == {f"AC{i:02d}" for i in range(1, 51)}
    claimed = []
    visited = set()
    active = set()

    def visit(task_id):
        assert task_id in by_task
        assert task_id not in active, f"dependency cycle: {task_id}"
        if task_id in visited:
            return
        active.add(task_id)
        for dependency in by_task[task_id]["depends_on"]:
            visit(dependency)
        active.remove(task_id)
        visited.add(task_id)

    for task in tasks:
        visit(task["id"])
        assert task["status"] == "NOT_STARTED"
        for ac_id in task["acceptance_ids"]:
            assert by_ac[ac_id]["owner"] == task["id"]
            claimed.append(ac_id)
    assert len(claimed) == len(set(claimed)) == len(criteria)
    assert set(claimed) == set(by_ac)
    assert set(trace["features"]) == {f"UI-{i:02d}" for i in range(1, 8)}
    assert all(set(owners) <= set(by_task) and owners
               for owners in trace["features"].values())
    assert all(row["status"] == "NOT_RUN" and not row["evidence"]
               for row in criteria)
    assert baseline["implementation_base"] is None
    source = ROOT / baseline["source_report_snapshot"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == baseline["source_report_sha256"]

    acceptance = (ROOT / "ACCEPTANCE.md").read_text()
    cards = (ROOT / "TASKS.md").read_text()
    for row in criteria:
        assert acceptance.count(f'| {row["id"]} | {row["owner"]} |') == 1
    for task in tasks:
        assert f'## {task["id"]}｜' in cards

    checked_links = 0
    for path in ROOT.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            target = target.strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("/"):
                continue
            # validation.json is this check's output, not a missing input.
            if target == "validation.json":
                continue
            assert (path.parent / target).exists(), f"{path.name}: {target}"
            checked_links += 1
    checks = {
        "schema_version": "spec_validation.v1",
        "scope": "documentation_only",
        "status": "PASS",
        "task_count": len(tasks),
        "acceptance_count": len(criteria),
        "feature_count": len(trace["features"]),
        "unique_acceptance_owners": True,
        "dependency_graph_acyclic": True,
        "source_report_hash_matches": True,
        "relative_links_checked": checked_links,
        "product_tests": "NOT_RUN",
        "browser_tests": "NOT_RUN",
        "installed_tests": "NOT_RUN",
        "actual_host_tests": "NOT_RUN",
        "human_acceptance": "NOT_RUN",
    }
    (ROOT / "validation.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
