#!/usr/bin/env python3
"""Validate this specification package only; never runs Deck Master product tests."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    raise SystemExit("Spec validation requires jsonschema. Install it in a disposable environment; no product tests will be run.")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    schemas: dict[str, Any] = {}
    for path in sorted((root / "contracts").glob("*.schema.json")):
        try:
            payload = load(path)
            Draft202012Validator.check_schema(payload)
            schemas[path.name] = payload
        except Exception as exc:
            errors.append(f"Schema {path.name}: {exc}")
    positive = load(root / "examples" / "INDEX.json")["examples"]
    for item in positive:
        schema_path = (root / "examples" / item["schema"]).resolve()
        try:
            Draft202012Validator(load(schema_path), format_checker=FormatChecker()).validate(
                load(root / "examples" / item["file"])
            )
        except Exception as exc:
            errors.append(f"Example {item['file']}: {exc}")
    negative = load(root / "tools" / "schema_negative_cases.json")["cases"]
    for item in negative:
        validator = Draft202012Validator(load(root / item["schema"]), format_checker=FormatChecker())
        if not list(validator.iter_errors(item["payload"])):
            errors.append(f"Negative example unexpectedly accepted: {item['name']}")
    cases = load(root / "acceptance" / "cases.json")["cases"]
    ids = [item["id"] for item in cases]
    if len(ids) != len(set(ids)) or len(ids) != 64:
        errors.append("Acceptance IDs must be unique and have the expected 64 entries.")
    if any(item["status"] != "not_run" or item["actual_result"] is not None for item in cases):
        errors.append("Specification template must not claim executed product results.")
    mapping = load(root / "acceptance" / "SC1_SUPERSESSION_MAP.json")["entries"]
    if len(mapping) != 88 or len({item["sc1_id"] for item in mapping}) != 88:
        errors.append("SC-1 mapping must contain 88 unique original cases.")
    for item in mapping:
        if item["ndc_anchor"] and item["ndc_anchor"] not in ids:
            errors.append(f"Unknown NDC mapping anchor: {item['ndc_anchor']}")
        if item["verification_status"] != "unverified":
            errors.append(f"SC-1 case must not be automatically accepted: {item['sc1_id']}")
    source_ids = {item["id"] for item in load(root / "sources" / "index.json")["sources"]}
    link_count = 0
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for citation in re.findall(r"\[((?:R|L)\d{2})\]", text):
            if citation not in source_ids:
                errors.append(f"Unknown source ID in {path.name}: {citation}")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            target = match.group(1).split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "sandbox:", "provided:")):
                continue
            target_path = (path.parent / target).resolve()
            if not target_path.is_relative_to(root):
                errors.append(f"Link escapes package: {path.relative_to(root)} -> {target}")
            elif not target_path.exists():
                errors.append(f"Broken link: {path.relative_to(root)} -> {target}")
            link_count += 1
    return {
        "validation_scope": "specification structure only; no product tests or runtime probes executed",
        "status": "passed" if not errors else "failed",
        "schema_count": len(schemas),
        "synthetic_examples_validated": len(positive),
        "selected_schema_counterexamples_rejected": len(negative),
        "planned_product_cases": len(cases),
        "inherited_mapping_count": len(mapping),
        "local_markdown_links_checked": link_count,
        "product_test_status": "not_run",
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        report = validate(root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"status": "failed", "validation_scope": "specification only", "errors": [str(exc)]}
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
