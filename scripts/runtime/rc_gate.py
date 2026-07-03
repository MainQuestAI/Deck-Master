from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from importlib import import_module
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from benchmark.aggregate import build_benchmark_aggregate_report
from runtime.artifact_validator import sha256_file, validate_artifact_manifest
from runtime.run_state import write_json
from skills.installer import build_release_tree, external_dependency_statuses, verify_release_tree


SCHEMA_VERSION = "deck_rc_gate_report.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]


class RCGateError(ValueError):
    pass


class BrowserSmokeUnavailable(RuntimeError):
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


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _safe_smoke_setup_status(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "schema_version": "deck_master_setup_status.v2",
        "status": "ready",
        "install_ready": True,
        "workspace_ready": True,
        "run_ready": True,
        "production_ready": True,
        "production_backend_ready": True,
        "client_delivery_ready": True,
        "missing_items": [],
        "repair_items": [],
        "repair_items_count": 0,
        "warnings": [],
        "config": {
            "install_root": "smoke-fixture",
            "active_workspace": "",
            "default_runs_dir": "",
        },
        "workspace": {"status": "valid"},
        "suite": {
            "status": "ready",
            "full_suite_ready": True,
            "production_backend_ready": True,
            "client_delivery_ready": True,
        },
        "external_dependency_status": [
            {
                "name": "ppt-master",
                "repo_label": "deck-master/ppt-master",
                "binding_status": "bound_verified",
                "short_sha": "smoke",
                "verified": True,
                "summary": "Smoke fixture backend summary.",
            }
        ],
        "blocking_summary": [],
    }


def _run_review_desk_browser_smoke(
    *,
    setup_status_fixture: Callable[..., dict[str, Any]] | None = None,
    workspace_payload_fixture: Callable[[str | Path], dict[str, Any]] | None = None,
    expected_title_contains: str | None = "Retail Transformation Draft",
    expected_visible_text: str | None = None,
    exercise_delivery_preview: bool = False,
    forbidden_markers: tuple[str, ...] = (
        "/Users/",
        "/private/",
        "--run-dir",
        "--workspace",
        "python3 ",
        "deck-master ",
        "artifact_path",
        "render_result",
        "rendered/index.html",
        ".json",
        "cmd=",
        "javascript:",
    ),
) -> dict[str, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001 - optional environment dependency.
        raise BrowserSmokeUnavailable(str(exc)) from exc

    preview_dir = REPO_ROOT / "scripts" / "preview"
    if str(preview_dir) not in sys.path:
        sys.path.insert(0, str(preview_dir))
    preview_server = import_module("server")
    preview_workspace_api = import_module("workspace_api")

    sample_run = REPO_ROOT / "examples" / "preview-run"
    if not sample_run.exists():
        raise RCGateError("Review Desk browser smoke fixture is missing.")

    with tempfile.TemporaryDirectory(prefix="dm_rc_browser_") as tmp:
        runs_dir = Path(tmp) / "runs"
        run_dir = runs_dir / "sample-preview-run"
        shutil.copytree(sample_run, run_dir)

        original_server_setup = preview_server.setup_status
        original_workspace_setup = preview_workspace_api.setup_status
        original_workspace_payload = preview_server.build_workspace_payload
        setup_status_source = setup_status_fixture or _safe_smoke_setup_status
        preview_server.setup_status = setup_status_source
        preview_workspace_api.setup_status = setup_status_source
        if workspace_payload_fixture is not None:
            preview_server.build_workspace_payload = workspace_payload_fixture
        httpd: ThreadingHTTPServer | None = None
        try:
            handler = preview_server.build_handler(run_dir, runs_dir, "fixture", use_setup_runs_dir=False)
            handler.log_message = lambda self, format, *args: None  # type: ignore[method-assign]
            port = _free_local_port()
            httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{port}/?run=sample-preview-run"
            collect_dom_attributes = """() => {
                const values = [];
                document.querySelectorAll("*").forEach((el) => {
                    Array.from(el.attributes || []).forEach((attr) => {
                        const name = String(attr.name || "").toLowerCase();
                        if (
                            name === "class"
                            || name === "title"
                            || name === "alt"
                            || name.startsWith("data-")
                            || name.startsWith("aria-")
                        ) {
                            values.push({
                                selector: el.tagName.toLowerCase(),
                                attribute: name,
                                value: attr.value || "",
                            });
                        }
                    });
                });
                document.querySelectorAll("img").forEach((el) => {
                    values.push({ selector: "img", attribute: "src", value: el.src || "" });
                });
                document.querySelectorAll("iframe").forEach((el) => {
                    values.push({ selector: "iframe", attribute: "src", value: el.src || "" });
                });
                document.querySelectorAll("option").forEach((el) => {
                    values.push({ selector: "option", attribute: "value", value: el.value || "" });
                });
                return values.filter((item) => item.value);
            }"""

            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    try:
                        page = browser.new_page(viewport={"width": 1280, "height": 900})
                        console_errors: list[str] = []
                        exercised_delivery = False
                        page.on(
                            "console",
                            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
                        )
                        page.goto(url, wait_until="networkidle", timeout=15000)
                        page.wait_for_selector("#workspace-title", timeout=10000)
                        title = page.locator("#workspace-title").inner_text(timeout=5000).strip()
                        page.wait_for_timeout(250)
                        attribute_values = page.evaluate(collect_dom_attributes)
                        if exercise_delivery_preview:
                            delivery_mode = page.locator("#delivery-mode:not([hidden])")
                            delivery_mode.wait_for(timeout=5000)
                            delivery_mode.click(timeout=5000)
                            page.wait_for_timeout(250)
                            exercised_delivery = True
                            attribute_values.extend(page.evaluate(collect_dom_attributes))
                        body_text = page.locator("body").inner_text(timeout=5000)
                        if expected_visible_text:
                            page.get_by_text(expected_visible_text).first.wait_for(timeout=10000)
                            body_text = page.locator("body").inner_text(timeout=5000)
                        if expected_title_contains and expected_title_contains not in title:
                            raise RCGateError(f"Review Desk did not load the fixture run title: {title}")
                        unsafe_markers = [
                            marker
                            for marker in forbidden_markers
                            if marker in body_text
                        ]
                        if unsafe_markers:
                            raise RCGateError(
                                f"Review Desk DOM exposed unsafe markers: {', '.join(unsafe_markers)}"
                            )
                        unsafe_attribute_values = []
                        for entry in attribute_values:
                            value = str(entry.get("value") or "")
                            decoded_value = unquote(value)
                            matched = [
                                marker
                                for marker in forbidden_markers
                                if marker in value or marker in decoded_value
                            ]
                            if matched:
                                unsafe_attribute_values.append({**entry, "markers": matched})
                        if unsafe_attribute_values:
                            markers = sorted({marker for item in unsafe_attribute_values for marker in item["markers"]})
                            raise RCGateError(
                                f"Review Desk DOM attributes exposed unsafe markers: {', '.join(markers)}"
                            )
                        if console_errors:
                            raise RCGateError(f"Review Desk console errors: {' | '.join(console_errors[:3])}")
                    finally:
                        browser.close()
            except PlaywrightError as exc:
                raise RCGateError(str(exc)) from exc

            return {
                "url": url,
                "run_id": "sample-preview-run",
                "title": title,
                "unsafe_markers": [],
                "unsafe_attribute_values": [],
                "attribute_values": attribute_values,
                "exercised_delivery_preview": exercised_delivery,
            }
        finally:
            preview_server.setup_status = original_server_setup
            preview_workspace_api.setup_status = original_workspace_setup
            preview_server.build_workspace_payload = original_workspace_payload
            if httpd is not None:
                httpd.shutdown()
                httpd.server_close()


def _browser_smoke_check(*, skip: bool, require: bool) -> dict[str, Any]:
    if skip:
        return _check(
            "browser_smoke",
            "skipped",
            required=require,
            summary="Browser smoke skipped by command option.",
        )
    try:
        details = _run_review_desk_browser_smoke()
    except BrowserSmokeUnavailable as exc:
        return _check(
            "browser_smoke",
            "fail" if require else "skipped",
            required=require,
            summary="Playwright browser runtime is not available.",
            details={"error": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001 - browser smoke should report UI failures as check details.
        return _check(
            "browser_smoke",
            "fail",
            required=require,
            summary="Review Desk browser smoke failed.",
            details={"error": str(exc)},
        )
    return _check(
        "browser_smoke",
        "pass",
        required=require,
        summary="Review Desk browser smoke loads the fixture run without unsafe visible markers.",
        details=details,
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


def _dependency_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for item in items:
        if item.get("name") == name:
            return item
    return {}


def _dependency_snapshot(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for name in ("ppt-master", "ppt-deck-pro-max"):
        item = _dependency_by_name(items, name)
        snapshot[name] = {
            "binding_status": str(item.get("binding_status") or ""),
            "git_sha": str(item.get("git_sha") or ""),
            "verified": bool(item.get("verified")),
        }
    return snapshot


def _external_dependency_closure_check(benchmark_report: dict[str, Any]) -> dict[str, Any]:
    dependencies = external_dependency_statuses()
    dependency_snapshot = _dependency_snapshot(dependencies)
    failures: list[str] = []
    backend = _dependency_by_name(dependencies, "ppt-master")
    bridge = _dependency_by_name(dependencies, "ppt-deck-pro-max")

    if backend.get("binding_status") not in {"bound_verified", "bound_verified_runtime_blocked"} or not backend.get("verified"):
        failures.append("ppt-master is not bound_verified")
    if not str(backend.get("git_sha") or ""):
        failures.append("ppt-master git_sha is missing")
    if bridge.get("binding_status") != "bound_verified" or not bridge.get("verified"):
        failures.append("ppt-deck-pro-max bridge is not bound_verified")
    if not str(bridge.get("git_sha") or ""):
        failures.append("ppt-deck-pro-max bridge git_sha is missing")
    if benchmark_report.get("status") != "report_ready":
        failures.append("benchmark aggregate is not report_ready")

    lock_snapshot: dict[str, dict[str, Any]] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="dm_rc_dependency_lock_") as tmp:
            release_root = Path(tmp) / "release"
            build_release_tree(release_root, force=True)
            lock = json.loads((release_root / "deck_capability_lock.json").read_text(encoding="utf-8"))
            locked = lock.get("external_dependency_status")
            if not isinstance(locked, list):
                locked = lock.get("external_dependencies")
            if not isinstance(locked, list):
                failures.append("capability lock missing external dependencies")
                locked = []
            lock_snapshot = _dependency_snapshot([item for item in locked if isinstance(item, dict)])
    except Exception as exc:  # noqa: BLE001 - RC gate should report closure errors as check details.
        failures.append(f"capability lock could not be built: {exc}")

    for name, current in dependency_snapshot.items():
        if lock_snapshot.get(name) != current:
            failures.append(f"{name} capability lock snapshot does not match current dependency truth")

    return _check(
        "external_dependency_closure",
        "pass" if not failures else "fail",
        required=True,
        summary="External backend, bridge, release lock, and benchmark closure are verified.",
        details={
            "dependencies": dependency_snapshot,
            "capability_lock_dependencies": lock_snapshot,
            "benchmark_status": str(benchmark_report.get("status") or ""),
            "failures": failures,
        },
    )


def build_rc_gate_report(
    *,
    benchmark_dir: str | Path | None = None,
    skip_browser_smoke: bool = False,
    require_browser_smoke: bool = False,
    min_real_cases: int = 3,
) -> dict[str, Any]:
    bench_root = Path(benchmark_dir).expanduser().resolve() if benchmark_dir else REPO_ROOT / "benchmarks"
    benchmark_report = build_benchmark_aggregate_report(bench_root, min_real_cases=min_real_cases)
    checks = [
        _json_parse_check(),
        _artifact_validator_check(),
        _release_smoke_check(),
        _fixture_e2e_check(),
        _browser_smoke_check(skip=skip_browser_smoke, require=require_browser_smoke),
        _check(
            "benchmark_aggregate",
            "pass" if benchmark_report["status"] == "report_ready" else "fail",
            required=True,
            summary="Benchmark aggregate requires real completed benchmark reports for RC.",
            details=benchmark_report,
        ),
        _external_dependency_closure_check(benchmark_report),
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
