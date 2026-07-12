from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import sys
from typing import Any
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from manifest import (
    DECISIONS,
    ManifestError,
    find_page,
    load_manifest,
    load_quality_reports,
    page_payload,
    preview_file_path,
    update_page_decision,
)

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runtime.events import append_typed_event
from runtime.import_log import summarize_import_log
from runtime.setup_status import configured_runs_dir, read_setup_config, setup_status
from runtime.library_status import inspect_library_status
from runtime.orchestration import orchestration_check
from runtime.next_step import resolve_next_step
from runtime.final_readiness import final_readiness_clearance
from runtime.run_state_resolver import resolve_run_state
from skills.installer import inspect_suite_status

from review.readiness import (
    compute_claim_coverage,
    compute_deck_readiness,
    compute_next_actions,
    summarize_sourcing_readiness,
)
from review.workbench import WorkbenchError, execute_review_action
from workspace_api import (
    build_delivery_preview_payload,
    build_workspace_activity_payload,
    build_workspace_page_payload,
    build_workspace_payload,
    handle_workspace_page_action,
    handle_workspace_run_action,
    skill_os_accept_handoff,
    skill_os_projection,
    skill_os_reject_handoff,
)

from delivery.outcome import record_delivery_outcome
from delivery.validate import validate_delivery
from feedback.library_feedback import summarize_library_feedback_events
from metrics.run_metrics import summarize_run_metrics
from orchestrate.export_queue import export_queue, has_client_export_quality_clearance
from generation.task_builder import create_generation_tasks
from orchestrate.preview_builder import build_preview_from_sourcing
from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from planning.sourcing_decider import decide_sourcing
from quality.overrides import create_override, list_active_overrides, load_overrides, revoke_override
from runtime.run_state import NARRATIVE_PLAN_NAME, SOURCING_PLAN_NAME, create_run, load_request, read_json, run_status, write_artifact
from tools.ppt_library_client import run_library_selection


STATIC_DIR = Path(__file__).parent / "static"
WRITE_TOKEN_ENV = "DECK_MASTER_REVIEW_WRITE_TOKEN"
WRITE_TOKEN_HEADER = "X-Deck-Master-Write-Token"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
REMOTE_PREVIEW_WARNING = (
    "WARNING: Review Desk write token is a local preview guard, not a network "
    "authentication boundary. Anyone who can load the page can read the token."
)


def is_loopback_bind_host(host: str) -> bool:
    text = str(host or "").strip().lower()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return text in LOOPBACK_HOSTS


def validate_preview_bind_host(host: str, *, allow_remote_preview: bool = False) -> str:
    if is_loopback_bind_host(host):
        return ""
    if allow_remote_preview:
        return REMOTE_PREVIEW_WARNING
    raise ValueError(
        "Refusing to bind Review Desk to a non-loopback host. Use "
        "--allow-remote-preview only for trusted local-network demos."
    )


def _load_narrative_data(run_dir: Path) -> dict:
    """加载 narrative review 所需数据。"""
    data: dict[str, object] = {}

    brief_path = run_dir / "deck_brief.json"
    if brief_path.exists():
        try:
            data["deck_brief"] = json.loads(brief_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data["deck_brief"] = {}

    judgments_path = run_dir / "consulting_judgments.json"
    if judgments_path.exists():
        try:
            data["judgments"] = json.loads(judgments_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data["judgments"] = {}

    graph_path = run_dir / "claim_evidence_graph.json"
    if graph_path.exists():
        try:
            data["claim_graph"] = json.loads(graph_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data["claim_graph"] = {}

    claim_path = run_dir / "claim_map.json"
    if claim_path.exists():
        try:
            data["claim_map"] = json.loads(claim_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data["claim_map"] = {}

    return data


def _load_asset_signals(run_dir: Path) -> dict:
    """加载 asset signals 数据。"""
    signals: dict[str, object] = {}

    # 尝试从 workspace 读取 asset graph
    request_path = run_dir / "request.json"
    workspace_dir = ""
    if request_path.exists():
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            workspace_dir = request.get("workspace", "")
        except json.JSONDecodeError:
            pass

    if workspace_dir:
        ws = Path(workspace_dir)
        # 读取 asset graph
        graph_path = ws / "assets" / "asset_graph.json"
        if graph_path.exists():
            try:
                signals["asset_graph"] = json.loads(graph_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                signals["asset_graph"] = {}

        # 读取 asset feedback
        feedback_path = ws / "assets" / "asset_feedback.jsonl"
        if feedback_path.exists():
            feedback = []
            for line in feedback_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        feedback.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            signals["feedback"] = feedback

    # 读取 sourcing plan 获取 candidate scores
    sourcing_path = run_dir / "sourcing_plan.json"
    if sourcing_path.exists():
        try:
            signals["sourcing_plan"] = json.loads(sourcing_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return signals


def _quality_blocking_summary(run_dir: Path) -> dict[str, Any]:
    quality_dir = run_dir / "quality_reports"
    summary = {
        "schema_version": "deck_master_quality_blocking_summary.v1",
        "reports": 0,
        "blocking_reports": 0,
        "p0": 0,
        "p1": 0,
        "p2": 0,
        "delivery_blocked": False,
    }
    if not quality_dir.exists():
        return summary
    for gate_file in sorted(quality_dir.glob("*_gate.json")):
        try:
            report = json.loads(gate_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(report, dict):
            continue
        summary["reports"] += 1
        report_summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        summary["p0"] += int(report_summary.get("p0_count") or 0)
        summary["p1"] += int(report_summary.get("p1_count") or 0)
        summary["p2"] += int(report_summary.get("p2_count") or 0)
        if (
            report.get("blocks_delivery")
            or report.get("status") == "rework_required"
            or int(report_summary.get("p0_count") or 0)
            or int(report_summary.get("p1_count") or 0)
        ):
            summary["blocking_reports"] += 1
    summary["delivery_blocked"] = bool(summary["p0"] or summary["p1"] or summary["blocking_reports"])
    return summary


def _runtime_readiness_payload(run_dir: Path) -> dict[str, Any]:
    suite_readiness = inspect_suite_status(targets=["codex"], include_optional=True)
    return {
        "schema_version": "deck_master_runtime_readiness.v1",
        "run_id": run_dir.name,
        "suite_readiness": suite_readiness,
        "library_status": suite_readiness.get("library_status", {}),
        "sourcing_readiness": summarize_sourcing_readiness(run_dir),
        "imports_summary": summarize_import_log(run_dir),
        "quality_blocking_summary": _quality_blocking_summary(run_dir),
        "feedback_pending_summary": summarize_library_feedback_events(run_dir),
    }


class PreviewHandler(BaseHTTPRequestHandler):
    run_dir: Path | None = None
    runs_dir: Path
    library_mode: str = "fixture"
    use_setup_runs_dir: bool = False
    write_token: str = ""

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def studio_runs_dir(self) -> Path:
        if self.run_dir is not None or not self.use_setup_runs_dir:
            return self.runs_dir.resolve()
        config = read_setup_config()
        if isinstance(config, dict) and not config.get("_invalid") and config.get("default_runs_dir"):
            return Path(str(config["default_runs_dir"])).expanduser().resolve()
        return self.runs_dir.resolve()

    def run_title(self, run_dir: Path) -> str:
        try:
            request = load_request(run_dir)
        except ValueError:
            return run_dir.name
        return str(request.get("project_name") or request.get("business_goal") or run_dir.name)

    def preview_manifest_exists(self, run_dir: Path) -> bool:
        return (run_dir / "preview_manifest.json").exists()

    def preview_not_ready_payload(self, run_dir: Path) -> dict[str, Any]:
        return {
            "run_id": run_dir.name,
            "title": self.run_title(run_dir),
            "status": run_status(run_dir),
            "updated_at": "",
            "quality": {},
            "pages": [],
            "preview_ready": False,
            "message": "Preview is not ready yet.",
        }

    def public_manifest_error(self, exc: Exception) -> str:
        message = str(exc)
        if "Missing preview_manifest.json" in message:
            return "Preview is not ready yet."
        if "Invalid JSON in preview_manifest.json" in message:
            return "Preview manifest is invalid."
        return message

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/":
            self.serve_static("index.html")
            return
        if path.startswith("/static/"):
            self.serve_static(path.removeprefix("/static/"))
            return
        if path == "/api/deck":
            self.api_deck(parsed)
            return
        if path == "/api/runs":
            self.api_runs()
            return
        if path.startswith("/api/page/"):
            self.api_page(path.removeprefix("/api/page/"), parsed)
            return
        if path.startswith("/api/workspace/"):
            self.api_workspace(path.removeprefix("/api/workspace/"), parsed)
            return
        if path.startswith("/delivery-preview/"):
            self.serve_delivery_preview(path.removeprefix("/delivery-preview/").strip("/"), parsed)
            return
        if path.startswith("/api/narrative/"):
            self.api_narrative(path.removeprefix("/api/narrative/").strip("/"))
            return
        if path.startswith("/api/asset-signals/"):
            self.api_asset_signals(path.removeprefix("/api/asset-signals/").strip("/"))
            return
        if path.startswith("/api/quality-governance/"):
            self.api_quality_governance(path.removeprefix("/api/quality-governance/").strip("/"))
            return
        if path.startswith("/api/readiness/"):
            self.api_review_summary(path.removeprefix("/api/readiness/").strip("/"))
            return
        if path.startswith("/api/review-summary/"):
            self.api_review_summary(path.removeprefix("/api/review-summary/").strip("/"))
            return
        if path.startswith("/api/claim-coverage/"):
            self.api_claim_coverage(path.removeprefix("/api/claim-coverage/").strip("/"))
            return
        if path.startswith("/api/next-actions/"):
            self.api_next_actions(path.removeprefix("/api/next-actions/").strip("/"))
            return
        if path == "/api/setup-status":
            self.api_setup_status(parsed)
            return
        if path.startswith("/api/run-state/"):
            self.api_run_state(path.removeprefix("/api/run-state/").strip("/"), parsed)
            return
        if path.startswith("/api/workflow-status/"):
            self.api_workflow_status(path.removeprefix("/api/workflow-status/").strip("/"), parsed)
            return
        if path.startswith("/api/workflow-handoffs/"):
            self.api_workflow_handoffs(path.removeprefix("/api/workflow-handoffs/").strip("/"), parsed)
            return
        if path.startswith("/api/workflow-questions/"):
            self.api_workflow_questions(path.removeprefix("/api/workflow-questions/").strip("/"), parsed)
            return
        if path.startswith("/api/external-results/"):
            self.api_external_results(path.removeprefix("/api/external-results/").strip("/"))
            return
        if path.startswith("/api/runtime-readiness/"):
            self.api_runtime_readiness(path.removeprefix("/api/runtime-readiness/").strip("/"))
            return
        if path.startswith("/api/export-queue/"):
            self.api_export_queue(path.removeprefix("/api/export-queue/").strip("/"), parsed)
            return
        if path.startswith("/api/metrics/"):
            self.api_run_metrics(path.removeprefix("/api/metrics/").strip("/"))
            return
        if path.startswith("/api/run-metrics/"):
            self.api_run_metrics(path.removeprefix("/api/run-metrics/").strip("/"))
            return
        if path.startswith("/preview/"):
            self.serve_preview(path.removeprefix("/preview/"), parsed)
            return

        self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found.")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if not self.write_guard_allows_request():
            return
        if path == "/api/runs":
            self.api_create_run()
            return
        if path.startswith("/api/page/") and path.endswith("/decision"):
            page_id = path.removeprefix("/api/page/").removesuffix("/decision").strip("/")
            self.api_update_decision(page_id, parsed)
            return
        if path.startswith("/api/page/") and path.endswith("/review-action"):
            page_id = path.removeprefix("/api/page/").removesuffix("/review-action").strip("/")
            self.api_review_action(page_id, parsed)
            return
        if path.startswith("/api/workspace/"):
            self.api_workspace_post(path.removeprefix("/api/workspace/"), parsed)
            return
        if path.startswith("/api/workflow-handoff/") and path.endswith("/accept"):
            run_id = path.removeprefix("/api/workflow-handoff/").removesuffix("/accept").strip("/")
            self.api_workflow_handoff_decide(run_id, parsed, decision="accept")
            return
        if path.startswith("/api/workflow-handoff/") and path.endswith("/reject"):
            run_id = path.removeprefix("/api/workflow-handoff/").removesuffix("/reject").strip("/")
            self.api_workflow_handoff_decide(run_id, parsed, decision="reject")
            return
        if path.startswith("/api/workflow-autopilot/") and path.endswith("/resume"):
            run_id = path.removeprefix("/api/workflow-autopilot/").removesuffix("/resume").strip("/")
            self.api_workflow_autopilot_resume(run_id, parsed)
            return
        if path == "/api/override/create":
            self.api_override_create(parsed)
            return
        if path == "/api/override/revoke":
            self.api_override_revoke(parsed)
            return
        if path == "/api/delivery/mark-delivered":
            self.api_delivery_mark_delivered(parsed)
            return
        if path == "/api/delivery/record-reaction":
            self.api_delivery_record_reaction(parsed)
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found.")

    def header_value(self, name: str) -> str:
        value = self.headers.get(name, "")
        if value:
            return str(value)
        lowered = name.lower()
        for key, candidate in getattr(self.headers, "items", lambda: [])():
            if str(key).lower() == lowered:
                return str(candidate)
        return ""

    def write_guard_allows_request(self) -> bool:
        expected = str(getattr(self, "write_token", "") or "")
        supplied = self.header_value(WRITE_TOKEN_HEADER)
        if not expected or not secrets.compare_digest(supplied, expected):
            self.send_error_json(HTTPStatus.FORBIDDEN, "Write token is required for Review Desk mutations.")
            return False
        if not self.same_origin_or_local_request():
            self.send_error_json(HTTPStatus.FORBIDDEN, "Write request origin is not allowed.")
            return False
        return True

    def same_origin_or_local_request(self) -> bool:
        origin = self.header_value("Origin") or self.header_value("Referer")
        if not origin:
            return True
        parsed = urlparse(origin)
        if not parsed.scheme or not parsed.netloc:
            return False
        origin_host = str(parsed.hostname or "").lower()
        origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host_header = self.header_value("Host")
        if host_header:
            host, port = self.split_host_port(host_header)
            if parsed.netloc == host_header:
                return True
            return host in LOOPBACK_HOSTS and origin_host in LOOPBACK_HOSTS and (port is None or port == origin_port)
        return origin_host in LOOPBACK_HOSTS

    def split_host_port(self, value: str) -> tuple[str, int | None]:
        text = value.strip()
        if text.startswith("[") and "]" in text:
            host, _, raw_port = text[1:].partition("]")
            raw_port = raw_port.removeprefix(":")
        elif text.count(":") == 1:
            host, raw_port = text.rsplit(":", 1)
        else:
            host, raw_port = text, ""
        try:
            port = int(raw_port) if raw_port else None
        except ValueError:
            port = None
        return host.lower(), port

    def active_run_dir(self, parsed) -> Path:
        if self.run_dir is not None:
            return self.run_dir
        params = parse_qs(parsed.query)
        run_id = (params.get("run_id") or params.get("run") or [""])[0].strip()
        if not run_id:
            raise ManifestError("run_id is required in studio mode.")
        runs_dir = self.studio_runs_dir()
        candidate = (runs_dir / run_id).resolve()
        root_text = str(runs_dir.resolve())
        candidate_text = str(candidate)
        if candidate_text != root_text and not candidate_text.startswith(root_text + "/"):
            raise ManifestError("Invalid run_id.")
        if not candidate.is_dir():
            raise ManifestError(f"Run not found: {run_id}")
        return candidate

    def run_summary(self, run_dir: Path) -> dict:
        title = run_dir.name
        pages = 0
        decisions: dict[str, int] = {}
        stage_label = ""
        stage_tone = "muted"
        pending_approvals = 0
        try:
            manifest = load_manifest(run_dir)
            title = manifest.get("title", title)
            pages = len(manifest["pages"])
            for page in manifest["pages"]:
                decision = page.get("decision", "needs_review")
                decisions[decision] = decisions.get(decision, 0) + 1
        except ManifestError:
            try:
                request = load_request(run_dir)
                title = request.get("project_name", title)
            except ValueError:
                title = run_dir.name
        try:
            workspace = build_workspace_payload(run_dir)
            stage_label = str((workspace.get("stage") or {}).get("label") or "")
            stage_tone = str((workspace.get("stage") or {}).get("tone") or "muted")
            pending_approvals = int((workspace.get("header_metrics") or {}).get("pending_approvals") or 0)
        except Exception:
            pass
        return {
            "run_id": run_dir.name,
            "title": title,
            "status": run_status(run_dir),
            "pages": pages,
            "decisions": decisions,
            "stage_label": stage_label,
            "stage_tone": stage_tone,
            "pending_approvals": pending_approvals,
        }

    def api_runs(self) -> None:
        if self.run_dir is not None:
            self.send_json(
                {
                    "runs_dir": str(self.run_dir.parent.resolve()),
                    "runs": [self.run_summary(self.run_dir)],
                }
            )
            return
        runs_dir = self.studio_runs_dir()
        runs_dir.mkdir(parents=True, exist_ok=True)
        runs = [
            self.run_summary(child)
            for child in sorted(runs_dir.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
            if child.is_dir()
        ]
        self.send_json({"runs_dir": str(runs_dir), "runs": runs})

    def api_deck(self, parsed) -> None:
        try:
            run_dir = self.active_run_dir(parsed)
            if not self.preview_manifest_exists(run_dir):
                self.send_json(self.preview_not_ready_payload(run_dir))
                return
            manifest = load_manifest(run_dir)
            pages = [page_payload(run_dir, page) for page in manifest["pages"]]
            self.send_json(
                {
                    "run_id": manifest["run_id"],
                    "title": manifest["title"],
                    "status": manifest["status"],
                    "updated_at": manifest.get("updated_at", ""),
                    "quality": load_quality_reports(run_dir),
                    "pages": pages,
                    "preview_ready": True,
                }
            )
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, self.public_manifest_error(exc))

    def api_page(self, page_id: str, parsed) -> None:
        try:
            run_dir = self.active_run_dir(parsed)
            manifest = load_manifest(run_dir)
            page = find_page(manifest, page_id)
            self.send_json(page_payload(run_dir, page))
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))

    def api_workspace(self, path_suffix: str, parsed) -> None:
        parts = [part for part in path_suffix.strip("/").split("/") if part]
        if not parts:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "run_id is required.")
            return

        run_id = parts[0]
        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return

        try:
            if len(parts) == 1:
                self.send_json(build_workspace_payload(run_dir))
                return
            if len(parts) == 2 and parts[1] == "activity":
                self.send_json(build_workspace_activity_payload(run_dir))
                return
            if len(parts) == 2 and parts[1] == "delivery-preview":
                self.send_json(build_delivery_preview_payload(run_dir))
                return
            if len(parts) == 2 and parts[1] == "skill-os":
                self.send_json(skill_os_projection(run_dir))
                return
            if len(parts) == 3 and parts[1] == "page":
                self.send_json(build_workspace_page_payload(run_dir, parts[2]))
                return
            self.send_error_json(HTTPStatus.NOT_FOUND, "Workspace route not found.")
        except (ManifestError, ValueError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_workspace_post(self, path_suffix: str, parsed) -> None:
        parts = [part for part in path_suffix.strip("/").split("/") if part]
        if not parts:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "run_id is required.")
            return
        run_id = parts[0]
        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return
        body = self.read_json_body()
        try:
            if len(parts) == 2 and parts[1] == "actions":
                self.send_json(handle_workspace_run_action(run_dir, body))
                return
            if len(parts) == 4 and parts[1] == "page" and parts[3] == "actions":
                self.send_json(handle_workspace_page_action(run_dir, parts[2], body))
                return
            self.send_error_json(HTTPStatus.NOT_FOUND, "Workspace route not found.")
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    # --- Skill OS HTTP routes (08-review-desk-integration.md §3) ---

    def api_workflow_status(self, run_id: str, parsed) -> None:
        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return
        try:
            self.send_json(skill_os_projection(run_dir))
        except (ManifestError, ValueError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_workflow_handoffs(self, run_id: str, parsed) -> None:
        from workflow.handoff import HandoffRuntime

        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return
        try:
            rt = HandoffRuntime()
            self.send_json({"handoffs": rt.list(run_dir), "current": rt.current(run_dir)})
        except (ManifestError, ValueError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_workflow_questions(self, run_id: str, parsed) -> None:
        from workflow.questions import QuestionResolver

        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return
        params = parse_qs(parsed.query)
        stage = (params.get("stage") or [""])[0].strip()
        if not stage:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "stage query param is required.")
            return
        try:
            qr = QuestionResolver()
            gaps = [g.__dict__ for g in qr.gaps(run_dir, stage)]
            self.send_json({
                "stage_id": stage,
                "gaps": gaps,
                "blocking": [g["question_id"] for g in gaps if g.get("required")],
                "pending_questions_count": len(gaps),
            })
        except (ManifestError, ValueError, KeyError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_workflow_handoff_decide(self, run_id: str, parsed, *, decision: str) -> None:
        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return
        body = self.read_json_body()
        handoff_id = str(body.get("handoff_id") or "").strip()
        actor = str(body.get("actor") or body.get("actor_id") or "review-desk").strip()
        if not handoff_id:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "handoff_id is required.")
            return
        try:
            if decision == "accept":
                self.send_json(skill_os_accept_handoff(run_dir, handoff_id, actor=actor))
            else:
                reason = str(body.get("reason") or "rejected from review desk").strip()
                repair_owner = str(body.get("repair_owner_stage") or "").strip()
                self.send_json(skill_os_reject_handoff(
                    run_dir, handoff_id, actor=actor, reason=reason, repair_owner_stage=repair_owner,
                ))
        except (ManifestError, ValueError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_workflow_autopilot_resume(self, run_id: str, parsed) -> None:
        from workflow.autopilot import AutopilotV2

        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return
        body = self.read_json_body() or {}
        mode = str(body.get("mode") or "interactive").strip()
        max_steps = int(body.get("max_steps") or 6)
        try:
            result = AutopilotV2().run(run_dir, mode=mode, max_steps=max_steps, run_id=run_id)
            self.send_json({
                "mode": result.mode,
                "stop_reason": result.stop_reason,
                "final_stage": result.final_stage,
                "steps": [s.__dict__ for s in result.steps],
            })
        except (ManifestError, ValueError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_create_run(self) -> None:
        try:
            body = self.read_json_body()
            run_mode = self._coerce_run_mode(body)
            request = build_request(
                brief=body.get("brief", ""),
                brief_file=None,
                industry=body.get("industry", ""),
                target_pages=body.get("target_pages", "auto"),
                audience=body.get("audience", "client"),
                style_preference=body.get("style_preference", ""),
                run_id=body.get("run_id", ""),
            )
            request["run_mode"] = run_mode

            setup = None
            workspace = None
            runs_dir = self.runs_dir
            if run_mode == "production":
                setup = setup_status(workspace=str(body.get("workspace") or None) if body.get("workspace") else None)
                if not self._is_setup_ready_for_production(setup):
                    self.send_error_json(
                        HTTPStatus.CONFLICT,
                        "Setup is not ready for production runs. Complete setup before creating a production project.",
                    )
                    return
                cfg = setup.get("config") if isinstance(setup.get("config"), dict) else {}
                runs_dir = Path(str(cfg.get("default_runs_dir") or self.runs_dir)).expanduser().resolve()
                workspace_report = setup.get("workspace") if isinstance(setup.get("workspace"), dict) else {}
                workspace = str(workspace_report.get("workspace_dir") or cfg.get("active_workspace") or "").strip()
            else:
                requested_runs_dir = body.get("runs_dir")
                if requested_runs_dir:
                    runs_dir = Path(str(requested_runs_dir)).expanduser().resolve()

            self.runs_dir = runs_dir

            request = self._write_workspace_runtime_fields(
                request,
                run_mode=run_mode,
                workspace=workspace,
                runs_dir=runs_dir,
            )
            run_dir = create_run(runs_dir, request, run_id=body.get("run_id") or None, force=bool(body.get("force")))
            request = load_request(run_dir)
            if run_mode == "production":
                run_state = resolve_run_state(run_dir, run_mode=run_mode)
                self.send_json(
                    {
                        "run_id": request["run_id"],
                        "run_dir": str(run_dir),
                        "status": run_state.get("stage") or "needs_context",
                        "run_state": run_state,
                        "summary": self.run_summary(run_dir),
                    },
                    HTTPStatus.CREATED,
                )
                return

            narrative_plan = plan_narrative(request)
            write_artifact(run_dir, NARRATIVE_PLAN_NAME, narrative_plan, action="narrative.plan.created")
            library_results = run_library_selection(
                narrative_plan=narrative_plan,
                narrative_plan_path=run_dir / NARRATIVE_PLAN_NAME,
                request=request,
                run_dir=run_dir,
                mode=body.get("library_mode", self.library_mode),
                command=body.get("ppt_lib_command", "ppt-lib"),
            )
            sourcing_plan = decide_sourcing(narrative_plan, library_results)
            write_artifact(run_dir, SOURCING_PLAN_NAME, sourcing_plan, action="sourcing.plan.created")
            generation_tasks = create_generation_tasks(sourcing_plan, run_dir)
            manifest = build_preview_from_sourcing(sourcing_plan, run_dir, generation_tasks)
            self.send_json(
                {
                    "run_id": request["run_id"],
                    "run_dir": str(run_dir),
                    "status": "preview_ready",
                    "pages": len(manifest["pages"]),
                    "summary": self.run_summary(run_dir),
                },
                HTTPStatus.CREATED,
            )
        except (ValueError, ManifestError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_setup_status(self, parsed) -> None:
        params = parse_qs(parsed.query)
        workspace = (params.get("workspace") or [None])[0]
        payload = setup_status(workspace=workspace, include_suite=True)
        self.send_json(self._adapt_setup_status(payload))

    def api_run_state(self, run_id: str, parsed) -> None:
        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if run_dir is None:
            return
        request = {}
        try:
            request = load_request(run_dir)
        except (ValueError, ManifestError):
            request = {}

        orchestration = orchestration_check(run_dir)
        next_step = resolve_next_step(run_dir)
        self.send_json(
            {
                "schema_version": "deck_run_state.v1",
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "status": run_status(run_dir),
                "stage": next_step.get("status", ""),
                "orchestration": orchestration,
                "next_step": next_step,
                "next_command": next_step.get("next_command", ""),
                "recommended_skill": next_step.get("recommended_skill", ""),
                "skill_stage": next_step.get("skill_stage", ""),
                "skill_route": next_step.get("skill_route", {}),
                "run_mode": request.get("run_mode", ""),
                "workspace": request.get("workspace", ""),
            }
        )

    def _coerce_run_mode(self, body: dict[str, object]) -> str:
        run_mode = str(body.get("run_mode") or body.get("run-mode") or "").strip().lower()
        if run_mode:
            return run_mode

        library_mode = str(body.get("library_mode") or "").strip().lower()
        planning_mode = str(body.get("planning_mode") or "").strip().lower()
        if library_mode == "fixture" or planning_mode == "classic":
            return "fixture"
        return "production"

    def _is_setup_ready_for_production(self, payload: dict[str, Any]) -> bool:
        if payload.get("status") != "ready":
            return False
        workspace = payload.get("workspace")
        return isinstance(workspace, dict) and workspace.get("status") == "valid"

    @staticmethod
    def _as_bool(value: object, default: bool = False) -> bool:
        return value if isinstance(value, bool) else default

    @staticmethod
    def _as_list(value: object) -> list[Any]:
        if isinstance(value, list):
            return value
        return []

    @staticmethod
    def _as_dict(value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _coerce_dependency_status(payload: dict[str, Any]) -> list[Any]:
        suite = payload.get("suite")
        suite_dependencies = PreviewHandler._as_list(PreviewHandler._as_dict(suite).get("external_dependency_status"))
        top_dependencies = PreviewHandler._as_list(payload.get("external_dependency_status"))
        if top_dependencies:
            return top_dependencies
        return suite_dependencies

    def _write_workspace_runtime_fields(
        self,
        request: dict[str, Any],
        *,
        run_mode: str,
        workspace: str | None = None,
        runs_dir: Path | None = None,
    ) -> dict[str, Any]:
        request["run_mode"] = run_mode
        resolved_runs_dir = runs_dir or self.runs_dir
        request["runs_dir"] = str(resolved_runs_dir)
        request["runs_dir_resolved_from"] = "payload" if runs_dir else "studio"

        if workspace:
            request["workspace"] = workspace
            request["workspace_resolved_from"] = "setup"
            request["workspace_id"] = workspace.split("/")[-1]
            request["workspace_manifest_ref"] = "workspace_manifest.json"
        return request

    def _adapt_setup_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = payload.get("config") if isinstance(payload.get("config"), dict) else None
        workspace = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else None
        suite = self._as_dict(payload.get("suite"))
        repair_items = self._as_list(payload.get("repair_items"))
        repair_items_count = payload.get("repair_items_count")
        repair_items_count = (
            int(repair_items_count)
            if isinstance(repair_items_count, int) and not isinstance(repair_items_count, bool)
            else len(repair_items)
        )
        workspace_ready = self._as_bool(
            payload.get("workspace_ready"),
            bool(workspace and workspace.get("status") == "valid"),
        )
        install_ready = self._as_bool(payload.get("install_ready"), bool(config))
        run_ready = self._as_bool(
            payload.get("run_ready"),
            bool(config and config.get("active_workspace") and workspace_ready),
        )
        production_ready = self._as_bool(
            payload.get("production_ready"),
            bool(install_ready and workspace_ready and not self._as_list(payload.get("repair_items"))),
        )
        workspace_entry_ready = self._as_bool(
            payload.get("workspace_entry_ready"),
            self._as_bool(
                payload.get("workspace_access_ready"),
                bool(payload.get("status") == "ready" and install_ready and workspace_ready and run_ready),
            ),
        )
        production_backend_ready = self._as_bool(
            payload.get("production_backend_ready"),
            self._as_bool(suite.get("production_backend_ready")),
        )
        client_delivery_ready = self._as_bool(
            payload.get("client_delivery_ready"),
            self._as_bool(suite.get("client_delivery_ready")),
        )
        blocking_summary = self._as_list(payload.get("blocking_summary"))
        if not blocking_summary and suite.get("blocking_summary"):
            blocking_summary = self._as_list(suite.get("blocking_summary"))
        external_dependency_status = self._coerce_dependency_status(payload)
        setup_blocking_summary = self._as_list(payload.get("setup_blocking_summary"))
        workspace_blocking_summary = self._as_list(payload.get("workspace_blocking_summary"))
        suite_blocking_summary = self._as_list(payload.get("suite_blocking_summary"))
        client_delivery_blocking_summary = self._as_list(payload.get("client_delivery_blocking_summary"))
        if not (setup_blocking_summary or workspace_blocking_summary or suite_blocking_summary or client_delivery_blocking_summary):
            for item in self._as_list(blocking_summary):
                if not isinstance(item, dict):
                    continue
                code = str(item.get("code") or "")
                blocking_type = str(item.get("blocking_type") or "")
                if blocking_type == "workspace":
                    workspace_blocking_summary.append(item)
                elif blocking_type == "delivery" or code == "client_delivery_blocked":
                    client_delivery_blocking_summary.append(item)
                elif blocking_type in {"backend", "runtime"} or code.startswith("suite_"):
                    suite_blocking_summary.append(item)
                else:
                    setup_blocking_summary.append(item)

        readiness_layers = self._as_dict(payload.get("readiness_layers"))
        if not readiness_layers:
            readiness_layers = {
                "setup": {
                    "ready": bool(install_ready and not setup_blocking_summary),
                    "status": "ready" if install_ready and not setup_blocking_summary else "blocked",
                    "blocking_summary": setup_blocking_summary,
                },
                "workspace": {
                    "ready": workspace_entry_ready,
                    "status": "ready" if workspace_entry_ready else payload.get("status", "blocked"),
                    "blocking_summary": workspace_blocking_summary,
                },
                "suite": {
                    "ready": self._as_bool(payload.get("full_suite_ready"), self._as_bool(suite.get("full_suite_ready"))),
                    "status": str(suite.get("status") or ""),
                    "blocking_summary": suite_blocking_summary,
                },
                "client_delivery": {
                    "ready": client_delivery_ready,
                    "status": "ready" if client_delivery_ready else "blocked",
                    "blocking_summary": client_delivery_blocking_summary,
                },
            }

        library_status = self._as_dict(payload.get("library_status"))
        if not library_status:
            library_status = self._as_dict(suite.get("library_status"))
        if not library_status:
            library_status = inspect_library_status()

        response = {
            "schema_version": payload.get("schema_version") or "deck_master_setup_status.v1",
            "schema_version_v2": "deck_master_setup_status.v2",
            "status": payload.get("status", "blocked"),
            "install_ready": install_ready,
            "workspace_ready": workspace_ready,
            "run_ready": run_ready,
            "workspace_entry_ready": workspace_entry_ready,
            "workspace_access_ready": workspace_entry_ready,
            "production_ready": production_ready,
            "dev_mode_allowed": self._as_bool(payload.get("dev_mode_allowed"), False),
            "fixture_mode_allowed": self._as_bool(payload.get("fixture_mode_allowed"), True),
            "active_workspace_required_for_production": self._as_bool(payload.get("active_workspace_required_for_production"), True),
            "install_root": str(config.get("install_root") or "") if isinstance(config, dict) else "",
            "active_workspace": str(config.get("active_workspace") or "") if isinstance(config, dict) else "",
            "default_runs_dir": str(config.get("default_runs_dir") or "") if isinstance(config, dict) else "",
            "next_command": payload.get("next_command", ""),
            "next_agent_action": payload.get("next_agent_action", ""),
            "config_path": payload.get("config_path"),
            "missing_items": self._as_list(payload.get("missing_items")),
            "repair_items": self._as_list(payload.get("repair_items")),
            "repair_items_count": repair_items_count,
            "warnings": self._as_list(payload.get("warnings")),
            "workspace": workspace,
            "config": config,
            "agent_targets": self._as_list(payload.get("agent_targets")),
            "suite": self._as_dict(payload.get("suite")),
            "full_suite_ready": self._as_bool(payload.get("full_suite_ready"), self._as_bool(suite.get("full_suite_ready"))),
            "capabilities": self._as_dict(payload.get("capabilities")),
            "task_readiness": self._as_dict(payload.get("task_readiness")),
            "library_status": library_status,
            "production_backend_ready": production_backend_ready,
            "client_delivery_ready": client_delivery_ready,
            "blocking_summary": self._as_list(blocking_summary),
            "setup_blocking_summary": setup_blocking_summary,
            "workspace_blocking_summary": workspace_blocking_summary,
            "suite_blocking_summary": suite_blocking_summary,
            "client_delivery_blocking_summary": client_delivery_blocking_summary,
            "readiness_layers": readiness_layers,
            "suite_external_dependency_status": self._as_list(self._as_dict(suite).get("external_dependency_status")),
            "external_dependency_status": self._as_list(external_dependency_status),
        }
        return response

    def api_update_decision(self, page_id: str, parsed) -> None:
        try:
            run_dir = self.active_run_dir(parsed)
            body = self.read_json_body()
            page = update_page_decision(
                run_dir,
                page_id,
                body.get("decision", ""),
                body.get("notes", ""),
            )
            append_typed_event(
                run_dir,
                "decision",
                "preview.review.decision",
                f"Page {page_id} decision updated to {page['decision']}",
                refs=[page_id],
                severity="info",
                payload={"decision": page["decision"], "notes": page.get("notes", "")},
            )
            self.send_json(page_payload(run_dir, page))
        except json.JSONDecodeError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be JSON.")
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_narrative(self, run_id: str) -> None:
        candidate = self._resolve_run_or_error(run_id)
        if not candidate:
            return
        try:
            narrative = _load_narrative_data(candidate)
            if not self.preview_manifest_exists(candidate):
                narrative["run_id"] = candidate.name
                narrative["title"] = self.run_title(candidate)
                narrative["preview_ready"] = False
                self.send_json(narrative)
                return
            manifest = load_manifest(candidate)
            narrative["run_id"] = manifest["run_id"]
            narrative["title"] = manifest["title"]
            narrative["preview_ready"] = True
            self.send_json(narrative)
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, self.public_manifest_error(exc))

    def api_asset_signals(self, run_id: str) -> None:
        """返回指定 run 的 asset signals 数据。"""
        candidate = self._resolve_run_or_error(run_id)
        if not candidate:
            return
        try:
            signals = _load_asset_signals(candidate)
            if not self.preview_manifest_exists(candidate):
                signals["run_id"] = candidate.name
                signals["title"] = self.run_title(candidate)
                signals["preview_ready"] = False
                signals["page_signals"] = []
                self.send_json(signals)
                return
            manifest = load_manifest(candidate)
            signals["run_id"] = manifest["run_id"]
            signals["preview_ready"] = True
            # 为每个页面构建候选信号摘要
            page_signals = []
            sourcing_plan = signals.get("sourcing_plan", {})
            asset_graph = signals.get("asset_graph", {})
            feedback_list = signals.get("feedback", [])

            # 按 page_id 索引 feedback
            feedback_by_page: dict[str, list] = {}
            for fb in feedback_list:
                pid = fb.get("page_id", "")
                if pid:
                    feedback_by_page.setdefault(pid, []).append(fb)

            # 按 page_id 索引 asset graph nodes
            assets_by_page: dict[str, list] = {}
            nodes = asset_graph.get("nodes", []) if isinstance(asset_graph, dict) else []
            for node in nodes:
                pid = node.get("page_id", "")
                if pid:
                    assets_by_page.setdefault(pid, []).append(node)

            for page in manifest["pages"]:
                pid = page["page_id"]
                page_fb = feedback_by_page.get(pid, [])
                page_assets = assets_by_page.get(pid, [])

                approved = sum(1 for f in page_fb if f.get("decision") == "approved")
                rejected = sum(1 for f in page_fb if f.get("decision") == "rejected")
                delivered = len(page_assets)
                total_fb = len(page_fb)
                approval_rate = round(approved / total_fb, 2) if total_fb > 0 else None

                # 查找当前选中候选的评分
                selected_candidate = None
                page_sourcing = {}
                if isinstance(sourcing_plan, dict):
                    pages_list = sourcing_plan.get("pages", [])
                    for sp in pages_list:
                        if sp.get("page_id") == pid:
                            page_sourcing = sp
                            break
                candidates = page_sourcing.get("candidates", [])
                selected_id = page_sourcing.get("selected_candidate_id", "")
                for c in candidates:
                    if c.get("candidate_id") == selected_id:
                        selected_candidate = c
                        break

                # Health flags from asset nodes
                health_flags = []
                for asset in page_assets:
                    flags = asset.get("health_flags", [])
                    if isinstance(flags, list):
                        health_flags.extend(flags)

                page_signals.append({
                    "page_id": pid,
                    "approval_rate": approval_rate,
                    "rejection_count": rejected,
                    "delivered_count": delivered,
                    "feedback_count": total_fb,
                    "health_flags": list(set(health_flags)),
                    "has_screenshot": any(a.get("screenshot_path") for a in page_assets),
                    "selected_candidate": selected_candidate,
                })

            signals["page_signals"] = page_signals
            append_typed_event(
                candidate,
                "step_started",
                "preview.asset_signals.viewed",
                f"Asset signals viewed for run {run_id}",
                severity="info",
                payload={"page_count": len(page_signals)},
            )
            self.send_json(signals)
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, self.public_manifest_error(exc))

    def api_quality_governance(self, run_id: str) -> None:
        """返回 quality governance 综合数据。"""
        candidate = self._resolve_run_or_error(run_id)
        if not candidate:
            return

        # Gate summary
        gate_summary = []
        quality_dir = candidate / "quality_reports"
        if quality_dir.exists():
            for gate_file in sorted(quality_dir.glob("*_gate.json")):
                try:
                    report = json.loads(gate_file.read_text(encoding="utf-8"))
                    gate_summary.append({
                        "gate": gate_file.stem.replace("_gate", ""),
                        "status": report.get("status", ""),
                        "blocks_delivery": report.get("blocks_delivery", False),
                        "findings_count": len(report.get("findings", [])),
                        "page_findings_count": len(report.get("page_findings", [])),
                    })
                except json.JSONDecodeError:
                    pass

        # Page-level findings (aggregated from all gates)
        page_findings = []
        if quality_dir.exists():
            for gate_file in sorted(quality_dir.glob("*_gate.json")):
                try:
                    report = json.loads(gate_file.read_text(encoding="utf-8"))
                    gate_name = gate_file.stem.replace("_gate", "")
                    for f in report.get("findings", []):
                        entry = dict(f)
                        entry["gate"] = gate_name
                        page_findings.append(entry)
                except json.JSONDecodeError:
                    pass

        # Active overrides
        active_overrides = list_active_overrides(candidate)

        # Delivery readiness uses the final readiness gate that client export enforces.
        has_blocking = any(g["blocks_delivery"] for g in gate_summary)
        clearance = has_client_export_quality_clearance(candidate, allow_quality_override=True)
        final_clearance = final_readiness_clearance(candidate)
        delivery_ready = bool(final_clearance["ready"])

        # Final artifact validation status
        delivery_dir = candidate / "delivery"
        validation_status = None
        lineage_data = {}
        if delivery_dir.exists():
            lineage_path = delivery_dir / "final_version_lineage.json"
            if lineage_path.exists():
                try:
                    lineage_data = json.loads(lineage_path.read_text(encoding="utf-8"))
                    validation_status = "validated"
                except json.JSONDecodeError:
                    validation_status = "invalid_lineage"

        # Delivery outcome
        outcome_data = {}
        if delivery_dir.exists():
            outcome_path = delivery_dir / "delivery_outcome.json"
            if outcome_path.exists():
                try:
                    outcome_data = json.loads(outcome_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass

        self.send_json({
            "run_id": run_id,
            "title": self.run_title(candidate),
            "status": run_status(candidate),
            "preview_ready": self.preview_manifest_exists(candidate),
            "gate_summary": gate_summary,
            "page_findings": page_findings,
            "active_overrides": active_overrides,
            "delivery_readiness": {
                "ready": delivery_ready,
                "has_blocking_gates": has_blocking,
                "active_override_count": len(active_overrides),
                "reason": final_clearance.get("reason", "") or clearance.get("reason", ""),
                "final_readiness_status": final_clearance.get("status", ""),
                "final_readiness_path": final_clearance.get("path", ""),
            },
            "validation_status": validation_status,
            "lineage": lineage_data,
            "outcome": outcome_data,
        })

    def _resolve_run_or_error(self, run_id: str, parsed: object | None = None, *, run_dir: str | None = None):
        """Resolve run_id to a Path, or return None and send error response."""
        if not run_id:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "run_id is required.")
            return None

        debug_run_dir = run_dir
        if parsed is not None and not debug_run_dir:
            try:
                debug_run_dir = parse_qs(parsed.query).get("run_dir", [None])[0]  # type: ignore[attr-defined]
            except Exception:
                debug_run_dir = None

        if self.run_dir is not None and not debug_run_dir:
            run_parts = Path(run_id).parts
            if "/" in run_id or ".." in run_parts:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid run_id.")
                return None
            allowed_run_ids = {self.run_dir.name}
            try:
                allowed_run_ids.add(str(load_manifest(self.run_dir).get("run_id") or ""))
            except ManifestError:
                pass
            if run_id not in allowed_run_ids:
                self.send_error_json(HTTPStatus.NOT_FOUND, f"Run not found: {run_id}")
                return None
            candidate = self.run_dir.resolve()
            root = candidate.parent
        else:
            root = self.studio_runs_dir()
            candidate = (root / run_id).resolve()
        if debug_run_dir:
            candidate = Path(str(debug_run_dir)).expanduser().resolve()

        root_text = str(root.resolve())
        candidate_text = str(candidate)
        if candidate_text != root_text and not candidate_text.startswith(root_text + "/"):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid run_id.")
            return None
        if not candidate.is_dir():
            self.send_error_json(HTTPStatus.NOT_FOUND, f"Run not found: {run_id}")
            return None
        return candidate

    def api_review_summary(self, run_id: str) -> None:
        """Return deck readiness panel data."""
        run_dir = self._resolve_run_or_error(run_id)
        if not run_dir:
            return
        try:
            self.send_json(compute_deck_readiness(run_dir))
        except Exception as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_claim_coverage(self, run_id: str) -> None:
        """Return claim coverage matrix."""
        run_dir = self._resolve_run_or_error(run_id)
        if not run_dir:
            return
        try:
            self.send_json(compute_claim_coverage(run_dir))
        except Exception as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_next_actions(self, run_id: str) -> None:
        """Return prioritised next 5 actions."""
        run_dir = self._resolve_run_or_error(run_id)
        if not run_dir:
            return
        try:
            self.send_json(compute_next_actions(run_dir))
        except Exception as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_review_action(self, page_id: str, parsed) -> None:
        """Execute a page review action (F2)."""
        try:
            run_dir = self.active_run_dir(parsed)
        except Exception as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            return
        body = self.read_json_body()
        action = body.get("action", "")
        if not action:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "action is required.")
            return
        try:
            result = execute_review_action(
                run_dir,
                page_id,
                action,
                actor=body.get("actor", "user"),
                reason=body.get("reason", ""),
                note=body.get("note", ""),
                finding_id=body.get("finding_id", ""),
                severity=body.get("severity", "P1"),
                approver=body.get("approver", ""),
            )
            self.send_json(result)
        except WorkbenchError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_external_results(self, run_id: str) -> None:
        """Return external result visibility data (F3)."""
        run_dir = self._resolve_run_or_error(run_id)
        if not run_dir:
            return

        results: dict[str, Any] = {
            "run_id": run_id,
            "narrative_advice": None,
            "external_reviews": [],
            "generation_results": [],
            "runtime_readiness": _runtime_readiness_payload(run_dir),
        }

        # Narrative advice.
        narr_path = run_dir / "advisor_results" / "narrative_advice.json"
        if narr_path.exists():
            try:
                results["narrative_advice"] = json.loads(narr_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        # External quality reviews.
        quality_dir = run_dir / "quality_reports"
        if quality_dir.exists():
            for gate_file in sorted(quality_dir.glob("external_*_gate.json")):
                try:
                    report = json.loads(gate_file.read_text(encoding="utf-8"))
                    report["_report_file"] = gate_file.name
                    results["external_reviews"].append(report)
                except json.JSONDecodeError:
                    pass

        # Generation results.
        gen_results_dir = run_dir / "generation_results"
        if gen_results_dir.exists():
            for result_file in sorted(gen_results_dir.glob("*.json")):
                try:
                    result = json.loads(result_file.read_text(encoding="utf-8"))
                    results["generation_results"].append(result)
                except json.JSONDecodeError:
                    pass

        self.send_json(results)

    def api_runtime_readiness(self, run_id: str) -> None:
        run_dir = self._resolve_run_or_error(run_id)
        if not run_dir:
            return
        self.send_json(_runtime_readiness_payload(run_dir))

    def api_export_queue(self, run_id: str, parsed) -> None:
        """Return export queue preview without writing queue artifacts."""
        run_dir = self._resolve_run_or_error(run_id)
        if not run_dir:
            return

        params = parse_qs(parsed.query)
        decisions = set(params.get("decision", ["approved"]))
        queue_type = (params.get("queue_type", ["client"])[0] or "client").strip()
        allow_quality_override = (params.get("allow_quality_override", ["false"])[0] or "").lower() in {
            "1",
            "true",
            "yes",
        }
        if not self.preview_manifest_exists(run_dir):
            invalid = decisions - DECISIONS
            if invalid:
                self.send_error_json(HTTPStatus.BAD_REQUEST, f"Invalid decisions: {', '.join(sorted(invalid))}")
                return
            self.send_json(
                {
                    "run_id": run_id,
                    "title": self.run_title(run_dir),
                    "status": run_status(run_dir),
                    "preview_ready": False,
                    "decisions": sorted(decisions),
                    "queue_type": queue_type,
                    "pages": [],
                    "blocked_pages": [],
                    "blocked_count": 0,
                }
            )
            return
        try:
            queue = export_queue(
                run_dir,
                decisions,
                queue_type=queue_type,
                allow_quality_override=allow_quality_override,
            )
            self.send_json(queue)
        except (ManifestError, ValueError) as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, self.public_manifest_error(exc))

    def api_run_metrics(self, run_id: str) -> None:
        """Return lightweight run metrics without writing run_metrics.json."""
        run_dir = self._resolve_run_or_error(run_id)
        if not run_dir:
            return
        try:
            self.send_json(summarize_run_metrics(run_dir))
        except Exception as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_override_create(self, parsed) -> None:
        """创建 quality override。"""
        try:
            run_dir = self.active_run_dir(parsed)
            body = self.read_json_body()
            override = create_override(
                run_dir,
                finding_id=body.get("finding_id", ""),
                severity=body.get("severity", "P1"),
                reason=body.get("reason", ""),
                approver=body.get("approver", ""),
                scope=body.get("scope", "client_export"),
                actor=body.get("actor", "user"),
                expires_days=body.get("expires_days", 14),
                run_id=run_dir.name,
            )
            self.send_json(override, HTTPStatus.CREATED)
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except json.JSONDecodeError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be JSON.")
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_override_revoke(self, parsed) -> None:
        """撤销 quality override。"""
        try:
            run_dir = self.active_run_dir(parsed)
            body = self.read_json_body()
            override = revoke_override(
                run_dir,
                override_id=body.get("override_id", ""),
                reason=body.get("reason", ""),
            )
            self.send_json(override)
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except json.JSONDecodeError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be JSON.")
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_delivery_mark_delivered(self, parsed) -> None:
        """标记已交付。"""
        try:
            run_dir = self.active_run_dir(parsed)
            body = self.read_json_body()
            outcome = record_delivery_outcome(
                run_dir,
                delivered=True,
                advanced_to_next_stage=body.get("advanced_to_next_stage", False),
                notes=body.get("notes", ""),
            )
            self.send_json(outcome)
        except json.JSONDecodeError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be JSON.")
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_delivery_record_reaction(self, parsed) -> None:
        """记录客户反馈。"""
        try:
            run_dir = self.active_run_dir(parsed)
            body = self.read_json_body()
            outcome = record_delivery_outcome(
                run_dir,
                delivered=body.get("delivered", True),
                customer_reaction=body.get("customer_reaction", ""),
                notes=body.get("notes", ""),
            )
            self.send_json(outcome)
        except json.JSONDecodeError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be JSON.")
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def serve_preview(self, page_id: str, parsed) -> None:
        try:
            run_dir = self.active_run_dir(parsed)
            manifest = load_manifest(run_dir)
            page = find_page(manifest, page_id)
            asset_path = preview_file_path(run_dir, page)
            if not asset_path.exists():
                self.send_error_json(HTTPStatus.NOT_FOUND, "Preview asset is missing.")
                return
            content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
            content = asset_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def serve_delivery_preview(self, run_id: str, parsed) -> None:
        run_dir = self._resolve_run_or_error(run_id, parsed=parsed)
        if not run_dir:
            return
        payload = build_delivery_preview_payload(run_dir)
        if not payload.get("artifact_ready"):
            self.send_error_json(HTTPStatus.NOT_FOUND, str(payload.get("detail") or "Delivery preview artifact is missing."))
            return
        artifact_path = str(payload.get("artifact_path") or "")
        target = (run_dir / artifact_path).resolve()
        root_text = str(run_dir.resolve())
        target_text = str(target)
        if target_text != root_text and not target_text.startswith(root_text + "/"):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid delivery preview path.")
            return
        if not target.exists() or not target.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "Delivery preview file not found.")
            return
        content_type = mimetypes.guess_type(target.name)[0] or "text/html"
        content = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw_body.decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object.")
        return body

    def serve_static(self, filename: str) -> None:
        target = (STATIC_DIR / filename).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid static path.")
            return
        if not target.exists() or not target.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "Static file not found.")
            return
        content_type = mimetypes.guess_type(target.name)[0] or "text/plain"
        if target.name == "index.html":
            runtime_config = {
                "writeToken": str(getattr(self, "write_token", "") or ""),
                "writeTokenHeader": WRITE_TOKEN_HEADER,
            }
            text = target.read_text(encoding="utf-8")
            injection = (
                "<script>"
                f"window.__DECK_MASTER_CONFIG__ = {json.dumps(runtime_config, ensure_ascii=False)};"
                "</script>"
            )
            text = text.replace("</head>", f"    {injection}\n  </head>")
            content = text.encode("utf-8")
        else:
            content = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message}, status)


def build_handler(
    run_dir: Path | None,
    runs_dir: Path | None = None,
    library_mode: str = "fixture",
    *,
    use_setup_runs_dir: bool | None = None,
    write_token: str | None = None,
):
    class Handler(PreviewHandler):
        pass

    Handler.run_dir = run_dir
    Handler.runs_dir = (runs_dir or configured_runs_dir(ROOT_DIR / "runs")).expanduser().resolve()
    Handler.library_mode = library_mode
    Handler.use_setup_runs_dir = bool(runs_dir is None if use_setup_runs_dir is None else use_setup_runs_dir)
    Handler.write_token = write_token or secrets.token_urlsafe(32)
    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Deck Master local preview UI.")
    parser.add_argument("run_dir", nargs="?", help="Directory containing preview_manifest.json. Omit for Studio mode.")
    parser.add_argument("--runs-dir", default=None, help="Studio mode run storage directory.")
    parser.add_argument("--library-mode", choices=["auto", "real", "fixture"], default="fixture")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--write-token", default=None, help=f"Review Desk write token. Defaults to {WRITE_TOKEN_ENV} or a generated token.")
    parser.add_argument(
        "--allow-remote-preview",
        action="store_true",
        help="Allow binding Review Desk to a non-loopback host for trusted local-network demos.",
    )
    args = parser.parse_args()

    try:
        remote_warning = validate_preview_bind_host(args.host, allow_remote_preview=args.allow_remote_preview)
    except ValueError as exc:
        parser.error(str(exc))

    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None
    explicit_runs_dir = args.runs_dir is not None
    runs_dir = Path(args.runs_dir).expanduser().resolve() if explicit_runs_dir else configured_runs_dir(ROOT_DIR / "runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    if run_dir is not None:
        load_manifest(run_dir)
    server = ThreadingHTTPServer(
        (args.host, args.port),
        build_handler(
            run_dir,
            runs_dir,
            args.library_mode,
            use_setup_runs_dir=not explicit_runs_dir,
            write_token=args.write_token or os.environ.get(WRITE_TOKEN_ENV) or None,
        ),
    )
    mode = "Preview" if run_dir else "Studio"
    print(f"Deck Master {mode}: http://{args.host}:{args.port}")
    print(f"Runs directory: {runs_dir}")
    if run_dir:
        print(f"Run directory: {run_dir}")
    print(f"Write protection: enabled ({WRITE_TOKEN_HEADER})")
    if remote_warning:
        print(remote_warning, file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
