from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "preview"))

from server import build_handler


SAMPLE_RUN = ROOT / "examples" / "preview-run"


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = self.temp_dir / "run"
        shutil.copytree(SAMPLE_RUN, self.run_dir)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(self.run_dir))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_deck_api_returns_pages(self) -> None:
        status, data = self.request("GET", "/api/deck")
        self.assertEqual(200, status)
        self.assertEqual("sample-preview-run", data["run_id"])
        self.assertEqual(3, len(data["pages"]))

    def test_page_decision_api_writes_manifest(self) -> None:
        status, data = self.request(
            "POST",
            "/api/page/page_003/decision",
            {"decision": "approved", "notes": "Conclusion is now accepted."},
        )
        self.assertEqual(200, status)
        self.assertEqual("approved", data["decision"])
        self.assertEqual("Conclusion is now accepted.", data["notes"])

        status, page = self.request("GET", "/api/page/page_003")
        self.assertEqual(200, status)
        self.assertEqual("approved", page["decision"])


if __name__ == "__main__":
    unittest.main()
