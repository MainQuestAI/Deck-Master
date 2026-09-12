"""Byte-level evidence fixtures; these tests do not claim real PPTX rendering."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from uat.evidence_validation import verify_evidence_bundle
from workflow.actions import create_action_envelope, stage_action_result, commit_action_result

SHA = "a" * 40


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def index(root):
    files = [{"path": path.relative_to(root).as_posix(), "sha256": digest(path)}
             for path in sorted(root.rglob("*")) if path.is_file() and path.name != "durable-evidence-manifest.json"]
    write(root / "durable-evidence-manifest.json", {"source_sha": SHA, "file_count": len(files), "files": files})


def bundle(tmp_path):
    root = tmp_path / "evidence"
    run = tmp_path / "run"
    run.mkdir()
    write(run / "request.json", {"run_id": "run", "run_mode": "production"})
    envelope = create_action_envelope(action_id="input", task_id="input", scope_pages=["P001"], permission="runtime", input_fingerprint="input")
    files = {"high_density_build/svg/P001.svg": "unit SVG bytes", "high_density_build/page_scenes/P001.json": "{}"}
    stage_action_result(run, envelope, files)
    receipt = commit_action_result(run, envelope, current_input_fingerprint="input", targets={name: run / name for name in files})
    (run / "deck.pptx").write_bytes(b"unit artifact bytes, not a presentation")
    (run / "P001.png").write_bytes(b"unit preview bytes, not an image")
    write(run / "render_results/render_result.json", {"tool": "deck_native", "status": "completed", "build_revision": receipt["revision_id"],
        "artifact_path": "deck.pptx", "page_count": 1, "artifacts": [{"kind": "page_png", "page_id": "P001", "path": "P001.png"}]})
    parity_root = root / "actual20-aaaaaaa"
    page_root = parity_root / "main/P001"
    page_root.mkdir(parents=True)
    for source, target in [(run / "high_density_build/svg/P001.svg", page_root / "original.svg"),
                           (run / "high_density_build/page_scenes/P001.json", page_root / "scene.json"),
                           (run / "P001.png", page_root / "pptx-original.png"), (run / "deck.pptx", parity_root / "main/deck.pptx")]:
        target.write_bytes(source.read_bytes())
    page = {"run": "main", "page_id": "P001", "source_sha": SHA, "input_revision": receipt["revision_id"],
            "source_svg_sha256": digest(page_root / "original.svg"), "scene_sha256": digest(page_root / "scene.json"),
            "png_sha256": digest(page_root / "pptx-original.png"), "pptx_sha256": digest(parity_root / "main/deck.pptx"),
            "pass": True, "geometry_p0_p1_pass": True, "missing_ids": [], "masked_ssim": 0.99, "geometry_max_delta_pt": 0.1}
    write(parity_root / "summary.json", {"source_sha": SHA, "pages": [page], "total": 1, "passed": 1})
    release_root = root / "release-aaaaaaa"
    release_root.mkdir()
    (release_root / "actual.log").write_text("unit evidence")
    write(release_root / "summary.json", {"candidate_sha": SHA, "result": "passed", "evidence": [{"path": "actual.log", "sha256": digest(release_root / "actual.log")}]})
    (root / "python312-pytest.log").write_text("1 passed")
    (root / "python312-results.xml").write_text('<testsuites><testsuite tests="1" failures="0" errors="0"/></testsuites>')
    write(root / "python312-metadata.json", {"sha": SHA})
    write(root / "ci.json", {"headRefOid": SHA, "statusCheckRollup": [{"name": "unit", "status": "COMPLETED", "conclusion": "SUCCESS"}]})
    write(root / "validation.json", {"source_sha": SHA, "human_visual_review": "pending", "final_file_approval": "pending",
        "tests": [{"python": "312", "status": "passed", "tests": "1", "junit_sha256": digest(root / "python312-results.xml"), "log_sha256": digest(root / "python312-pytest.log")}]})
    index(root)
    return root, run


def verify(root, run, sha=SHA):
    return verify_evidence_bundle(root, sha, run_dirs={"main": run})


def reasons(result):
    return {row["reason"] for row in result["checks"]}


def test_current_bundle_is_read_only_and_keeps_human_pending(tmp_path):
    root, run = bundle(tmp_path)
    before = {str(path): (digest(path), path.stat().st_mtime_ns) for path in tmp_path.rglob("*") if path.is_file()}
    result = verify(root, run)
    assert result["status"] == "human_pending"
    assert result["counts"]["human_pending"] == 2
    assert set(result["counts"]) == {"passed", "human_pending"}
    assert str(tmp_path) not in json.dumps(result)
    assert before == {str(path): (digest(path), path.stat().st_mtime_ns) for path in tmp_path.rglob("*") if path.is_file()}


@pytest.mark.parametrize("change, expected", [("candidate", "candidate_sha_mismatch_or_unbound"),
    ("artifact", "evidence_sha256_mismatch"), ("evidence", "evidence_sha256_mismatch"),
    ("revision", "input_revision_changed_or_unbound"), ("missing", "evidence_file_missing")])
def test_historical_pass_cannot_be_reused_after_drift(tmp_path, change, expected):
    root, run = bundle(tmp_path)
    candidate = SHA
    if change == "candidate":
        candidate = "b" * 40
    elif change == "artifact":
        (run / "deck.pptx").write_bytes(b"new artifact")
    elif change == "evidence":
        (root / "release-aaaaaaa/actual.log").write_text("changed evidence")
    elif change == "missing":
        (root / "actual20-aaaaaaa/main/P001/scene.json").unlink()
    else:
        envelope = create_action_envelope(action_id="later", task_id="later", scope_pages=["P001"], permission="runtime", input_fingerprint="later")
        stage_action_result(run, envelope, {"request.json": '{"run_id":"run","changed":true}'})
        commit_action_result(run, envelope, current_input_fingerprint="later", targets={"request.json": run / "request.json"})
    result = verify(root, run, candidate)
    assert result["status"] in {"stale", "missing"}
    assert expected in reasons(result)


@pytest.mark.parametrize("unsafe", ["../outside", "/outside", "C:/outside", "parent/../outside"])
def test_escaping_manifest_reference_is_rejected_without_reading(tmp_path, unsafe):
    root, run = bundle(tmp_path)
    manifest = json.loads((root / "durable-evidence-manifest.json").read_text())
    manifest["files"].append({"path": unsafe, "sha256": "0" * 64})
    manifest["file_count"] += 1
    write(root / "durable-evidence-manifest.json", manifest)
    assert "unsafe_relative_path" in reasons(verify(root, run))


def test_symlink_and_unbound_ci_are_never_current_passes(tmp_path):
    root, run = bundle(tmp_path)
    original = root / "release-aaaaaaa/actual.log"
    outside = tmp_path / "outside.log"
    original.rename(outside)
    original.symlink_to(outside)
    manifest = json.loads((root / "durable-evidence-manifest.json").read_text())
    manifest["files"] = [item for item in manifest["files"] if item["path"] != "ci.json"]
    manifest["file_count"] -= 1
    write(root / "durable-evidence-manifest.json", manifest)
    result = verify(root, run)
    assert "symlink_reference" in reasons(result)
    assert any(row["key"] == "ci.json" and row["status"] == "missing" and row["observed_sha256"] == digest(root / "ci.json") for row in result["checks"])


def test_false_pass_and_weakened_visual_threshold_do_not_pass(tmp_path):
    root, run = bundle(tmp_path)
    path = root / "actual20-aaaaaaa/summary.json"
    parity = json.loads(path.read_text())
    parity["thresholds"] = {"masked_ssim": 0.1, "geometry_pt": 100}
    parity["pages"][0]["masked_ssim"] = 0.8
    write(path, parity)
    index(root)
    assert "recorded_parity_threshold_failed" in reasons(verify(root, run))


def test_page_coverage_and_human_flags_are_not_self_certifying(tmp_path):
    root, run = bundle(tmp_path)
    render_path = run / "render_results/render_result.json"
    render = json.loads(render_path.read_text())
    render["page_count"] = 2
    render["artifacts"].append({"kind": "page_png", "page_id": "P002", "path": "P002.png"})
    write(render_path, render)
    validation = json.loads((root / "validation.json").read_text())
    validation["human_visual_review"] = "passed"
    validation["final_file_approval"] = "passed"
    write(root / "validation.json", validation)
    index(root)
    result = verify(root, run)
    assert "current_page_set_not_fully_covered" in reasons(result)
    assert "human_approval_binding_not_evaluated" in reasons(result)
    assert "current_run_not_supplied" in reasons(verify_evidence_bundle(root, SHA))


def test_module_cli_works_without_pythonpath(tmp_path):
    root, run = bundle(tmp_path)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-m", "scripts.uat.evidence_validation", "--evidence-root", str(root),
        "--candidate-sha", SHA, "--run", "main=" + str(run)], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["status"] == "human_pending"


@pytest.mark.parametrize("kind", ["junit_failure", "ci_failure", "empty_junit", "malformed_manifest", "malformed_pages"])
def test_recorded_failures_and_malformed_evidence_do_not_inherit_pass(tmp_path, kind):
    root, run = bundle(tmp_path)
    if kind in {"junit_failure", "empty_junit"}:
        path = root / "python312-results.xml"
        path.write_text('<testsuite tests="1" failures="1" errors="0"/>' if kind == "junit_failure" else '<testsuite tests="0" failures="0" errors="0"/>')
        validation = json.loads((root / "validation.json").read_text())
        validation["tests"][0]["junit_sha256"] = digest(path)
        write(root / "validation.json", validation)
    elif kind == "ci_failure":
        write(root / "ci.json", {"headRefOid": SHA, "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "FAILURE"}]})
    elif kind == "malformed_pages":
        write(root / "actual20-aaaaaaa/summary.json", {"source_sha": SHA, "pages": [None]})
    index(root)
    if kind == "malformed_manifest":
        write(root / "durable-evidence-manifest.json", {"source_sha": SHA, "files": {"unexpected": True}})
    result = verify(root, run)
    assert result["status"] == ("failed" if kind in {"junit_failure", "ci_failure"} else "missing" if kind == "empty_junit" else "stale")


def test_artifact_changed_during_verification_invalidates_observation(tmp_path, monkeypatch):
    import uat.evidence_validation as module
    root, run = bundle(tmp_path)
    original = module._parity

    def change_after_verification(*args, **kwargs):
        original(*args, **kwargs)
        (run / "deck.pptx").write_bytes(b"replacement after this artifact was checked")

    monkeypatch.setattr(module, "_parity", change_after_verification)
    result = verify(root, run)
    assert result["status"] == "stale"
    assert "evidence_changed_during_verification" in reasons(result)
