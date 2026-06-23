from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmark.aggregate import build_benchmark_aggregate_report
from runtime.artifact_validator import sha256_file, validate_artifact_manifest
from runtime.run_state import write_json
from skills.installer import build_release_tree, verify_release_tree


SCHEMA_VERSION = "deck_rc_gate_report.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]


class RCGateError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check(check_id: str, status: str, *, required: bool, summary: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "required": required,
        "summary": summary,
        "details": details or {},
    }


def _json_parse_check() -> dict[str, Any]:
    roots = [
        REPO_ROOT / "docs" / "contracts",
        REPO_ROOT / "contracts",
        REPO_ROOT / "skills" / "deck-master" / "schemas",
    ]
    roots.extend(sorted((REPO_ROOT / "product_capabilities").glob("*/contracts")))
    roots.extend(sorted((REPO_ROOT / "capabilities").glob("*/contracts")))
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.glob("*.json")))
    files.extend(sorted((REPO_ROOT / "benchmarks" / "cases").glob("*/benchmark_case.json")))
    errors: list[dict[str, str]] = []
    for path in files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
    return _check(
        "schema_json_parse",
        "pass" if not errors else "fail",
        required=True,
        summary=f"{len(files)} JSON contract/case files parsed.",
        details={"file_count": len(files), "errors": errors},
    )


def _release_smoke_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dm_rc_release_") as tmp:
        release_root = Path(tmp) / "release"
        build_release_tree(release_root, force=True)
        verification = verify_release_tree(release_root, run_smoke=True)
        return _check(
            "release_smoke",
            "pass" if verification.get("valid") else "fail",
            required=True,
            summary="Self-contained release tree builds and starts.",
            details=verification,
        )


def _artifact_validator_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dm_rc_artifacts_") as tmp:
        run_dir = Path(tmp) / "run"
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True)
        html = artifacts_dir / "deck.html"
        html.write_text("<!doctype html><html><body>RC gate</body></html>", encoding="utf-8")
        manifest = {
            "schema_version": "deck_artifact_manifest.v1",
            "run_id": "rc-gate",
            "source_fingerprint": "rc-gate",
            "artifacts": [
                {
                    "artifact_id": "deck_html",
                    "kind": "deck_html",
                    "path": "artifacts/deck.html",
                    "media_type": "text/html",
                    "bytes": html.stat().st_size,
                    "sha256": sha256_file(html),
                    "source_fingerprint": "rc-gate",
                    "validation_status": "valid",
                }
            ],
        }
        validation = validate_artifact_manifest(run_dir, manifest, expected_source_fingerprint="rc-gate")
        return _check(
            "artifact_validator",
            "pass" if validation.get("valid") else "fail",
            required=True,
            summary="Artifact validator accepts a signed HTML artifact manifest.",
            details=validation,
        )


def _fixture_e2e_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dm_rc_fixture_") as tmp:
        root = Path(tmp)
        runs_dir = root / "runs"
        output = root / "autoplan-output.json"
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "deck_master.py"),
            "autoplan",
            "--brief-file",
            str(REPO_ROOT / "examples" / "briefs" / "retail_digital_transformation.txt"),
            "--industry",
            "retail",
            "--library-mode",
            "fixture",
            "--run-mode",
            "fixture",
            "--dev-allow-unsetup",
            "--runs-dir",
            str(runs_dir),
            "--run-id",
            "rc-fixture-smoke",
        ]
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            timeout=60,
        )
        details: dict[str, Any] = {"returncode": completed.returncode}
        if completed.returncode != 0:
            details["stderr"] = completed.stderr[-2000:]
            return _check("fixture_e2e", "fail", required=True, summary="Fixture autoplan smoke failed.", details=details)
        output.write_text(completed.stdout, encoding="utf-8")
        payload = json.loads(completed.stdout)
        run_dir = Path(payload["run_dir"])
        required = [
            "request.json",
            "narrative_plan.json",
            "page_tasks.json",
            "sourcing_plan.json",
            "preview_manifest.json",
        ]
        missing = [name for name in required if not (run_dir / name).exists()]
        preview = json.loads((run_dir / "preview_manifest.json").read_text(encoding="utf-8"))
        page_count = len(preview.get("pages", [])) if isinstance(preview.get("pages"), list) else 0
        details.update({"run_dir": str(run_dir), "missing": missing, "page_count": page_count})
        passed = not missing and page_count >= 10
        return _check(
            "fixture_e2e",
            "pass" if passed else "fail",
            required=True,
            summary="Fixture autoplan smoke produces a reviewable preview.",
            details=details,
        )


def _browser_smoke_check(*, skip: bool, require: bool) -> dict[str, Any]:
    if skip:
        return _check(
            "browser_smoke",
            "skipped",
            required=require,
            summary="Browser smoke skipped by command option.",
        )
    try:
        import playwright.sync_api  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - optional environment dependency.
        return _check(
            "browser_smoke",
            "fail" if require else "skipped",
            required=require,
            summary="Playwright browser runtime is not available.",
            details={"error": str(exc)},
        )
    static_dir = REPO_ROOT / "scripts" / "preview" / "static"
    expected = ["index.html"]
    missing = [name for name in expected if not (static_dir / name).exists()]
    return _check(
        "browser_smoke",
        "pass" if not missing else "fail",
        required=require,
        summary="Preview static browser assets are present.",
        details={"missing": missing},
    )


def _benchmark_aggregate_check(benchmark_dir: Path, min_real_cases: int) -> dict[str, Any]:
    report = build_benchmark_aggregate_report(benchmark_dir, min_real_cases=min_real_cases)
    status = "pass" if report["status"] == "report_ready" else "fail"
    return _check(
        "benchmark_aggregate",
        status,
        required=True,
        summary="Benchmark aggregate requires real completed benchmark reports for RC.",
        details=report,
    )


def build_rc_gate_report(
    *,
    benchmark_dir: str | Path | None = None,
    skip_browser_smoke: bool = False,
    require_browser_smoke: bool = False,
    min_real_cases: int = 3,
) -> dict[str, Any]:
    bench_root = Path(benchmark_dir).expanduser().resolve() if benchmark_dir else REPO_ROOT / "benchmarks"
    checks = [
        _json_parse_check(),
        _artifact_validator_check(),
        _release_smoke_check(),
        _fixture_e2e_check(),
        _browser_smoke_check(skip=skip_browser_smoke, require=require_browser_smoke),
        _benchmark_aggregate_check(bench_root, min_real_cases),
    ]
    required_failures = [check for check in checks if check["required"] and check["status"] != "pass"]
    optional_warnings = [
        check for check in checks
        if not check["required"] and check["status"] not in {"pass", "skipped"}
    ]
    status = "pass"
    if required_failures:
        status = "fail"
    elif optional_warnings:
        status = "warning"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "created_at": _utc_now(),
        "benchmark_dir": str(bench_root),
        "summary": {
            "checks": len(checks),
            "required_failures": len(required_failures),
            "optional_warnings": len(optional_warnings),
        },
        "checks": checks,
    }


def render_rc_gate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Deck Master RC Gate Report",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Required failures: `{(report.get('summary') or {}).get('required_failures', 0)}`",
        f"- Optional warnings: `{(report.get('summary') or {}).get('optional_warnings', 0)}`",
        "",
        "## Checks",
        "",
    ]
    for check in report.get("checks", []):
        lines.append(
            f"- `{check.get('check_id')}`: `{check.get('status')}` - {check.get('summary', '')}"
        )
    lines.append("")
    return "\n".join(lines)


def write_rc_gate_report(
    output_dir: str | Path,
    *,
    benchmark_dir: str | Path | None = None,
    skip_browser_smoke: bool = False,
    require_browser_smoke: bool = False,
    min_real_cases: int = 3,
    force: bool = False,
) -> dict[str, Any]:
    out_dir = Path(output_dir).expanduser().resolve()
    json_path = out_dir / "rc_gate_report.json"
    markdown_path = out_dir / "rc_gate_report.md"
    if not force and (json_path.exists() or markdown_path.exists()):
        raise RCGateError(f"RC gate report already exists: {out_dir}. Use --force to overwrite.")
    report = build_rc_gate_report(
        benchmark_dir=benchmark_dir,
        skip_browser_smoke=skip_browser_smoke,
        require_browser_smoke=require_browser_smoke,
        min_real_cases=min_real_cases,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(json_path, report)
    markdown_path.write_text(render_rc_gate_markdown(report), encoding="utf-8")
    return {
        "status": report["status"],
        "report": str(json_path),
        "markdown": str(markdown_path),
        "summary": report["summary"],
    }
