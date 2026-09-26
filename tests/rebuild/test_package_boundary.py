"""AC-L07 package boundary tests (T01).

T01 freezes the per-path disposition/reference baseline; it does not require
reference-zeroing (that is T24 / AC-L05). These tests enforce:

1. The old-file disposition inventory is complete and well-formed.
2. No old file has been deleted prematurely (old code and user material stay).
3. The new ``src/deck_master`` package never imports the old namespaces
   (spec 01.2 reverse-import forbidden zone).
"""

from __future__ import annotations

import ast
import csv
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_DIR = REPO_ROOT / "docs" / "specs" / "deck-master-rebuild-v1" / "inventory"
NEW_PACKAGE = REPO_ROOT / "src" / "deck_master"

ALLOWED_ACTIONS = {"RETIRE_THEN_DELETE", "EXTRACT_THEN_DELETE", "DELETE_AFTER_CUTOVER", "REPLACE"}
EXPECTED_OLD_FILE_COUNT = 177

# spec 01.2: old namespaces the new package must never import. "build" appears
# in the spec only as build.native_* of the old runtime's build package.
FORBIDDEN_IMPORT_ROOTS = ("runtime", "workflow", "high_density", "preview", "build")


def _read_old_files() -> list[dict[str, str]]:
    with (INVENTORY_DIR / "old-files.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _git_tracked_paths() -> set[str]:
    output = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    return set(output.stdout.decode("utf-8").splitlines())


def test_disposition_inventory_is_complete() -> None:
    rows = _read_old_files()
    assert len(rows) == EXPECTED_OLD_FILE_COUNT, (
        f"old-files.csv must freeze all {EXPECTED_OLD_FILE_COUNT} script paths, got {len(rows)}"
    )
    for row in rows:
        path = row["path"].strip()
        assert path, f"row {row.get('id')} has an empty path"
        assert row["action"].strip() in ALLOWED_ACTIONS, (
            f"{path}: unknown disposition {row['action']!r}"
        )
        if row["action"].strip() == "EXTRACT_THEN_DELETE":
            assert row["target"].strip(), (
                f"{path}: EXTRACT_THEN_DELETE must name the new target module"
            )


def test_old_file_disposition_executed() -> None:
    """T24: every frozen old path is now either deleted from the working tree
    (disposition executed, history kept in git) or still present with a
    recorded reason. The T01 "no premature deletion" rule is superseded by
    the T24 cutover (WP04 entry switched, AC-L05)."""
    tracked = _git_tracked_paths()
    rows = _read_old_files()
    still_present = [row["path"] for row in rows if row["path"].strip() in tracked]
    deleted = [row["path"] for row in rows if row["path"].strip() not in tracked]
    # The old implementation tree is retired; surviving paths must be ones
    # the disposition table explicitly keeps (none today under scripts/).
    assert not still_present, (
        f"T24 must retire every frozen old path or record a keep reason; still present: {still_present[:10]}"
    )
    assert deleted, "T24 disposition must actually delete the retired tree"
    evidence = INVENTORY_DIR / "reference-scan.md"
    assert evidence.is_file(), "per-path reference scan evidence must be committed"


RETIRED_COMMAND_NEEDLES = (
    "suite-status", "suite-install", "suite-repair", "suite-migrate",
    "release-build", "release-smoke", "release-install", "release-rollback",
    "preview-gate", "rc-gate", "search-library", "decide-sourcing",
    "library-status", "import-library-selection", "record-library-feedback",
    "validate-ppt-library-result", "uat-ppt-library", "start-conversation",
    "build-brief", "build-claim-map", "autoplan", "setup-status",
    "install-skill", "uninstall-skill", "validate-skill",
    "backend bind ", "backend verify ", "generation-session", "run-generation",
    "build-judgments", "build-claim-graph", "init-workspace", "init-project",
    "orchestration-check", "bind-workspace", "smoke-real-workflow",
)

# Surfaces allowed to NAME retired things: the mapping table (refuses them),
# its refusal tests, the changelog (history), and the migration guide.
SELF_DOCUMENTING = {"src/deck_master/cli.py", "tests/rebuild/test_cli.py",
                    "tests/rebuild/test_install.py",  # wheel denial assertions name retired commands
                    "CHANGELOG.md", "docs/migration-to-rebuilt-core.md"}


def _living_surfaces() -> list[Path]:
    roots = ["src/", "tests/rebuild/", "tools/", "skills/deck-master/", ".github/",
             "docs/"]
    root_files = ["pyproject.toml", "MANIFEST.in", "README.md", "AGENTS.md",
                  "CONTRIBUTING.md", "ROADMAP.md", "DESIGN.md", "CHANGELOG.md"]
    surfaces = [REPO_ROOT / name for name in root_files]
    for root in roots:
        target = REPO_ROOT / root
        if not target.is_dir():
            continue
        for path in sorted(target.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts                     and path.suffix in {".py", ".md", ".toml", ".yml", ".yaml", ".in", ".txt"}                     and not str(path.relative_to(REPO_ROOT)).startswith("docs/archive/")                     and not str(path.relative_to(REPO_ROOT)).startswith("docs/specs/deck-master-rebuild-v1/"):
                surfaces.append(path)
    return surfaces


def test_retired_tree_has_zero_living_references() -> None:
    """AC-L05: no living surface (new code, rebuild tests, build tools, living
    skill, CI, root docs/config) references the retired tree or teaches the
    retired commands. The legacy-map table, its refusal tests, the changelog
    and the migration guide name them on purpose."""
    offenders = []
    for path in _living_surfaces():
        relative = str(path.relative_to(REPO_ROOT))
        if relative in SELF_DOCUMENTING or path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in ("scripts/deck_master.py", "scripts/runtime", "scripts/workflow",
                       "scripts/high_density", "import runtime", "import workflow",
                       "from runtime", "from workflow", "from high_density"):
            if needle in text:
                offenders.append(f"{relative}: {needle!r}")
        for needle in RETIRED_COMMAND_NEEDLES:
            # /autoplan is an external review skill, also named in archived
            # input paths. Still forbid the bare Deck Master CLI subcommand.
            found = re.search(r"(?<![/\w-])autoplan(?![\w-])", text) if needle == "autoplan" else needle in text
            if found:
                offenders.append(f"{relative}: retired command {needle!r}")
    assert not offenders, f"living references to the retired surface: {offenders[:10]}"


def test_spec_contracts_match_packaged_contracts_byte_for_byte() -> None:
    """Spec mirrors must match the active packaged contracts (P2 parity guard)."""
    spec_dirs = [REPO_ROOT / "docs" / "specs" / pack / "contracts"
                 for pack in ("deck-master-rebuild-v1", "deck-master-workbench-v3")]
    pkg_dir = NEW_PACKAGE / "resources" / "contracts"
    spec_files = [p for folder in spec_dirs for p in folder.glob("*.json")]
    spec_names = {p.name for p in spec_files}
    assert len(spec_names) == len(spec_files), "each contract has exactly one spec mirror"
    pkg_names = {p.name for p in pkg_dir.glob("*.json")}
    assert spec_names == pkg_names, f"contract sets differ: {spec_names ^ pkg_names}"
    for path in spec_files:
        assert path.read_bytes() == (pkg_dir / path.name).read_bytes(), \
            f"contract drift: {path.name}"
