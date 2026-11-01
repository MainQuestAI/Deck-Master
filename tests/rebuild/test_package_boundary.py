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
                    # Frozen inventory tools inspect/name old paths; they do not execute them.
                    "docs/specs/deck-master-rebuild-v1/inventory/scan_old_references.py",
                    "docs/specs/deck-master-rebuild-v1/tools/materialize_inventory.py",
                    "CHANGELOG.md", "docs/migration-to-rebuilt-core.md"}


# Point-in-time audit/evidence directories that legitimately cite retired
# trees as historical fact — the same non-living status as docs/archive/.
# Registration is explicit and deliberate: a date in a directory name does
# not grant an exemption (see test_dated_but_unregistered_doc_stays_guarded).
# Code files are never exempt, wherever they live.
HISTORICAL_AUDIT_DIRS = (
    "docs/reports/controlled-collaboration-audit-20261012",
    "docs/reports/skill-flow-review-20261012",
    "docs/reports/webui-backend-feasibility-20260926",
    "docs/reports/workbench-v3-execution-20260926",
)


def _is_historical_audit_record(relative: str, path: Path) -> bool:
    """True only for non-code files inside an explicitly registered historical
    audit directory. Everything else (code, living documents, dated-but-
    unregistered directories, including this increment's own evidence
    directory) stays on the scanned living surface."""
    if path.suffix == ".py":
        return False
    parts = relative.split("/")
    if len(parts) < 3:
        return False
    return "/".join(parts[:3]) in HISTORICAL_AUDIT_DIRS


def _living_surfaces() -> list[Path]:
    roots = ["src/", "tests/rebuild/", "tools/", "skills/", ".github/",
             "docs/"]
    root_files = ["pyproject.toml", "MANIFEST.in", "README.md", "AGENTS.md", "CLAUDE.md",
                  "CONTRIBUTING.md", "ROADMAP.md", "DESIGN.md", "CHANGELOG.md"]
    surfaces = [REPO_ROOT / name for name in root_files]
    for root in roots:
        target = REPO_ROOT / root
        if not target.is_dir():
            continue
        for path in sorted(target.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix not in {".py", ".md", ".toml", ".yml", ".yaml", ".in", ".txt"}:
                continue
            relative = str(path.relative_to(REPO_ROOT))
            if path.suffix != ".py" and relative.startswith("docs/archive/"):
                continue
            if path.suffix != ".py" and relative.startswith("docs/specs/deck-master-rebuild-v1/"):
                continue
            if _is_historical_audit_record(relative, path):
                continue
            surfaces.append(path)
    return surfaces


def test_dated_but_unregistered_doc_stays_guarded(tmp_path, monkeypatch) -> None:
    """A directory carrying a date is not thereby historical: only explicitly
    registered audit directories are exempt, and code inside them never is."""
    for registered in HISTORICAL_AUDIT_DIRS:
        assert _is_historical_audit_record(f"{registered}/notes.md", Path("notes.md")), registered
        assert not _is_historical_audit_record(f"{registered}/tool.py", Path("tool.py")), registered
    # A dated directory that is NOT registered remains an active surface — an
    # operational guide with a date in its name must not silently hide.
    assert not _is_historical_audit_record("docs/reports/some-active-guide-20260101/guide.md",
                                           Path("guide.md"))
    assert not _is_historical_audit_record("docs/reports/deep/nested-20260101/notes.md",
                                           Path("notes.md"))
    code_paths = ["docs/archive/old/tool.py",
                  "docs/specs/deck-master-rebuild-v1/new_tool.py",
                  f"{HISTORICAL_AUDIT_DIRS[0]}/tool.py"]
    dated_doc = "docs/reports/some-active-guide-20260101/guide.md"
    for relative in [*code_paths, dated_doc]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Run deck-master backend bind production.")
    monkeypatch.setitem(globals(), "REPO_ROOT", tmp_path)
    surfaces = {str(path.relative_to(tmp_path)) for path in _living_surfaces()}
    assert {*code_paths, dated_doc} <= surfaces


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
        for issue in active_guidance_issues(text, code=path.suffix == '.py'):
            offenders.append(f"{relative}: {issue}")
    assert not offenders, f"living references to the retired surface: {offenders[:10]}"


def active_guidance_issues(text: str, *, code=False) -> list[str]:
    """Reject executable retired guidance, preserving explicit migration prose.

    Context only applies to prose; code never gains an exemption by naming
    a directory historical or by mentioning a negation elsewhere in a file.
    """
    issues = []
    for number, line in enumerate(text.splitlines(), 1):
        for needle in RETIRED_COMMAND_NEEDLES:
            pattern = r'(?<![/\w-])autoplan(?![\w-])' if needle == 'autoplan' else re.escape(needle)
            for mention in re.finditer(pattern, line):
                prefix = line[:mention.start()]
                invocation = re.search(r'\bdeck-master\s+$', prefix)
                if invocation:
                    prefix = prefix[:invocation.start()]
                # The modifier must bind this occurrence. Unrelated "retired
                # cache" prose or an earlier negated command cannot hide it.
                negative = re.search(
                    r'(?:无需(?:运行|执行)?|不得(?:运行|执行)?|不要(?:运行|执行)?|'
                    r'不再(?:运行|执行|要求)?|do not (?:run|use)|never (?:run|use)|'
                    r'no longer (?:run|use|require))\s*`?$', prefix, re.I)
                historical_name = not invocation and re.search(r'(?:旧|historical|retired)\s*`?$', prefix, re.I)
                historical_command = re.search(
                    r'(?:historical command|retired command)\s*:\s*`?$', prefix, re.I)
                if not code and (negative or historical_command or historical_name):
                    continue
                issues.append(f'line {number}: retired command {needle!r}')
        if not code and re.search(
                r'GBrain is set up and synced on this machine|'
                r'This worktree is pinned to a worktree-scoped code source|'
                r'Platform:\s*local Mac launchd|Production URL:\s*http://127\.0\.0\.1:5050', line):
            issues.append(f'line {number}: unverified maintainer-machine configuration')
    return issues


def test_active_guard_covers_four_skills_and_claude():
    surfaces = {str(path.relative_to(REPO_ROOT)) for path in _living_surfaces()}
    assert {'CLAUDE.md', *(f'skills/{name}/SKILL.md' for name in
            ('deck-master', 'deck-content', 'deck-design', 'deck-review'))} <= surfaces
    assert active_guidance_issues('Run deck-master backend bind production before create.')
    assert active_guidance_issues('Run deck-master backend bind production; retired cache was removed.')
    assert active_guidance_issues('Do not use a retired cache; run deck-master backend bind production.')
    assert active_guidance_issues('Do not run deck-master backend bind old; run deck-master backend bind production.')
    assert active_guidance_issues('GBrain is set up and synced on this machine.')


def test_active_guard_preserves_explicit_migration_and_negative_context():
    assert not active_guidance_issues('无需运行 deck-master backend bind production；新项目直接 create。')
    assert not active_guidance_issues('旧 backend bind 属于历史说明，当前材料目录即可创建项目。')
    assert not active_guidance_issues('Do not run deck-master backend bind production.')
    assert not active_guidance_issues('Historical command: `deck-master backend bind production` (migration record).')
    assert active_guidance_issues('Do not run deck-master backend bind production.', code=True)
    assert active_guidance_issues('deck-master backend bind production', code=True)
    frozen_spec = REPO_ROOT / "docs/specs/deck-master-next-iteration-20261019/task-cards/N5-docs-and-release.md"
    baseline_rows = [line for line in frozen_spec.read_text().splitlines() if "旧 backend bind" in line]
    assert baseline_rows
    assert all(not active_guidance_issues(line) for line in baseline_rows)


def test_contracts_have_exactly_one_active_source() -> None:
    """Runtime contracts live in the packaged package, and nowhere else.

    2026-10-30: the 85 byte-identical spec mirrors under ``docs/specs/*/contracts``
    were retired (audit overdefense-audit-20261030, OD-D1). A re-added ``docs``
    schema copy reopens the drift surface this guard used to police.
    """
    from deck_master.models import SCHEMA_FILES

    pkg_dir = NEW_PACKAGE / "resources" / "contracts"
    packaged = {path.name for path in pkg_dir.glob("*.schema.json")}
    assert packaged, "packaged contracts are missing"
    assert not list((REPO_ROOT / "docs").rglob("*.schema.json")), \
        "spec schema copies are retired; link src/deck_master/resources/contracts instead"
    assert set(SCHEMA_FILES.values()) <= packaged
