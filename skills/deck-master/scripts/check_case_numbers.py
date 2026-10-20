#!/usr/bin/env python3
"""Check explicit arithmetic; never infer business validity.

Usage: python check_case_numbers.py input.json
Exit: 0 all agree, 1 arithmetic mismatch, 2 invalid input.
Read-only, standard-library only; no eval, network or project writes.
"""
from __future__ import annotations
import argparse
import json
import sys
from decimal import Decimal, Inexact, InvalidOperation, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from typing import Any

MAX_BYTES = 1_000_000
ALLOWED = {"add", "subtract", "multiply", "divide", "percent_change", "share_pct"}


def decimal_value(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{label}: expected decimal string or JSON number, not bool")
    raw = str(value)
    if len(raw) > 128:
        raise ValueError(f"{label}: number is too long")
    try:
        out = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{label}: invalid decimal") from exc
    if not out.is_finite() or abs(out.adjusted()) > 100:
        raise ValueError(f"{label}: finite number of bounded magnitude required")
    return out


def evaluate(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema_version") != "case-arithmetic.v1":
        raise ValueError("expected schema_version=case-arithmetic.v1")
    values, checks = document.get("values"), document.get("checks")
    if not isinstance(values, dict) or len(values) > 10000:
        raise ValueError("values must be an object of at most 10000 keys")
    if not isinstance(checks, list) or not 1 <= len(checks) <= 1000:
        raise ValueError("checks must contain 1..1000 checks")
    numbers = {key: decimal_value(value, f"values.{key}") for key, value in values.items()}
    output, seen = [], set()
    with localcontext() as ctx:
        # At most 100 operands, each <=128 characters and adjusted exponent
        # within +/-100: 26000 digits cover exact products and aligned sums,
        # including subtraction of the bounded expected value.
        ctx.prec = 26000
        ctx.rounding = ROUND_HALF_EVEN
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
            if not isinstance(refs, list) or not 1 <= len(refs) <= 100:
                raise ValueError(f"{cid}: operands must contain 1..100 value keys")
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
                # Only division rounds: 40 significant digits, half-even.
                # Rounded quotients require an explicit positive tolerance.
                with localcontext() as division:
                    division.prec = 40
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
            "limitation": "Arithmetic only; not source truth, denominator suitability, causality, ROI or product validation."}


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
        with args.input.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError(f"input exceeds {MAX_BYTES} bytes")
        doc = json.loads(raw.decode("utf-8"), parse_float=Decimal, object_pairs_hook=no_duplicate_keys)
        result = evaluate(doc)
    except (OSError, UnicodeError, ValueError, InvalidOperation) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
