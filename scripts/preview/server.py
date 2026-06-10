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

from generation.task_builder import create_generation_tasks
from orchestrate.preview_builder import build_preview_from_sourcing
from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from planning.sourcing_decider import decide_sourcing
from runtime.run_state import NARRATIVE_PLAN_NAME, SOURCING_PLAN_NAME, create_run, load_request, read_json, run_status, write_artifact
from tools.ppt_library_client import run_library_selection


STATIC_DIR = Path(__file__).parent / "static"


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
            self.send_json(page_payload(run_dir, page))
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
