"""Installed-package browser gate. Synthetic quality inputs; no Host/model claims.

Internet requests are refused while loopback stays available. This tests an
internet-disconnected local application, not an offline local server.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import zipfile
from urllib.parse import urlencode, urlsplit
from importlib.resources import files
from playwright.sync_api import sync_playwright, expect
import deck_master
from deck_master import ui_journal
from deck_master.web import WorkbenchServer
from w11_browser import fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--font", default="Arial")
    parser.add_argument("--require-installed", action="store_true")
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    module = Path(deck_master.__file__).resolve()
    if args.require_installed:
        assert module.is_relative_to(Path(sys.prefix).resolve()) and "site-packages" in module.parts, module
    project, store, historical = fixture(root, args.font)
    revision = store.current_revision_id()
    identity = ui_journal.project_info(project)["project_identity"]
    server = WorkbenchServer(project)
    external = []
    errors = []
    downloads = []
    resources = []
    fonts = []
    checks = {}
    try:
        url = server.start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(accept_downloads=True, record_har_path=str(root / "local-only.har"), record_har_content="omit")

            def gate(route):
                if urlsplit(route.request.url).hostname not in ("127.0.0.1", "localhost"):
                    external.append(route.request.url)
                    route.abort()
                else:
                    route.continue_()

            context.route("**/*", gate)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: resources.append({"path": urlsplit(response.url).path, "status": response.status}))
            for width, height in [(1440, 900), (1280, 800)]:
                page.set_viewport_size({"width": width, "height": height})
                page.goto(url + "v2/#" + urlencode({"project": identity, "revision": revision, "surface": "runs", "layer": "content"}))
                expect(page.get_by_role("heading", name="版本与文件", exact=True)).to_be_visible()
                assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
                page.get_by_role("button", name="查看版本与文件", exact=True).click()
                expect(page.get_by_role("heading", name="版本与文件", exact=True)).to_be_focused()
                fonts.append(
                    page.evaluate(
                        "async () => {await document.fonts.ready; return {status:document.fonts.status,body:getComputedStyle(document.body).fontFamily}}"
                    )
                )
                page.screenshot(path=str(root / f"delivery-{width}.png"))
                checks[f"viewport_{width}_{height}_focus_and_overflow"] = True
            for purpose, label in [("review", "审阅包"), ("delivery", "正式交付包"), ("engineering", "内部工程包")]:
                page.get_by_role("button", name="生成" + label, exact=True).click()
                row = page.locator(".export-result").filter(has=page.get_by_role("heading", name=label + " ·")).first
                link = row.get_by_role("link", name="下载 ZIP", exact=True)
                expect(link).to_be_visible()
                with page.expect_download() as event:
                    link.click()
                target = root / event.value.suggested_filename
                event.value.save_as(target)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                expect(row).to_contain_text(digest)
                with zipfile.ZipFile(target) as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                    assert manifest["purpose"] == purpose and manifest["revision_id"] == revision
                    for item in manifest["files"]:
                        assert hashlib.sha256(archive.read(item["path"])).hexdigest() == item["sha256"]
                downloads.append({"purpose": purpose, "revision": revision, "sha256": digest, "files": len(manifest["files"])})
            checks["three_fixed_offline_downloads_hash_verified"] = True
            static = files("deck_master").joinpath("resources/static/v2")
            for asset in sorted(static.iterdir(), key=lambda p: p.name):
                if not asset.is_file():
                    continue
                response = context.request.get(url + "v2/" + asset.name)
                assert response.status == 200 and response.body() == asset.read_bytes(), asset.name
            checks["every_v2_asset_served_from_installed_package"] = True
            # Read old entry from the same installed core without changing project.
            before = store.read_current()
            page.goto(url)
            assert page.locator("body").inner_text().strip()
            assert store.read_current() == before
            checks["legacy_entry_read_without_write"] = True
            assert not external and not errors and all(f["status"] == "loaded" for f in fonts)
            checks["no_cdn_external_font_or_runtime_request"] = True
            context.close()
            browser.close()
        result = {
            "checks": checks,
            "downloads": downloads,
            "external_requests": external,
            "page_errors": errors,
            "font_checks": fonts,
            "resources": resources,
            "environment": {
                "module": str(module),
                "python": platform.python_version(),
                "platform": platform.platform(),
                "installed": "site-packages" in module.parts,
            },
            "synthetic": True,
            "model_calls": 0,
            "professional_evidence": "not_evaluated",
        }
        (root / "checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"checks": len(checks), "status": "verified"}))
    finally:
        server.stop()


if __name__ == "__main__":
    main()
