from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from manifest import (
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

from delivery.outcome import record_delivery_outcome
from delivery.validate import validate_delivery
from orchestrate.export_queue import has_client_export_quality_clearance
from generation.task_builder import create_generation_tasks
from orchestrate.preview_builder import build_preview_from_sourcing
from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from planning.sourcing_decider import decide_sourcing
from quality.overrides import create_override, list_active_overrides, load_overrides, revoke_override
from runtime.run_state import NARRATIVE_PLAN_NAME, SOURCING_PLAN_NAME, create_run, load_request, read_json, run_status, write_artifact
from tools.ppt_library_client import run_library_selection


STATIC_DIR = Path(__file__).parent / "static"


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


class PreviewHandler(BaseHTTPRequestHandler):
    run_dir: Path | None = None
    runs_dir: Path
    library_mode: str = "fixture"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

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
        if path.startswith("/api/narrative/"):
            self.api_narrative(path.removeprefix("/api/narrative/").strip("/"))
            return
        if path.startswith("/api/asset-signals/"):
            self.api_asset_signals(path.removeprefix("/api/asset-signals/").strip("/"))
            return
        if path.startswith("/api/quality-governance/"):
            self.api_quality_governance(path.removeprefix("/api/quality-governance/").strip("/"))
            return
        if path.startswith("/preview/"):
            self.serve_preview(path.removeprefix("/preview/"), parsed)
            return

        self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found.")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/runs":
            self.api_create_run()
            return
        if path.startswith("/api/page/") and path.endswith("/decision"):
            page_id = path.removeprefix("/api/page/").removesuffix("/decision").strip("/")
            self.api_update_decision(page_id, parsed)
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

    def active_run_dir(self, parsed) -> Path:
        if self.run_dir is not None:
            return self.run_dir
        params = parse_qs(parsed.query)
        run_id = (params.get("run_id") or params.get("run") or [""])[0].strip()
        if not run_id:
            raise ManifestError("run_id is required in studio mode.")
        candidate = (self.runs_dir / run_id).resolve()
        root_text = str(self.runs_dir.resolve())
        candidate_text = str(candidate)
        if candidate_text != root_text and not candidate_text.startswith(root_text + "/"):
            raise ManifestError("Invalid run_id.")
        return candidate

    def run_summary(self, run_dir: Path) -> dict:
        title = run_dir.name
        pages = 0
        decisions: dict[str, int] = {}
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
        return {
            "run_id": run_dir.name,
            "title": title,
            "status": run_status(run_dir),
            "pages": pages,
            "decisions": decisions,
        }

    def api_runs(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        runs = [
            self.run_summary(child)
            for child in sorted(self.runs_dir.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
            if child.is_dir()
        ]
        self.send_json({"runs_dir": str(self.runs_dir), "runs": runs})

    def api_deck(self, parsed) -> None:
        try:
            run_dir = self.active_run_dir(parsed)
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
                }
            )
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_page(self, page_id: str, parsed) -> None:
        try:
            run_dir = self.active_run_dir(parsed)
            manifest = load_manifest(run_dir)
            page = find_page(manifest, page_id)
            self.send_json(page_payload(run_dir, page))
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))

    def api_create_run(self) -> None:
        try:
            body = self.read_json_body()
            request = build_request(
                brief=body.get("brief", ""),
                brief_file=None,
                industry=body.get("industry", ""),
                target_pages=body.get("target_pages", "auto"),
                audience=body.get("audience", "client"),
                style_preference=body.get("style_preference", ""),
                run_id=body.get("run_id", ""),
            )
            run_dir = create_run(self.runs_dir, request, run_id=body.get("run_id") or None, force=bool(body.get("force")))
            request = load_request(run_dir)
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
        if not run_id:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "run_id is required.")
            return
        candidate = (self.runs_dir / run_id).resolve()
        root_text = str(self.runs_dir.resolve())
        candidate_text = str(candidate)
        if candidate_text != root_text and not candidate_text.startswith(root_text + "/"):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid run_id.")
            return
        if not candidate.is_dir():
            self.send_error_json(HTTPStatus.NOT_FOUND, f"Run not found: {run_id}")
            return
        try:
            narrative = _load_narrative_data(candidate)
            manifest = load_manifest(candidate)
            narrative["run_id"] = manifest["run_id"]
            narrative["title"] = manifest["title"]
            self.send_json(narrative)
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_asset_signals(self, run_id: str) -> None:
        """返回指定 run 的 asset signals 数据。"""
        if not run_id:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "run_id is required.")
            return
        candidate = (self.runs_dir / run_id).resolve()
        root_text = str(self.runs_dir.resolve())
        candidate_text = str(candidate)
        if candidate_text != root_text and not candidate_text.startswith(root_text + "/"):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid run_id.")
            return
        if not candidate.is_dir():
            self.send_error_json(HTTPStatus.NOT_FOUND, f"Run not found: {run_id}")
            return
        try:
            signals = _load_asset_signals(candidate)
            manifest = load_manifest(candidate)
            signals["run_id"] = manifest["run_id"]
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
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_quality_governance(self, run_id: str) -> None:
        """返回 quality governance 综合数据。"""
        if not run_id:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "run_id is required.")
            return
        candidate = (self.runs_dir / run_id).resolve()
        root_text = str(self.runs_dir.resolve())
        candidate_text = str(candidate)
        if candidate_text != root_text and not candidate_text.startswith(root_text + "/"):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid run_id.")
            return
        if not candidate.is_dir():
            self.send_error_json(HTTPStatus.NOT_FOUND, f"Run not found: {run_id}")
            return

        try:
            manifest = load_manifest(candidate)
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
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

        # Delivery readiness uses the same policy as client export.
        has_blocking = any(g["blocks_delivery"] for g in gate_summary)
        clearance = has_client_export_quality_clearance(candidate, allow_quality_override=True)
        delivery_ready = bool(clearance["ready"])

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
            "gate_summary": gate_summary,
            "page_findings": page_findings,
            "active_overrides": active_overrides,
            "delivery_readiness": {
                "ready": delivery_ready,
                "has_blocking_gates": has_blocking,
                "active_override_count": len(active_overrides),
                "reason": clearance.get("reason", ""),
            },
            "validation_status": validation_status,
            "lineage": lineage_data,
            "outcome": outcome_data,
        })

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


def build_handler(run_dir: Path | None, runs_dir: Path | None = None, library_mode: str = "fixture"):
    class Handler(PreviewHandler):
        pass

    Handler.run_dir = run_dir
    Handler.runs_dir = (runs_dir or ROOT_DIR / "runs").expanduser().resolve()
    Handler.library_mode = library_mode
    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Deck Master local preview UI.")
    parser.add_argument("run_dir", nargs="?", help="Directory containing preview_manifest.json. Omit for Studio mode.")
    parser.add_argument("--runs-dir", default=str(ROOT_DIR / "runs"), help="Studio mode run storage directory.")
    parser.add_argument("--library-mode", choices=["auto", "real", "fixture"], default="fixture")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None
    runs_dir = Path(args.runs_dir).expanduser().resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)
    if run_dir is not None:
        load_manifest(run_dir)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(run_dir, runs_dir, args.library_mode))
    mode = "Preview" if run_dir else "Studio"
    print(f"Deck Master {mode}: http://{args.host}:{args.port}")
    print(f"Runs directory: {runs_dir}")
    if run_dir:
        print(f"Run directory: {run_dir}")
    server.serve_forever()


if __name__ == "__main__":
    main()
