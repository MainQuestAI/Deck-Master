from __future__ import annotations

import json
import os
import re
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
from runtime.library_status import inspect_library_status
from runtime.run_state import write_json
from skills.installer import build_release_tree, external_dependency_statuses, verify_release_tree
from sourcing.plan import build_sourcing_plan_v2, migrate_v1
from tools.ppt_library_client import (
    PPTLibraryClientError,
    build_bridge_plan,
    normalize_candidate,
    run_library_selection,
    validate_library_selection,
)
from uat.real_workflow_smoke import run_real_workflow_smoke


SCHEMA_VERSION = "deck_rc_gate_report.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]


class RCGateError(ValueError):
    pass


class BrowserSmokeUnavailable(RuntimeError):
    pass


_UNSAFE_EVIDENCE_MARKERS = (
    "/Users/",
    "/Volumes/",
    "/home/",
    "/opt/",
    "/private/",
    "/tmp/",
    "/var/",
    "\\Users\\",
)
_UNSAFE_EVIDENCE_KEYS = ('"source_file"', '"source_path"')


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


def _safe_benchmark_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(report.get("status") or ""),
        "min_real_cases": int(report.get("min_real_cases") or 0),
        "case_counts": dict(report.get("case_counts") or {}),
        "report_counts": dict(report.get("report_counts") or {}),
        "private_source_policy": dict(report.get("private_source_policy") or {}),
        "metrics": dict(report.get("metrics") or {}),
    }


def _evidence_safety_violations(
    *texts: str,
    forbidden_markers: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    markers = [*_UNSAFE_EVIDENCE_MARKERS, *(forbidden_markers or [])]
    violations: list[str] = []
    joined = "\n".join(texts)
    for marker in markers:
        if marker and marker in joined:
            violations.append(f"forbidden marker: {marker}")
    for key in _UNSAFE_EVIDENCE_KEYS:
        if key in joined:
            violations.append(f"forbidden field: {key.strip(chr(34))}")
    if re.search(r'"\s*:\s*"/(?!/)', joined):
        violations.append("absolute path value")
    return sorted(set(violations))


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
        smoke = verification.get("smoke") if isinstance(verification.get("smoke"), dict) else {}
        runtime = verification.get("runtime") if isinstance(verification.get("runtime"), dict) else {}
        safe_verification = {
            "schema_version": verification.get("schema_version"),
            "valid": bool(verification.get("valid")),
            "status": verification.get("status"),
            "errors": list(verification.get("errors") or []),
            "warnings": list(verification.get("warnings") or []),
            "smoke": {
                "skipped": bool(smoke.get("skipped")),
                "status": smoke.get("status"),
                "returncode": smoke.get("returncode"),
            },
            "runtime": {
                "python_requirement": runtime.get("python_requirement"),
                "python_version": runtime.get("python_version"),
                "interpreter": runtime.get("interpreter"),
                "disposable_stage": bool(runtime.get("disposable_stage")),
            },
        }
        return _check(
            "release_smoke",
            "pass" if verification.get("valid") else "fail",
            required=True,
            summary="Self-contained release tree builds and starts.",
            details=safe_verification,
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
        details.update({"run_id": "rc-fixture-smoke", "missing": missing, "page_count": page_count})
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
    expected_title_contains: str | None = "Retail Transformation Technical Preview Demo",
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


def _bridge_v2_contract_check() -> dict[str, Any]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="dm_rc_bridge_v2_") as tmp:
        run_dir = Path(tmp)
        narrative = {
            "beats": [
                {"beat_id": "beat-001", "role": "opener", "page_title": "Opening", "reuse_query": "opening proof"},
                {"beat_id": "beat-002", "role": "capability_detail", "page_title": "Capability", "reuse_query": "capability proof"},
                {"beat_id": "beat-003", "role": "section_handoff", "page_title": "Transition"},
            ]
        }
        page_tasks = {
            "tasks": [
                {"beat_id": f"beat-00{index}", "page_task_id": f"page-00{index}"}
                for index in range(1, 4)
            ]
        }
        try:
            plan = build_bridge_plan(
                narrative,
                page_tasks,
                run_id="rc-bridge-v2",
                run_mode="production",
            )
            requests = plan.get("requests") if isinstance(plan.get("requests"), list) else []
            if len(requests) != 3:
                failures.append("bridge plan is not per-page")
            if len({item.get("query_trace_id") for item in requests}) != len(requests):
                failures.append("query trace identity is not unique per page")
            strategies = {item.get("role_strategy") for item in requests}
            if not {"passthrough", "mapped", "semantic_only"}.issubset(strategies):
                failures.append("role strategies are incomplete")
            candidate, _ = normalize_candidate(
                {
                    "slide_id": "slide-001",
                    "source_file": "/private/library/private-deck.pptx",
                    "page_number": 7,
                    "title": "Reusable page",
                    "score": 0.9,
                },
                run_dir=run_dir,
                reuse_policy="reuse_or_adapt",
                index=1,
            )
            encoded = json.dumps(candidate, ensure_ascii=False)
            if "source_file" in candidate or "source_path" in candidate:
                failures.append("normalized candidate retains raw source fields")
            if _evidence_safety_violations(encoded):
                failures.append("normalized candidate retains an absolute source path")
            if not candidate.get("asset_key") or not candidate.get("source_asset_id"):
                failures.append("normalized candidate identity is incomplete")
        except Exception as exc:  # noqa: BLE001 - reported as a gate failure.
            failures.append(f"bridge contract check raised {type(exc).__name__}")
    return _check(
        "bridge_v2_contract",
        "pass" if not failures else "fail",
        required=True,
        summary="Bridge v2 per-page policy, identity, and sanitized candidate contract are reproducible.",
        details={"schema_version": "deck_master_ppt_library_selection.v2", "failures": failures},
    )


def _sourcing_v2_contract_check() -> dict[str, Any]:
    failures: list[str] = []
    page_tasks = {
        "tasks": [
            {"beat_id": "beat-001", "page_task_id": "page-001", "page_title": "Page one"},
            {"beat_id": "beat-002", "page_task_id": "page-002", "page_title": "Page two"},
        ]
    }
    shared = {
        "candidate_id": "candidate-shared",
        "slide_id": "slide-shared",
        "asset_key": "canonical:shared",
        "query_trace_id": "query-shared",
        "page_task_id": "page-001",
        "score": 0.9,
        "confidence": 0.9,
        "candidate_origin": "ppt_library",
        "reuse_policy": "reuse_or_adapt",
    }
    second = {**shared, "candidate_id": "candidate-second", "asset_key": "canonical:second", "page_task_id": "page-002", "score": 0.8}
    library_results = {
        "source": "ppt_library",
        "selections": [
            {"beat_id": "beat-001", "page_task_id": "page-001", "query_trace_id": "query-one", "candidates": [shared]},
            {"beat_id": "beat-002", "page_task_id": "page-002", "query_trace_id": "query-two", "candidates": [{**shared, "page_task_id": "page-002"}, second]},
        ],
    }
    try:
        plan = build_sourcing_plan_v2(
            run_id="rc-sourcing-v2",
            page_tasks=page_tasks,
            library_results=library_results,
            permission_default="approved",
        )
        pages = plan.get("pages") if isinstance(plan.get("pages"), list) else []
        if len(pages) != 2 or len({page.get("page_id") for page in pages}) != 2:
            failures.append("pages[] does not contain one decision per page")
        selected_keys = [
            source.get("asset_key")
            for page in pages
            for source in page.get("selected_sources", [])
            if isinstance(source, dict)
        ]
        if len(selected_keys) != len(set(selected_keys)):
            failures.append("selected asset_key values are not globally unique")
        legacy = {"schema_version": "deck_sourcing_plan.v1", "run_id": "legacy-run", "decisions": [{"beat_id": "legacy-001", "source_decision": "generate"}]}
        before = json.dumps(legacy, sort_keys=True)
        migrated = migrate_v1(legacy)
        if migrated.get("schema_version") != "deck_sourcing_plan.v2" or migrated.get("migrated_from") != "deck_sourcing_plan.v1":
            failures.append("legacy v1 migration does not produce canonical v2")
        if json.dumps(legacy, sort_keys=True) != before:
            failures.append("legacy v1 migration modified its input")
    except Exception as exc:  # noqa: BLE001 - reported as a gate failure.
        failures.append(f"sourcing contract check raised {type(exc).__name__}")
    return _check(
        "sourcing_v2_contract",
        "pass" if not failures else "fail",
        required=True,
        summary="Sourcing v2 pages, unique allocation, and read-only v1 migration are reproducible.",
        details={"schema_version": "deck_sourcing_plan.v2", "failures": failures},
    )


def _library_status_v2_contract_check(*, live: bool) -> dict[str, Any]:
    status = inspect_library_status(cache_ttl_seconds=0) if live else inspect_library_status(
        which=lambda _command: None,
        cache_ttl_seconds=0,
    )
    required_fields = {
        "schema_version", "status", "runtime_ready", "contract_ready", "semantic_search_ready",
        "role_selection_ready", "fallback_ready", "preview_ready", "business_ranking_ready",
        "data_hygiene_status", "blocking_summary", "warnings",
    }
    failures: list[str] = []
    if status.get("schema_version") != "deck_master_library_status.v2":
        failures.append("library status schema version is not v2")
    if set(status) != required_fields:
        failures.append("library status fields are inconsistent")
    if live and status.get("status") == "blocked":
        failures.append("live PPT Library status is blocked")
    safe_summary = {
        key: status.get(key)
        for key in (
            "schema_version", "status", "runtime_ready", "contract_ready", "semantic_search_ready",
            "role_selection_ready", "fallback_ready", "preview_ready", "business_ranking_ready",
            "data_hygiene_status", "blocking_summary", "warnings",
        )
    }
    return _check(
        "library_status_v2_contract",
        "pass" if not failures else "fail",
        required=True,
        summary="Library Status v2 fields and readiness truth are consistent.",
        details={"live": live, "status": safe_summary, "failures": failures},
    )


def _strict_fixture_policy_check() -> dict[str, Any]:
    failures: list[str] = []
    for run_mode in ("production", "benchmark"):
        with tempfile.TemporaryDirectory(prefix=f"dm_rc_{run_mode}_fixture_") as tmp:
            run_dir = Path(tmp)
            narrative = {"run_id": f"rc-{run_mode}", "beats": [{"beat_id": "beat-001", "role": "opener", "page_title": "Opening"}]}
            (run_dir / "page_tasks.json").write_text(
                json.dumps({"tasks": [{"beat_id": "beat-001", "page_task_id": "page-001"}]}),
                encoding="utf-8",
            )
            try:
                run_library_selection(
                    narrative_plan=narrative,
                    narrative_plan_path=run_dir / "narrative_plan.json",
                    request={"run_id": f"rc-{run_mode}", "run_mode": run_mode},
                    run_dir=run_dir,
                    mode="fixture",
                )
            except PPTLibraryClientError:
                continue
            failures.append(f"fixture mode was accepted for {run_mode}")
    return _check(
        "strict_fixture_policy",
        "pass" if not failures else "fail",
        required=True,
        summary="Production and benchmark runs reject fixture library selection.",
        details={"modes": ["production", "benchmark"], "failures": failures},
    )


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validated_uat_copy_dir(uat_run_dir: str | Path) -> tuple[Path | None, str | None]:
    raw = Path(uat_run_dir).expanduser()
    raw_absolute = Path(os.path.abspath(raw))
    relative: Path | None = None
    lexical_root: Path | None = None
    resolved_root: Path | None = None
    temp_roots = {
        Path(os.path.abspath(tempfile.gettempdir())),
        Path(os.path.abspath("/tmp")),
    }
    for temp_root in temp_roots:
        for root in (temp_root, temp_root.resolve()):
            try:
                relative = raw_absolute.relative_to(root)
                lexical_root = root
                resolved_root = temp_root.resolve()
                break
            except ValueError:
                continue
        if relative is not None:
            break
    if relative is None or lexical_root is None or resolved_root is None or not relative.parts:
        return None, "UAT_COPY_OUTSIDE_SYSTEM_TEMP"

    current = lexical_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return None, "UAT_COPY_SYMLINK_REJECTED"

    try:
        resolved = raw_absolute.resolve(strict=True)
    except OSError:
        return None, "UAT_COPY_UNAVAILABLE"
    if not resolved.is_dir() or not _path_is_within(resolved, resolved_root):
        return None, "UAT_COPY_OUTSIDE_SYSTEM_TEMP"

    persistent_roots = (
        REPO_ROOT.resolve(),
        Path.home().resolve(),
        (Path.home() / ".deck-master" / "runs").resolve(),
    )
    if any(_path_is_within(resolved, root) for root in persistent_roots):
        return None, "UAT_COPY_PERSISTENT_LOCATION_REJECTED"
    return resolved, None


def _read_uat_json_artifact(
    run_dir: Path,
    candidates: tuple[str, ...],
) -> tuple[dict[str, Any] | None, str | None]:
    for relative in candidates:
        path = run_dir / relative
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink():
            return None, "ARTIFACT_SYMLINK_REJECTED"
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return None, "ARTIFACT_UNAVAILABLE"
        if not _path_is_within(resolved, run_dir) or not resolved.is_file():
            return None, "ARTIFACT_OUTSIDE_UAT_COPY"
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "ARTIFACT_JSON_INVALID"
        return (payload if isinstance(payload, dict) else None), (
            None if isinstance(payload, dict) else "ARTIFACT_JSON_INVALID"
        )
    return None, None


def _uat_copy_symlink_failure(run_dir: Path) -> str | None:
    pending = [run_dir]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        return "UAT_COPY_INTERNAL_SYMLINK_REJECTED"
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
        except OSError:
            return "UAT_COPY_SCAN_FAILED"
    return None


def _artifact_matches_schema(payload: dict[str, Any], schema_name: str) -> bool:
    try:
        import jsonschema  # type: ignore

        schema = json.loads((REPO_ROOT / "docs" / "contracts" / schema_name).read_text(encoding="utf-8"))
    except (ImportError, OSError, json.JSONDecodeError):
        return False
    try:
        jsonschema.Draft202012Validator(schema).validate(payload)
    except jsonschema.ValidationError:
        return False
    return True


def _validate_real_uat_artifacts(run_dir: Path) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    selection, selection_error = _read_uat_json_artifact(
        run_dir,
        (
            "external/ppt_library/library_results.v2.json",
            "library_results/selection.json",
            "ppt-library-selection.json",
            "ppt_library_selection.json",
        ),
    )
    sourcing, sourcing_error = _read_uat_json_artifact(run_dir, ("sourcing_plan.json",))
    summary: dict[str, Any] = {
        "selection_schema": "missing",
        "selection_pages": 0,
        "selection_candidates": 0,
        "sourcing_schema": "missing",
        "sourcing_pages": 0,
        "selected_assets": 0,
        "duplicate_asset_keys": 0,
    }
    selection_task_ids: set[str] = set()
    sourcing_task_ids: set[str] = set()
    selection_pool: dict[tuple[str, str, str], dict[str, Any]] = {}
    selection_asset_pages: dict[str, set[str]] = {}
    selection_page_asset_traces: dict[tuple[str, str], set[str]] = {}

    if selection_error:
        failures.append(f"SELECTION_{selection_error}")
    elif selection is None:
        failures.append("SELECTION_V2_MISSING")
    else:
        summary["selection_schema"] = str(selection.get("schema_version") or "invalid")
        if selection.get("schema_version") != "deck_master_ppt_library_selection.v2":
            failures.append("SELECTION_V2_REQUIRED")
        elif _evidence_safety_violations(json.dumps(selection, ensure_ascii=False)):
            failures.append("SELECTION_UNSAFE_CONTENT")
        elif not validate_library_selection(selection).get("valid"):
            failures.append("SELECTION_V2_INVALID")
        selections = selection.get("selections") if isinstance(selection.get("selections"), list) else []
        summary["selection_pages"] = len(selections)
        identities: set[tuple[str, str]] = set()
        candidate_count = 0
        identity_valid = bool(selections)
        for item in selections:
            if not isinstance(item, dict):
                identity_valid = False
                continue
            beat_id = str(item.get("beat_id") or "")
            page_task_id = str(item.get("page_task_id") or "")
            query_trace_id = str(item.get("query_trace_id") or "")
            identity = (beat_id, page_task_id)
            if not all(identity) or not query_trace_id or identity in identities:
                identity_valid = False
            identities.add(identity)
            if page_task_id:
                selection_task_ids.add(page_task_id)
            candidates = item.get("candidates") if isinstance(item.get("candidates"), list) else []
            candidate_count += len(candidates)
            for candidate in candidates:
                if not isinstance(candidate, dict) or not all(
                    str(candidate.get(field) or "")
                    for field in ("candidate_id", "asset_key", "source_asset_id")
                ):
                    identity_valid = False
                    continue
                candidate_page_task_id = str(candidate.get("page_task_id") or page_task_id)
                candidate_trace_id = str(candidate.get("query_trace_id") or query_trace_id)
                asset_key = str(candidate.get("asset_key") or "")
                if candidate_page_task_id != page_task_id or candidate_trace_id != query_trace_id:
                    identity_valid = False
                pool_key = (candidate_page_task_id, candidate_trace_id, asset_key)
                if pool_key in selection_pool:
                    identity_valid = False
                selection_pool[pool_key] = candidate
                selection_asset_pages.setdefault(asset_key, set()).add(candidate_page_task_id)
                selection_page_asset_traces.setdefault(
                    (candidate_page_task_id, asset_key),
                    set(),
                ).add(candidate_trace_id)
        summary["selection_candidates"] = candidate_count
        if selection.get("schema_version") == "deck_master_ppt_library_selection.v2" and not identity_valid:
            failures.append("SELECTION_IDENTITY_CHAIN_INCOMPLETE")

    if sourcing_error:
        failures.append(f"SOURCING_{sourcing_error}")
    elif sourcing is None:
        failures.append("SOURCING_V2_MISSING")
    else:
        summary["sourcing_schema"] = str(sourcing.get("schema_version") or "invalid")
        if sourcing.get("schema_version") != "deck_sourcing_plan.v2":
            failures.append("SOURCING_V2_REQUIRED")
        elif _evidence_safety_violations(json.dumps(sourcing, ensure_ascii=False)):
            failures.append("SOURCING_UNSAFE_CONTENT")
        elif not _artifact_matches_schema(sourcing, "sourcing-plan.v2.schema.json"):
            failures.append("SOURCING_V2_INVALID")
        pages = sourcing.get("pages") if isinstance(sourcing.get("pages"), list) else []
        summary["sourcing_pages"] = len(pages)
        page_ids: set[str] = set()
        task_ids: set[str] = set()
        asset_keys: list[str] = []
        pages_valid = bool(pages)
        for page in pages:
            if not isinstance(page, dict):
                pages_valid = False
                continue
            page_id = str(page.get("page_id") or "")
            page_task_id = str(page.get("page_task_id") or "")
            if not page_id or not page_task_id or page_id in page_ids or page_task_id in task_ids:
                pages_valid = False
            page_ids.add(page_id)
            task_ids.add(page_task_id)
            if page_task_id:
                sourcing_task_ids.add(page_task_id)
            sources = page.get("selected_sources") if isinstance(page.get("selected_sources"), list) else []
            for source in sources:
                asset_key = str(source.get("asset_key") or "") if isinstance(source, dict) else ""
                if not asset_key:
                    pages_valid = False
                    continue
                asset_keys.append(asset_key)
                source_page_task_id = str(source.get("page_task_id") or "")
                source_trace_id = str(source.get("query_trace_id") or "")
                if source_page_task_id != page_task_id:
                    failures.append("SOURCING_SELECTION_CROSS_PAGE")
                    continue
                candidate = selection_pool.get((source_page_task_id, source_trace_id, asset_key))
                if candidate is None:
                    known_pages = selection_asset_pages.get(asset_key, set())
                    if asset_key in selection_asset_pages and source_page_task_id not in known_pages:
                        failures.append("SOURCING_SELECTION_CROSS_PAGE")
                    elif selection_page_asset_traces.get((source_page_task_id, asset_key)):
                        failures.append("SOURCING_SELECTION_TRACE_MISMATCH")
                    else:
                        failures.append("SOURCING_SELECTION_CANDIDATE_MISSING")
                    continue
                for field in ("candidate_id", "source_asset_id", "slide_id"):
                    selected_value = source.get(field)
                    if selected_value not in {None, ""} and selected_value != candidate.get(field):
                        failures.append("SOURCING_SELECTION_IDENTITY_MISMATCH")
        duplicate_count = len(asset_keys) - len(set(asset_keys))
        summary["selected_assets"] = len(asset_keys)
        summary["duplicate_asset_keys"] = duplicate_count
        if sourcing.get("schema_version") == "deck_sourcing_plan.v2" and not pages_valid:
            failures.append("SOURCING_PAGE_DECISIONS_INVALID")
        if duplicate_count:
            failures.append("SOURCING_DUPLICATE_ASSET_KEY")

    if selection_task_ids and sourcing_task_ids and selection_task_ids != sourcing_task_ids:
        failures.append("UAT_PAGE_IDENTITY_MISMATCH")

    return summary, sorted(set(failures))


def _real_workflow_uat_check(uat_run_dir: str | Path | None) -> dict[str, Any]:
    if not uat_run_dir:
        return _check(
            "real_workflow_uat",
            "fail",
            required=True,
            summary="Full tier requires an explicit real UAT run copy.",
            details={"uat_status": "missing", "failures": ["UAT_RUN_REQUIRED"]},
        )
    run_dir, copy_error = _validated_uat_copy_dir(uat_run_dir)
    if copy_error or run_dir is None:
        return _check(
            "real_workflow_uat",
            "fail",
            required=True,
            summary="Full-tier UAT requires an isolated, non-symlinked system-temp copy.",
            details={"uat_status": "blocked", "failures": [copy_error or "UAT_COPY_INVALID"]},
        )
    symlink_failure = _uat_copy_symlink_failure(run_dir)
    if symlink_failure:
        return _check(
            "real_workflow_uat",
            "fail",
            required=True,
            summary="Full-tier UAT rejects symlinks anywhere inside the run copy.",
            details={"uat_status": "blocked", "failures": [symlink_failure]},
        )
    artifacts, artifact_failures = _validate_real_uat_artifacts(run_dir)
    if artifact_failures:
        return _check(
            "real_workflow_uat",
            "fail",
            required=True,
            summary="Real UAT artifacts do not satisfy the v2 release contract.",
            details={"uat_status": "blocked", "artifacts": artifacts, "failures": artifact_failures},
        )
    try:
        report = run_real_workflow_smoke(run_dir, write=False)
    except Exception as exc:  # noqa: BLE001 - report only the stable exception type.
        return _check(
            "real_workflow_uat",
            "fail",
            required=True,
            summary="Real workflow UAT could not be evaluated.",
            details={"uat_status": "error", "artifacts": artifacts, "failures": [type(exc).__name__]},
        )
    uat_status = str(report.get("status") or "")
    phases = report.get("phases") if isinstance(report.get("phases"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    passed = uat_status == "pass" and all(value == "pass" for value in phases.values())
    return _check(
        "real_workflow_uat",
        "pass" if passed else "fail",
        required=True,
        summary="Real workflow UAT must pass without warnings in the full tier.",
        details={
            "uat_status": uat_status or "invalid",
            "artifacts": artifacts,
            "phases": {str(key): str(value) for key, value in phases.items()},
            "summary": {
                key: int(summary.get(key) or 0)
                for key in ("checks", "passed", "warnings", "failed")
            },
        },
    )


def _external_dependency_closure_ci_check() -> dict[str, Any]:
    """CI-tier external dependency closure.

    Verifies the release tree's capability lock is well-formed and carries an
    external dependency snapshot, which is reproducible from a fresh clone
    (``build_release_tree`` works entirely from committed source). Skips the
    live production-backend binding assertion and the benchmark readiness gate,
    which both require local-only state (a bound ``ppt-master`` backend and
    local-only benchmark results). The full tier runs those; CI does not.
    """
    failures: list[str] = []
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
    except Exception as exc:  # noqa: BLE001 - RC gate reports closure errors as check details.
        failures.append(f"capability lock could not be built: {exc}")

    return _check(
        "external_dependency_closure",
        "pass" if not failures else "fail",
        required=True,
        summary="CI tier: release capability lock is well-formed (live backend binding and benchmark gates skipped).",
        details={
            "tier": "ci",
            "capability_lock_dependencies": lock_snapshot,
            "skipped": [
                "ppt-master bound_verified assertion (requires locally-bound backend)",
                "benchmark aggregate report_ready gate (requires local-only results)",
            ],
            "failures": failures,
        },
    )


def _dependency_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for item in items:
        if item.get("name") == name:
            return item
    return {}


def _dependency_snapshot(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    item = _dependency_by_name(items, "ppt-master")
    snapshot["ppt-master"] = {
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

    if backend.get("binding_status") not in {"bound_verified", "bound_verified_runtime_blocked"} or not backend.get("verified"):
        failures.append("ppt-master is not bound_verified")
    if not str(backend.get("git_sha") or ""):
        failures.append("ppt-master git_sha is missing")
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
        summary="External production backend, release lock, and benchmark closure are verified.",
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
    tier: str = "full",
    uat_run_dir: str | Path | None = None,
) -> dict[str, Any]:
    if tier not in {"ci", "full"}:
        raise RCGateError("tier must be 'ci' or 'full'.")
    bench_root = Path(benchmark_dir).expanduser().resolve() if benchmark_dir else REPO_ROOT / "benchmarks"
    if tier == "ci":
        # CI tier: skip checks that need local-only state. benchmark_aggregate
        # needs gitignored benchmarks/results/; the live closure needs a
        # locally-bound ppt-master backend. The CI closure still verifies the
        # release tree's capability lock is well-formed (reproducible from a
        # fresh clone). benchmark_report is computed for visibility only.
        benchmark_summary = {
            "status": "skipped",
            "min_real_cases": min_real_cases,
            "case_counts": {},
            "report_counts": {},
            "private_source_policy": {},
            "metrics": {},
        }
        benchmark_check = _check(
            "benchmark_aggregate",
            "skipped",
            required=False,
            summary="Skipped in CI tier: requires local-only benchmark results.",
            details=benchmark_summary,
        )
        closure_check = _external_dependency_closure_ci_check()
        library_status_check = _library_status_v2_contract_check(live=False)
        full_only_checks: list[dict[str, Any]] = []
    else:
        benchmark_report = build_benchmark_aggregate_report(bench_root, min_real_cases=min_real_cases)
        benchmark_summary = _safe_benchmark_summary(benchmark_report)
        benchmark_check = _check(
            "benchmark_aggregate",
            "pass" if benchmark_report["status"] == "report_ready" else "fail",
            required=True,
            summary="Benchmark aggregate requires real completed benchmark reports for RC.",
            details=benchmark_summary,
        )
        closure_check = _external_dependency_closure_check(benchmark_report)
        library_status_check = _library_status_v2_contract_check(live=True)
        full_only_checks = [_real_workflow_uat_check(uat_run_dir)]
    checks = [
        _json_parse_check(),
        _artifact_validator_check(),
        _release_smoke_check(),
        _fixture_e2e_check(),
        _bridge_v2_contract_check(),
        _sourcing_v2_contract_check(),
        library_status_check,
        _strict_fixture_policy_check(),
        _browser_smoke_check(skip=skip_browser_smoke, require=require_browser_smoke),
        benchmark_check,
        closure_check,
        *full_only_checks,
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
        "tier": tier,
        "created_at": _utc_now(),
        "benchmark_dir": "repository-benchmarks" if bench_root == (REPO_ROOT / "benchmarks").resolve() else "external-benchmark-evidence",
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
        f"- Tier: `{report.get('tier', 'full')}`",
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
    tier: str = "full",
    uat_run_dir: str | Path | None = None,
    evidence_forbidden_markers: list[str] | tuple[str, ...] | None = None,
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
        tier=tier,
        uat_run_dir=uat_run_dir,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(json_path, report)
    markdown_path.write_text(render_rc_gate_markdown(report), encoding="utf-8")
    json_text = json_path.read_text(encoding="utf-8")
    markdown_text = markdown_path.read_text(encoding="utf-8")
    violations = _evidence_safety_violations(
        json_text,
        markdown_text,
        forbidden_markers=evidence_forbidden_markers,
    )
    if violations:
        json_path.unlink(missing_ok=True)
        markdown_path.unlink(missing_ok=True)
        raise RCGateError(f"RC evidence safety scan failed: {', '.join(violations)}")
    return {
        "status": report["status"],
        "report": str(json_path),
        "markdown": str(markdown_path),
        "summary": report["summary"],
    }
