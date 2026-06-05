from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from manifest import ManifestError, find_page, load_manifest, page_payload, preview_file_path, update_page_decision


STATIC_DIR = Path(__file__).parent / "static"


class PreviewHandler(BaseHTTPRequestHandler):
    run_dir: Path

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
            self.api_deck()
            return
        if path.startswith("/api/page/"):
            self.api_page(path.removeprefix("/api/page/"))
            return
        if path.startswith("/preview/"):
            self.serve_preview(path.removeprefix("/preview/"))
            return

        self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found.")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path.startswith("/api/page/") and path.endswith("/decision"):
            page_id = path.removeprefix("/api/page/").removesuffix("/decision").strip("/")
            self.api_update_decision(page_id)
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found.")

    def api_deck(self) -> None:
        try:
            manifest = load_manifest(self.run_dir)
            pages = [page_payload(self.run_dir, page) for page in manifest["pages"]]
            self.send_json(
                {
                    "run_id": manifest["run_id"],
                    "title": manifest["title"],
                    "status": manifest["status"],
                    "updated_at": manifest.get("updated_at", ""),
                    "pages": pages,
                }
            )
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def api_page(self, page_id: str) -> None:
        try:
            manifest = load_manifest(self.run_dir)
            page = find_page(manifest, page_id)
            self.send_json(page_payload(self.run_dir, page))
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))

    def api_update_decision(self, page_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw_body.decode("utf-8"))
            page = update_page_decision(
                self.run_dir,
                page_id,
                body.get("decision", ""),
                body.get("notes", ""),
            )
            self.send_json(page_payload(self.run_dir, page))
        except json.JSONDecodeError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be JSON.")
        except ManifestError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def serve_preview(self, page_id: str) -> None:
        try:
            manifest = load_manifest(self.run_dir)
            page = find_page(manifest, page_id)
            asset_path = preview_file_path(self.run_dir, page)
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


def build_handler(run_dir: Path):
    class Handler(PreviewHandler):
        pass

    Handler.run_dir = run_dir
    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Deck Master local preview UI.")
    parser.add_argument("run_dir", help="Directory containing preview_manifest.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    load_manifest(run_dir)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(run_dir))
    print(f"Deck Master preview: http://{args.host}:{args.port}")
    print(f"Run directory: {run_dir}")
    server.serve_forever()


if __name__ == "__main__":
    main()
