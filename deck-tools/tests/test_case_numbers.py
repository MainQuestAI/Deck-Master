"""File-level arithmetic helper: explicit checks, errors, and no writes."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
CASES = REPO / "deck-skill" / "assets" / "content" / "examples"
NUMBERS = (
    "E01-marketing/numbers.json",
    "E02-technical-choice/numbers.json",
    "E03-policy-training/numbers.json",
    "E04-saas-retention/numbers.json",
)


def run_helper(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "deck_tools.case_numbers", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_synthetic_case_files_recalculate(tmp_path: Path) -> None:
    del tmp_path
    for relative in NUMBERS:
        path = CASES / relative
        before = path.read_bytes()
        result = run_helper(path)
        assert result.returncode == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["all_passed"] is True
        assert path.read_bytes() == before


def test_wrong_expected_value_fails_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "numbers.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "case-arithmetic.v1",
                "values": {"start": "10", "end": "12"},
                "checks": [
                    {
                        "id": "growth",
                        "operator": "percent_change",
                        "operands": ["start", "end"],
                        "expected": "999",
                        "tolerance": "0",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()
    result = run_helper(path)
    assert result.returncode == 1
    assert json.loads(result.stdout)["all_passed"] is False
    assert path.read_bytes() == before


def test_invalid_operator_returns_input_error(tmp_path: Path) -> None:
    path = tmp_path / "numbers.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "case-arithmetic.v1",
                "values": {"a": "1", "b": "2"},
                "checks": [
                    {
                        "id": "bad",
                        "operator": "eval",
                        "operands": ["a", "b"],
                        "expected": "3",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()
    result = run_helper(path)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "invalid_input"
    assert path.read_bytes() == before
