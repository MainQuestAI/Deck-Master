#!/usr/bin/env python3
"""Validate this offline Spec pack; never execute product code or mark an AC PASS."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

BASELINE = "a08bc68c1cbbbc806205104c2bb01f3f096305f0"
AC_ROW = re.compile(r"^\|\s*(?:\*\*)?(AC-N[1-6]-\d{2})")
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
FENCE = re.compile(r"^\s*(" + chr(96) + r"{3,}|~{3,})(.*)$")
BLOB = re.compile(
    r"^https://github\.com/MainQuestAI/Deck-Master/blob/([a-f0-9]{40})/([^#?]+)"
    r"(?:#L(\d+)(?:-L(\d+))?)?$"
)
REQUIRED = [
    "README.md", "01-ITERATION-PLAN.md", "02-BASELINE-AND-DECISIONS.md",
    "03-ARCHITECTURE-AND-COMPATIBILITY.md", "04-EXECUTION-PLAN.md",
    "05-ACCEPTANCE.md", "06-CODEX-HANDOFF.md", "traceability.json",
    "templates/execution-ledger.json", "templates/quality-observation.json",
    "tools/validate_spec.py", "VALIDATION.md",
]
EXPECTED_COUNTS = {"N1": 12, "N2": 12, "N3": 12, "N4": 14, "N5": 10, "N6": 10}


def slug(value: str) -> str:
    value = value.replace(chr(96), "").lower()
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = "".join(
        c for c in value
        if c in "-_ " or unicodedata.category(c)[0] in "LN"
    )
    return value.strip().replace(" ", "-")


def markdown(path: Path, errors: list[str], root: Path) -> tuple[str, list[tuple[int, str]], set[str]]:
    text = path.read_text(encoding="utf-8")
    visible = []
    links = []
    anchors = set()
    headings = Counter()
    marker = None
    marker_size = 0
    code_language = ""
    code = []
    table_width = None
    relative = str(path.relative_to(root))
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if marker:
            if match and match[1][0] == marker and len(match[1]) >= marker_size:
                if code_language == "json":
                    try:
                        json.loads("\n".join(code))
                    except json.JSONDecodeError as exc:
                        errors.append(f"{relative}:{number}: invalid fenced JSON: {exc.msg}")
                marker = None
                code = []
                table_width = None
            else:
                code.append(line)
            continue
        if match:
            marker, marker_size = match[1][0], len(match[1])
            code_language = match[2].strip().lower()
            code = []
            continue
        visible.append(line)
        for target in LINK.findall(line):
            links.append((number, target))
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            base = slug(heading[1])
            suffix = headings[base]
            anchors.add(base if not suffix else f"{base}-{suffix}")
            headings[base] += 1
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            columns = len(re.split(r"(?<!\\)\|", stripped)) - 2
            if table_width is None:
                table_width = columns
            elif columns != table_width:
                errors.append(f"{relative}:{number}: table has {columns} cells, expected {table_width}")
        else:
            table_width = None
    if marker:
        errors.append(f"{relative}: unclosed code fence")
    return "\n".join(visible), links, anchors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repo", type=Path, help="Optional read-only clone at the fixed baseline")
    parser.add_argument("--output-json", type=Path, help="Write the actual validation result")
    parser.add_argument("--check-hashes", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = []
    checks = []
    for name in REQUIRED:
        if not (root / name).is_file():
            errors.append(f"missing required file: {name}")
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    json_files = sorted(root.rglob("*.json"))
    parsed = {}
    for path in json_files:
        try:
            parsed[str(path.relative_to(root))] = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            errors.append(f"{path.relative_to(root)}: invalid JSON: {exc}")
    trace = parsed.get("traceability.json", {})
    ledger = parsed.get("templates/execution-ledger.json", {})
    observation = parsed.get("templates/quality-observation.json", {})
    if trace.get("baseline_sha") != BASELINE:
        errors.append("traceability baseline differs from the frozen SHA")
    if trace.get("implementation_status") != "NOT_RUN":
        errors.append("Spec traceability must not claim implementation completion")
    tasks = trace.get("tasks", [])
    task_map = {task["id"]: task for task in tasks}
    if set(task_map) != set(EXPECTED_COUNTS) or len(tasks) != 6:
        errors.append("task set must be exactly N1 through N6")
    rows = []
    for owner, task in task_map.items():
        card = root / task["task_card"]
        if not card.is_file():
            errors.append(f"missing card for {owner}")
            continue
        found = [m[1] for line in card.read_text(encoding="utf-8").splitlines()
                 if (m := AC_ROW.match(line))]
        expected = [f"AC-{owner}-{i:02d}" for i in range(1, EXPECTED_COUNTS[owner] + 1)]
        if found != expected:
            errors.append(f"{owner}: AC rows are missing, duplicated or out of order")
        rows.extend((ac, owner, task["task_card"]) for ac in found)
        if task.get("final_owner") != owner:
            errors.append(f"{owner}: final_owner mismatch")
        for dependency in task.get("depends_on", []):
            if dependency not in task_map or dependency == owner:
                errors.append(f"{owner}: invalid dependency {dependency}")
    visiting, visited = set(), set()

    def visit(owner: str) -> None:
        if owner in visiting:
            errors.append(f"dependency cycle at {owner}")
            return
        if owner in visited:
            return
        visiting.add(owner)
        for parent in task_map.get(owner, {}).get("depends_on", []):
            if parent in task_map:
                visit(parent)
        visiting.remove(owner)
        visited.add(owner)

    for owner in task_map:
        visit(owner)
    expected_rows = Counter(rows)
    index_rows = Counter((ac["id"], ac["owner"], ac["criterion_file"])
                         for ac in trace.get("acceptance", []))
    if expected_rows != index_rows or len(rows) != 70:
        errors.append("AC criteria and traceability must match exactly with 70 unique rows")
    for ac in trace.get("acceptance", []):
        if ac.get("test_plan") != ac.get("owner") or not ac.get("verification_topic"):
            errors.append(f"{ac.get('id')}: missing test plan or topic")
    ac_records = ledger.get("acceptance", [])
    if Counter((ac["ac_id"], ac["owner"]) for ac in ac_records) != Counter((a, o) for a, o, _ in rows):
        errors.append("ledger AC/owner set differs from task cards")
    for ac in ac_records:
        if ac.get("status") != "NOT_RUN" or ac.get("evidence") or ac.get("candidate_sha") is not None:
            errors.append(f"{ac.get('ac_id')}: template contains actual execution claims")
    if ledger.get("status") != "NOT_RUN" or ledger.get("is_runtime_state") is not False:
        errors.append("ledger must be an unexecuted offline template")
    if observation.get("status") != "NOT_RUN" or observation.get("is_runtime_state") is not False:
        errors.append("quality observation must be an unexecuted offline template")

    md_data = {}
    for path in sorted(root.rglob("*.md")):
        md_data[path.resolve()] = markdown(path, errors, root)
    local_links = set()
    source_links = set()
    for path, (_, links, _) in md_data.items():
        for number, target in links:
            blob = BLOB.match(target)
            if blob:
                source_links.add(target)
            parsed_url = urlparse(target)
            if parsed_url.scheme or target.startswith("//"):
                continue
            target_path, _, anchor = target.partition("#")
            destination = (path.parent / unquote(target_path)).resolve() if target_path else path
            local_links.add((str(path.relative_to(root)), target))
            if destination != root and root not in destination.parents:
                errors.append(f"{path.relative_to(root)}:{number}: local link escapes package: {target}")
                continue
            if not destination.exists():
                errors.append(f"{path.relative_to(root)}:{number}: broken local link: {target}")
            elif anchor and destination.suffix == ".md":
                anchors = md_data.get(destination, ("", [], set()))[2]
                if unquote(anchor) not in anchors:
                    errors.append(f"{path.relative_to(root)}:{number}: missing heading anchor: {target}")

    verified_source_links = 0
    verified_test_paths = 0
    if args.repo:
        repo = args.repo.resolve()
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=False)
        if result.returncode or result.stdout.strip() != BASELINE:
            errors.append("optional source clone is not at the frozen baseline")
        else:
            for link in sorted(source_links):
                match = BLOB.match(link)
                if not match or match[1] != BASELINE:
                    errors.append(f"source link has unexpected baseline: {link}")
                    continue
                source = repo / unquote(match[2])
                if not source.is_file():
                    errors.append(f"missing cited baseline source: {match[2]}")
                    continue
                if match[3]:
                    count = len(source.read_text(encoding="utf-8").splitlines())
                    start, end = int(match[3]), int(match[4] or match[3])
                    if not 1 <= start <= end <= count:
                        errors.append(f"source line anchor outside file: {link}")
                        continue
                verified_source_links += 1
            for task in tasks:
                for test in task.get("test_targets", []):
                    if test.startswith("tests/"):
                        if not (repo / test).is_file():
                            errors.append(f"planned existing test path missing: {test}")
                        else:
                            verified_test_paths += 1

    hash_count = 0
    if args.check_hashes:
        manifest = root / "manifest.sha256"
        if not manifest.is_file():
            errors.append("manifest.sha256 missing")
        else:
            for line in manifest.read_text(encoding="utf-8").splitlines():
                digest, separator, name = line.partition("  ")
                target = (root / name).resolve()
                if not separator or root not in target.parents or not target.is_file():
                    errors.append(f"invalid hash manifest entry: {line}")
                    continue
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    errors.append(f"hash mismatch: {name}")
                hash_count += 1

    checks.extend([
        "required files and JSON syntax",
        "70 unique AC criteria and one final owner per AC",
        "traceability and unexecuted ledger coverage",
        "valid task dependencies without cycles",
        "Markdown tables, fences, JSON examples and internal heading links",
    ])
    if args.repo:
        checks.append("fixed-baseline citation paths, line bounds and existing test paths")
    if args.check_hashes:
        checks.append("package file hashes")
    report = {
        "status": "FAIL" if errors else "PASS",
        "scope": "Spec package only; no product implementation or AC execution",
        "baseline_sha": BASELINE,
        "task_cards": len(tasks),
        "acceptance_count": len(rows),
        "product_ac_status": "70 NOT_RUN",
        "markdown_files": len(md_data),
        "json_files": len(json_files),
        "internal_links": len(local_links),
        "verified_baseline_source_links": verified_source_links,
        "verified_existing_test_paths": verified_test_paths,
        "hash_entries": hash_count,
        "checks": checks,
        "errors": errors,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

