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
    parser.add_argument("--chromium-executable", type=Path,
                        help="Use an explicitly installed Chromium instead of Playwright's bundled browser.")
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
            browser = pw.chromium.launch(
                executable_path=str(args.chromium_executable) if args.chromium_executable else None,
            )
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
                page.goto(url + "v2/#" + urlencode({"project": identity, "revision": revision, "surface": "runs", "area": "files", "layer": "content"}))
                expect(page.get_by_role("heading", name="版本与文件", exact=True)).to_be_visible()
                assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
                page.get_by_role("button", name="文件", exact=True).click()
                expect(page.get_by_role("heading", name="版本与文件", exact=True)).to_be_focused()
                fonts.append(
                    page.evaluate(
                        "async () => {await document.fonts.ready; return {status:document.fonts.status,body:getComputedStyle(document.body).fontFamily}}"
                    )
                )
                page.screenshot(path=str(root / f"delivery-{width}.png"))
                checks[f"viewport_{width}_{height}_focus_and_overflow"] = True
            for purpose, label in [("review", "审阅包"), ("delivery", "正式交付包"), ("engineering", "内部工程包")]:
                if purpose == 'engineering':
                    page.locator('.export-recovery > summary').click()
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

            def public_assets(directory, prefix=""):
                for asset in sorted(directory.iterdir(), key=lambda p: p.name):
                    name = prefix + asset.name
                    if asset.is_dir():
                        yield from public_assets(asset, name + "/")
                    elif Path(asset.name).suffix in (".html", ".js", ".css", ".woff2", ".svg"):
                        yield name, asset

            served = []
            for name, asset in public_assets(static):
                response = context.request.get(url + "v2/" + name)
                assert response.status == 200 and response.body() == asset.read_bytes(), name
                served.append(name)
            assert "assets/deck-master-logo/logo-horizontal-light.svg" in served
            assert "assets/deck-master-logo/favicon.svg" in served
            assert static.joinpath("assets/deck-master-logo/IBMPlexMono-OFL.txt").is_file()
            assert json.loads(static.joinpath("package.json").read_text())["type"] == "module"
            checks["every_v2_asset_served_from_installed_package"] = True
            # All supported entries serve the current UI; retired routes stay absent.
            before = store.read_current()
            current_index = static.joinpath("index.html").read_bytes()
            for path in ("", "index.html", "v2/", "v2/index.html"):
                response = context.request.get(url + path)
                assert response.status == 200 and response.body() == current_index, path
            page.goto(url + "#" + urlencode({"project": identity, "revision": revision, "surface": "overview", "layer": "content"}))
            expect(page.get_by_role("heading", name="制作总览", exact=True)).to_be_visible()
            assert page.locator(".brand-logo").evaluate("image => image.complete && image.naturalWidth > 0")
            for path in ("legacy", "legacy/", "app.js", "style.css"):
                assert context.request.get(url + path).status == 404, path
            old_static = files("deck_master").joinpath("resources/static")
            assert all(not old_static.joinpath(name).is_file() for name in ("index.html", "app.js", "style.css"))
            assert store.read_current() == before
            checks["current_entries_and_retired_routes_without_write"] = True
            checks["installed_brand_license_and_esm_metadata"] = True
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
                "chromium": browser.version,
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
