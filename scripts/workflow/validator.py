"""Stage entry/exit validation against the Stage Contract registry.

Artifact paths declared by a contract's ``path_pattern`` are resolved relative
to the run directory. A pattern may be:

* a plain filename (``deck_brief.json``)
* a glob (``page_packages/*.json``)
* a directory marker (``page_packages/`` — present when the dir has ≥1 file)

Entry validation checks that the previous production stage has reached a
completed/accepted state and that the stage's ``entry.required_artifacts``
exist. Exit validation checks ``exit_criteria.required_artifacts`` and that
each required output declares at least one concrete file on disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skills.manifest import StageContract


def resolve_artifact_files(run_dir: Path, path_pattern: str) -> list[Path]:
    """Expand a contract ``path_pattern`` to concrete files under ``run_dir``."""
    pat = path_pattern.strip()
    if pat.endswith("/"):
        directory = run_dir / pat.rstrip("/")
        if not directory.is_dir():
            return []
        return [p for p in sorted(directory.rglob("*")) if p.is_file()]
    if "*" in pat or "?" in pat or "[" in pat:
        return sorted(p for p in (run_dir.glob(pat)) if p.is_file())
    candidate = run_dir / pat
    if candidate.is_file():
        return [candidate]
    return []


def artifact_present(run_dir: Path, path_pattern: str) -> bool:
    return bool(resolve_artifact_files(run_dir, path_pattern))


def required_outputs(contract: StageContract) -> list[dict[str, Any]]:
    return [o for o in contract.outputs if o.get("required")]


@dataclass(frozen=True)
class EntryReport:
    valid: bool
    missing: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExitReport:
    valid: bool
    missing: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def validate_entry(
    contract: StageContract,
    run_dir: Path,
    *,
    previous_completed: bool,
) -> EntryReport:
    missing: list[str] = []
    blockers: list[str] = []

    required_prev = contract.raw.get("allowed_previous_stages") or []
    if required_prev and not previous_completed:
        blockers.append(
            f"previous stage(s) not completed/accepted: {', '.join(required_prev)}"
        )

    for pattern in contract.entry.get("required_artifacts", []):
        # entry.required_artifacts may be path-like names; resolve as patterns
        if not artifact_present(run_dir, pattern):
            missing.append(pattern)

    # entry.required_decisions and transition approvals are facts produced by
    # the decision log (B1) and approval runtime (A4). A2 derives stage state
    # from artifacts only; decisions are surfaced in the stage view but do not
    # block artifact-based entry. A4 wires them in as hard gates.

    valid = not missing and not blockers
    return EntryReport(valid=valid, missing=missing, blockers=blockers)


def validate_exit(contract: StageContract, run_dir: Path) -> ExitReport:
    missing: list[str] = []
    invalid: list[str] = []
    blockers: list[str] = []

    exit_patterns = contract.exit_criteria.get("required_artifacts", [])
    for pattern in exit_patterns:
        files = resolve_artifact_files(run_dir, pattern)
        if not files:
            missing.append(pattern)

    # required outputs must each have at least one concrete file
    for out in required_outputs(contract):
        files = resolve_artifact_files(run_dir, out["path_pattern"])
        if not files:
            if out["path_pattern"] not in missing:
                missing.append(out["path_pattern"])

    for stop in contract.raw.get("stop_conditions", []):
        # stop conditions are advisory; resolver surfaces them as blockers only
        # when a concrete signal exists. A2 does not evaluate them automatically.
        pass

    valid = not missing and not invalid
    return ExitReport(valid=valid, missing=missing, invalid=invalid, blockers=blockers)
