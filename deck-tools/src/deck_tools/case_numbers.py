#!/usr/bin/env python3
"""Check explicit arithmetic; never infer business validity.

Usage: python -m deck_tools.case_numbers input.json
Exit: 0 all agree, 1 arithmetic mismatch, 2 invalid input.
Read-only, standard-library only; no eval, network or project writes.
Not a save or export gate.
"""
from __future__ import annotations
import argparse
import json
import sys
from decimal import Decimal, Inexact, InvalidOperation, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from typing import Any

ALLOWED = {"add", "subtract", "multiply", "divide", "percent_change", "share_pct"}


def decimal_value(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{label}: expected decimal string or JSON number, not bool")
    try:
        out = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label}: invalid decimal") from exc
    if not out.is_finite():
        raise ValueError(f"{label}: finite number required")
    return out


def evaluate(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema_version") != "case-arithmetic.v1":
        raise ValueError("expected schema_version=case-arithmetic.v1")
    values, checks = document.get("values"), document.get("checks")
    if not isinstance(values, dict):
        raise ValueError("values must be an object")
    if not isinstance(checks, list) or len(checks) < 1:
        raise ValueError("checks must contain at least one check")
    numbers = {key: decimal_value(value, f"values.{key}") for key, value in values.items()}
    output, seen = [], set()
    for row in checks:
        if not isinstance(row, dict):
            raise ValueError("check must be an object")
        cid = row.get("id")
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            raise ValueError("check id must be nonempty and unique")
        seen.add(cid)
        op, refs = row.get("operator"), row.get("operands")
        if not isinstance(op, str) or op not in ALLOWED:
            raise ValueError(f"{cid}: unknown operator")
        if not isinstance(refs, list) or len(refs) < 1:
            raise ValueError(f"{cid}: operands must name value keys")
        if any(not isinstance(key, str) or key not in numbers for key in refs):
            raise ValueError(f"{cid}: missing or invalid operand reference")
        if op not in {"add", "multiply"} and len(refs) != 2:
            raise ValueError(f"{cid}: {op} needs exactly two operands")
        args = [numbers[key] for key in refs]
        rounded_division = False
        if op == "add":
            result = sum(args, Decimal(0))
        elif op == "multiply":
            result = Decimal(1)
            for operand in args:
                result *= operand
        elif op == "subtract":
            result = args[0] - args[1]
        else:
            denominator = args[0] if op == "percent_change" else args[1]
            if denominator == 0:
                raise ValueError(f"{cid}: zero denominator")
            numerator = (args[1] - args[0]) * 100 if op == "percent_change" else args[0]
            if op == "share_pct":
                numerator *= 100
            # Division is the only rounded operator: 40 significant digits,
            # half-even. An inexact quotient needs an explicit positive tolerance.
            with localcontext() as division:
                division.prec = 40
                division.rounding = ROUND_HALF_EVEN
                division.clear_flags()
                result = numerator / denominator
                rounded_division = division.flags[Inexact]
        if "expected" not in row:
            raise ValueError(f"{cid}: expected is required")
        expected = decimal_value(row["expected"], f"{cid}.expected")
        tolerance = decimal_value(row.get("tolerance", "0"), f"{cid}.tolerance")
        if tolerance < 0:
            raise ValueError(f"{cid}: tolerance must be nonnegative")
        if rounded_division and tolerance == 0:
            raise ValueError(f"{cid}: rounded division requires positive tolerance")
        difference = abs(result - expected)
        output.append({"id": cid, "operator": op, "operand_keys": refs,
                       "operand_values": list(map(str, args)), "result": str(result),
                       "expected": str(expected), "absolute_difference": str(difference),
                       "tolerance": str(tolerance), "pass": difference <= tolerance,
                       "rounded_division": rounded_division})
    return {"schema_version": "case-arithmetic-result.v1", "scope": document.get("scope", ""),
            "all_passed": all(item["pass"] for item in output), "checks": output,
            "division_rule": "40 significant digits, ROUND_HALF_EVEN; inexact division requires positive tolerance; comparison uses rounded quotient.",
            "limitation": "Arithmetic only; not a save or export gate, and not source truth, denominator suitability, causality, ROI or product validation."}


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        doc = json.loads(raw.decode("utf-8"), parse_float=Decimal, object_pairs_hook=no_duplicate_keys)
        result = evaluate(doc)
    except (OSError, UnicodeError, ValueError, InvalidOperation) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
