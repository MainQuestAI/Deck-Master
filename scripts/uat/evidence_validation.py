"""Read-only verification of the existing validation/durable evidence bundle.

This checks recorded evidence, not whether an external tool really executed.
It never changes an acceptance ledger, a run, or a human approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys
from typing import Any, Mapping
from xml.etree import ElementTree

SHA = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"[0-9a-f]{64}")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

# The source checkout module entrypoint must load this checkout's sibling
# packages, without depending on PYTHONPATH or an unrelated editable install.
if __package__ == "scripts.uat" or not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or Path(relative).is_absolute() or PureWindowsPath(relative).drive
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise ValueError("unsafe_relative_path")
    path = root
    for part in relative.split("/"):
        path = path / part
        if path.is_symlink():
            raise ValueError("symlink_reference")
    if not path.resolve().is_relative_to(root):
        raise ValueError("outside_evidence_root")
    return path


class _Checks:
    def __init__(self, candidate_sha: str):
        self.candidate_sha = candidate_sha
        self.rows: list[dict[str, Any]] = []
        self.observed: dict[Path, str] = {}

    def add(self, key: str, status: str, reason: str = "", **details: Any) -> None:
        self.rows.append({"key": key, "status": status, "reason": reason, **details})

    def candidate(self, key: str, value: Any) -> bool:
        valid = value == self.candidate_sha
        self.add(key, "passed" if valid else "stale", "" if valid else "candidate_sha_mismatch_or_unbound",
                 expected_sha=self.candidate_sha, recorded_sha=value if isinstance(value, str) and SHA.fullmatch(value) else None)
        return valid

    def file(self, root: Path, relative: str, expected: Any, *, key: str = "") -> Path | None:
        key = key or relative
        try:
            path = _safe_path(root, relative)
            if not path.is_file():
                self.add(key, "missing", "evidence_file_missing")
                return None
            actual = _hash(path)
            self.observed[path] = actual
        except ValueError as exc:
            self.add(key, "stale", str(exc))
            return None
        except OSError:
            self.add(key, "missing", "evidence_file_unreadable")
            return None
        if expected is None:
            self.add(key, "missing", "expected_sha256_missing", observed_sha256=actual, expected_sha256=None)
        elif not isinstance(expected, str) or not HASH.fullmatch(expected) or actual != expected:
            self.add(key, "stale", "evidence_sha256_mismatch", observed_sha256=actual,
                     expected_sha256=expected if isinstance(expected, str) and HASH.fullmatch(expected) else None)
            return None
        else:
            self.add(key, "passed", observed_sha256=actual, expected_sha256=expected)
        return path

    def document(self, root: Path, relative: str, expected: Any = None, *, trusted_index: bool = False) -> dict:
        path = self.file(root, relative, expected)
        if trusted_index and path is not None and self.rows[-1]["reason"] == "expected_sha256_missing":
            # The caller-selected index is the verification root, not evidence
            # that an external command ran. Avoid an infinite hash recursion.
            self.rows.pop()
        if path is None:
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("expected_object")
            return value
        except (OSError, ValueError):
            self.add(relative, "stale", "invalid_json_object")
            return {}

    def finish(self) -> dict:
        # A pointer, index or file replaced during collection invalidates this
        # observation; the caller must retry. No projection repair is performed.
        for path, digest in self.observed.items():
            try:
                unchanged = not any(parent.is_symlink() for parent in (path, *path.parents)) and path.is_file() and _hash(path) == digest
            except OSError:
                unchanged = False
            if not unchanged:
                self.add("observation_stability", "stale", "evidence_changed_during_verification")
        counts = Counter(row["status"] for row in self.rows)
        status = next((name for name in ("failed", "stale", "missing", "human_pending") if counts[name]), "passed")
        return {"candidate_sha": self.candidate_sha, "status": status, "counts": dict(counts),
                "checks": self.rows, "read_only": True,
                "note": "Evidence verification only. This does not mark engineering_complete or accepted, attest external execution, or approve delivery."}


def _tests(checks: _Checks, root: Path, validation: dict, refs: dict) -> None:
    rows = validation.get("tests")
    if not isinstance(rows, list) or not rows:
        checks.add("tests", "missing", "test_records_missing")
        return
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            checks.add("tests", "stale", "invalid_test_record")
            continue
        version = str(row.get("python", ""))
        if not IDENTIFIER.fullmatch(version) or version in seen:
            checks.add("tests", "stale", "invalid_or_duplicate_python_id")
            continue
        seen.add(version)
        prefix = "python" + version
        metadata_ref = prefix + "-metadata.json"
        metadata = checks.document(root, metadata_ref, refs.get(metadata_ref))
        checks.candidate(prefix + ":candidate", metadata.get("sha"))
        xml = checks.file(root, prefix + "-results.xml", row.get("junit_sha256"))
        checks.file(root, prefix + "-pytest.log", row.get("log_sha256"))
        if xml is not None:
            try:
                document = ElementTree.parse(xml).getroot()
                suites = [document] if document.tag == "testsuite" else document.findall("testsuite")
                counters = [{name: int(suite.get(name, "0")) for name in ("tests", "skipped", "failures", "errors")} for suite in suites]
                if any(any(value < 0 for value in row.values()) or row["skipped"] > row["tests"] for row in counters):
                    raise ValueError("invalid_junit_counters")
                total = sum(counter["tests"] for counter in counters)
                skipped = sum(counter["skipped"] for counter in counters)
                failures = sum(counter["failures"] + counter["errors"] for counter in counters)
                executed = total - skipped
                observed = {"tests": total, "skipped": skipped, "executed": executed}
                if executed <= 0:
                    checks.add(prefix + ":result", "missing", "no_executed_tests", **observed)
                elif failures or row.get("status") == "failed":
                    checks.add(prefix + ":result", "failed", "test_failure_recorded", **observed)
                elif row.get("status") != "passed":
                    checks.add(prefix + ":result", "missing", "test_execution_incomplete", **observed)
                elif int(row.get("tests", -1)) != total:
                    checks.add(prefix + ":result", "stale", "test_count_disagrees_with_junit", **observed)
                else:
                    checks.add(prefix + ":result", "passed", **observed)
            except (OSError, ValueError, TypeError, ElementTree.ParseError):
                checks.add(prefix + ":result", "stale", "invalid_junit_result")


def _release(checks: _Checks, root: Path, relative: str, refs: dict) -> None:
    summary = checks.document(root, relative, refs.get(relative))
    checks.candidate("release:candidate", summary.get("candidate_sha"))
    evidence = summary.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        checks.add("release", "missing", "release_evidence_missing")
        return
    prefix = str(Path(relative).parent)
    for item in evidence:
        if not isinstance(item, dict):
            checks.add("release", "stale", "invalid_evidence_reference")
            continue
        checks.file(root, prefix + "/" + str(item.get("path", "")), item.get("sha256"))
    status = summary.get("result")
    checks.add("release:result", "passed" if status == "passed" else "failed" if status == "failed" else "missing", "" if status == "passed" else "release_not_passed")


def _run(checks: _Checks, label: str, root: Path) -> tuple[dict, dict]:
    from workflow.actions import read_revision_state
    try:
        pointer = checks.document(root, "build/current_revision.json", trusted_index=True)
        revision = pointer.get("revision_id", "")
        if not revision:
            checks.add(label + ":input_revision", "missing", "current_revision_missing")
            return {}, {}
        state = read_revision_state(root, revision)
        render = checks.document(root, "render_results/render_result.json", trusted_index=True)
        if not isinstance(render.get("artifacts", []), list):
            checks.add(label + ":render", "stale", "invalid_render_artifact_list")
            render["artifacts"] = []
        if render.get("build_revision") != revision:
            checks.add(label + ":render_revision", "stale", "render_does_not_match_current_input_revision")
        if render.get("status") != "completed":
            checks.add(label + ":render", "missing", "render_not_completed")
        render["current_input_revision"] = revision
        return state, render
    except (OSError, ValueError, TypeError, RuntimeError):
        checks.add(label + ":input_revision", "stale", "invalid_current_revision_snapshot")
        return {}, {}


def _parity(checks: _Checks, root: Path, relative: str, refs: dict, run_dirs: Mapping[str, Path]) -> None:
    summary = checks.document(root, relative, refs.get(relative))
    checks.candidate("parity:candidate", summary.get("source_sha"))
    pages = summary.get("pages")
    if not isinstance(pages, list) or not pages:
        checks.add("parity", "missing", "page_evidence_missing")
        return
    runs, seen = {}, set()
    prefix = str(Path(relative).parent)
    for page in pages:
        if not isinstance(page, dict):
            checks.add("parity:page_set", "stale", "invalid_page_record")
            continue
        label, page_id = str(page.get("run", "")), str(page.get("page_id", ""))
        key = label + ":" + page_id
        if not IDENTIFIER.fullmatch(label) or not IDENTIFIER.fullmatch(page_id) or key in seen:
            checks.add("parity:page_set", "stale", "unsafe_or_duplicate_page_id")
            continue
        seen.add(key)
        checks.candidate(key + ":candidate", page.get("source_sha"))
        folder = prefix + "/" + label
        for name, field in (("original.svg", "source_svg_sha256"), ("scene.json", "scene_sha256"), ("pptx-original.png", "png_sha256")):
            checks.file(root, folder + "/" + page_id + "/" + name, page.get(field))
        checks.file(root, folder + "/deck.pptx", page.get("pptx_sha256"))
        try:
            ssim, delta = page["masked_ssim"], page["geometry_max_delta_pt"]
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in (ssim, delta)):
                raise ValueError("invalid_numeric_measurement")
            passed = (math.isfinite(ssim) and math.isfinite(delta) and 0.97 <= ssim <= 1 and 0 <= delta <= 0.75
                      and page.get("pass") is True and page.get("geometry_p0_p1_pass") is True and page.get("missing_ids") == [])
        except (KeyError, TypeError, ValueError):
            passed = False
        checks.add(key + ":measured_result", "passed" if passed else "failed", "" if passed else "recorded_parity_threshold_failed")
        if label not in run_dirs:
            checks.add(key + ":current_inputs", "missing", "current_run_not_supplied")
            continue
        run_root = Path(run_dirs[label]).expanduser().resolve()
        if label not in runs:
            runs[label] = _run(checks, label, run_root)
        state, render = runs[label]
        if not isinstance(page.get("input_revision"), str) or not page["input_revision"] or page["input_revision"] != render.get("current_input_revision"):
            checks.add(key + ":input_revision", "stale", "input_revision_changed_or_unbound")
        else:
            checks.add(key + ":input_revision", "passed")
        for field, names in (
            ("source_svg_sha256", [f"high_density_build/svg/{page_id}.svg"]),
            ("scene_sha256", [f"high_density_build/page_scenes/{page_id}.json", f"high_density_build/page_scenes/{page_id}.page_scene.json"]),
        ):
            content = next((state[name] for name in names if name in state), None)
            status = "missing" if content is None else "passed" if hashlib.sha256(content).hexdigest() == page.get(field) else "stale"
            checks.add(key + ":current_" + field, status, "" if status == "passed" else "current_input_missing_or_changed")
        artifact = render.get("artifact_path", "")
        checks.file(run_root, artifact, page.get("pptx_sha256"), key=key + ":current_pptx")
        images = [item for item in render.get("artifacts", []) if isinstance(item, dict) and item.get("page_id") == page_id and item.get("kind") == "page_png"]
        if len(images) != 1:
            checks.add(key + ":current_png", "missing", "selected_page_preview_missing_or_ambiguous")
        else:
            checks.file(run_root, images[0].get("path", ""), page.get("png_sha256"), key=key + ":current_png")
    for label in run_dirs:
        if label not in runs:
            checks.add(label + ":page_coverage", "missing", "requested_run_has_no_page_evidence")
            continue
        render = runs[label][1]
        expected = {str(item.get("page_id")) for item in render.get("artifacts", []) if isinstance(item, dict) and item.get("kind") == "page_png"}
        actual = {key.split(":", 1)[1] for key in seen if key.startswith(label + ":")}
        if expected != actual or len(expected) != render.get("page_count"):
            checks.add(label + ":page_coverage", "missing", "current_page_set_not_fully_covered")
    if summary.get("total") != len(seen) or summary.get("passed") != sum(isinstance(page, dict) and page.get("pass") is True for page in pages):
        checks.add("parity:counts", "stale", "page_summary_counts_disagree")


def verify_evidence_bundle(evidence_root: str | Path, candidate_sha: str, *,
                           run_dirs: Mapping[str, Path] | None = None,
                           release_summary_ref: str | None = None,
                           parity_summary_ref: str | None = None) -> dict:
    """Verify existing bundle files without copying evidence or changing state.

    ``run_dirs`` maps the labels in parity pages to current local runs. Omission
    leaves freshness missing. The caller selects the full expected git SHA.
    Summary ref overrides support other bundle folder names without migration.
    """
    if not isinstance(candidate_sha, str) or not SHA.fullmatch(candidate_sha):
        raise ValueError("candidate_sha must be a full lowercase 40-character SHA")
    root = Path(evidence_root).expanduser().resolve()
    checks = _Checks(candidate_sha)
    manifest = checks.document(root, "durable-evidence-manifest.json", trusted_index=True)
    validation = checks.document(root, "validation.json", trusted_index=True)
    checks.candidate("manifest:candidate", manifest.get("source_sha"))
    checks.candidate("validation:candidate", validation.get("source_sha"))
    refs = {}
    files = manifest.get("files", [])
    if not isinstance(files, list):
        checks.add("manifest:files", "stale", "invalid_evidence_index")
        files = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            checks.add("manifest:files", "stale", "invalid_evidence_reference")
            continue
        relative = item.get("path", "")
        if relative in refs:
            checks.add("manifest:files", "stale", "duplicate_evidence_reference")
        refs[relative] = item.get("sha256")
        checks.file(root, relative, item.get("sha256"))
    if not refs or manifest.get("file_count") != len(refs):
        checks.add("manifest:files", "missing" if not refs else "stale", "empty_or_inconsistent_file_index")
    source = str(manifest.get("source_sha", ""))
    suffix = source[:7] if SHA.fullmatch(source) else candidate_sha[:7]
    _tests(checks, root, validation, refs)
    _release(checks, root, release_summary_ref or f"release-{suffix}/summary.json", refs)
    run_dirs = run_dirs or {}
    if any(not isinstance(label, str) or not IDENTIFIER.fullmatch(label) for label in run_dirs):
        raise ValueError("run_dirs labels must be safe identifiers")
    if len({str(Path(path).resolve()) for path in run_dirs.values()}) != len(run_dirs):
        checks.add("current_runs", "stale", "same_run_supplied_under_multiple_labels")
    _parity(checks, root, parity_summary_ref or f"actual20-{suffix}/summary.json", refs, run_dirs)
    ci = checks.document(root, "ci.json", refs.get("ci.json"))
    checks.candidate("ci:candidate", ci.get("headRefOid"))
    jobs = ci.get("statusCheckRollup")
    if not isinstance(jobs, list) or not jobs:
        checks.add("ci:result", "missing", "ci_checks_missing")
    elif not all(isinstance(job, dict) for job in jobs):
        checks.add("ci:result", "stale", "invalid_ci_check_record")
    elif any(str(job.get("conclusion")) in {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"} for job in jobs):
        checks.add("ci:result", "failed", "ci_failure_recorded")
    elif all(job.get("status") == "COMPLETED" and job.get("conclusion") == "SUCCESS" for job in jobs):
        checks.add("ci:result", "passed")
    else:
        checks.add("ci:result", "missing", "ci_execution_incomplete")
    for field in ("human_visual_review", "final_file_approval"):
        # These flags are declarations, not signed current workflow approvals.
        # A passed string cannot turn this read-only utility into an approver.
        pending = validation.get(field) in (None, "pending", "human_pending")
        checks.add(field, "human_pending" if pending else "missing", "human_review_required" if pending else "human_approval_binding_not_evaluated")
    return checks.finish()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run", action="append", default=[], metavar="LABEL=RUN_DIR")
    args = parser.parse_args(argv)
    runs = {}
    for item in args.run:
        label, separator, directory = item.partition("=")
        if not separator or not IDENTIFIER.fullmatch(label) or not directory or label in runs:
            parser.error("--run requires unique LABEL=RUN_DIR mappings")
        runs[label] = Path(directory)
    result = verify_evidence_bundle(args.evidence_root, args.candidate_sha, run_dirs=runs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"passed", "human_pending"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
