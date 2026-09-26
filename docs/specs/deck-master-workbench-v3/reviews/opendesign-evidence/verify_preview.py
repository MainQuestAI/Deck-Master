"""Bounded verification of the imported OpenDesign prototype, without mutation.

Uses fresh Chromium contexts and synthetic localStorage only. Reads the MCP import
manifest URL; does not call an OpenDesign generation or write API.
"""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import hashlib
import json
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
MANIFEST = HERE.parent / "09-opendesign-sync.json"
manifest = json.loads(MANIFEST.read_text())
url = manifest["preview_url"]
origin = (urlsplit(url).scheme, urlsplit(url).netloc)
result = {
    "time": datetime.now(timezone.utc).isoformat(),
    "scope": "Imported OpenDesign HTML prototype in isolated browser contexts",
    "preview_url": url,
    "generation_run_commissioned": False,
    "production_acceptance": False,
    "browser": "Chromium",
    "viewports": [],
    "asset_http_hash_checks": [],
}

with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, height in [(1280, 800), (1440, 900)]:
        ctx = browser.new_context(viewport={"width": width, "height": height})
        page = ctx.new_page()
        row = {
            "viewport": f"{width}x{height}", "checks": [], "page_errors": [],
            "external_resource_requests": [], "resource_http_failures": [],
            "request_failures": [], "screenshots": [],
        }
        page.on("pageerror", lambda e, r=row: r["page_errors"].append(str(e)))
        page.on("request", lambda req, r=row: r["external_resource_requests"].append(
            {"url": req.url, "type": req.resource_type})
            if (urlsplit(req.url).scheme, urlsplit(req.url).netloc) != origin else None)
        page.on("response", lambda res, r=row: r["resource_http_failures"].append(
            {"url": res.url, "status": res.status}) if res.status >= 400 else None)
        page.on("requestfailed", lambda req, r=row: r["request_failures"].append(
            {"url": req.url, "failure": req.failure}))

        def check(name, ok):
            assert ok, name
            row["checks"].append(name)

        def screenshot(name):
            file = f"{name}-{width}.png"
            page.screenshot(path=str(HERE / file), full_page=True)
            row["screenshots"].append(file)

        try:
            response = page.goto(url, wait_until="networkidle")
            check("OpenDesign imported index responds HTTP 200", response.status == 200)
            check("entry overview is rendered", "把 24 页，作为一份方案来做" in page.inner_text("main"))
            check("visible synthetic boundary", "全部为样本" in page.inner_text(".sidebar"))
            check("entry has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            screenshot("overview")
            page.get_by_role("button", name="看 24 页原图 →", exact=True).click()
            check("gallery contains 24 page tiles", page.locator(".slide-tile").count() == 24)
            check("gallery has 20 originals and 4 missing placeholders", page.locator(".slide-cover svg").count() == 20 and page.locator(".slide-cover .empty-artifact").count() == 4)
            check("gallery has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            screenshot("gallery")
            page.locator('[data-action="page-8-image"]').first.click()
            check("single page 8 is selected", "08" in page.locator("h1").inner_text())
            check("single page displays synthetic execution prompt", "实际发送的提示词" in page.inner_text("main") and "gen-008-v2" in page.inner_text("main"))
            page.locator('[data-action="stage-prompt"]').click()
            check("prompt layer and independent draft are reachable", "执行快照 · 不可改写" in page.inner_text("main") and page.locator("#prompt-draft").is_visible())
            check("prompt has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            screenshot("prompt")
            link = page.get_by_role("link", name="异常与整稿操作样板", exact=True)
            check("state sample link resolves within imported project", urljoin(page.url, link.get_attribute("href")) == urljoin(url, "states.html"))
            link.click()
            page.wait_for_url("**/states.html")
            page.wait_for_load_state("networkidle")
            check("state sample entry is clearly simulated", "全部为模拟" in page.inner_text(".state-banner"))
            check("text-only sample contains no fake image preview", page.locator("main img, main svg, main canvas").count() == 0)
            title = f"OpenDesign 预览核验 · {width}"
            body = "两个区域先试点。\n正文保存与真实生成分开。"
            page.locator("#text-title").fill(title)
            page.locator("#text-body").fill(body)
            page.get_by_role("button", name="保存正文（样本）", exact=True).click()
            check("sample save creates R17", "正文 R17" in page.inner_text("main"))
            page.reload(wait_until="networkidle")
            check("sample draft and saved value survive reload", page.locator("#text-title").input_value() == title and page.locator("#text-body").input_value() == body and "正文 R17" in page.inner_text("main"))
            check("state sample has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            screenshot("state-text-saved")
            check("zero browser page errors", not row["page_errors"])
            check("zero external resource requests", not row["external_resource_requests"])
            check("zero resource HTTP failures", not row["resource_http_failures"])
            check("zero failed network requests", not row["request_failures"])
            row["status"] = "passed"
        except Exception as error:
            row["status"] = "failed"
            row["error"] = str(error)
            try:
                screenshot("failure")
            except Exception:
                pass
        finally:
            result["viewports"].append(row)
            ctx.close()

    ctx = browser.new_context()
    for name, expected in manifest["sha256"].items():
        response = ctx.request.get(urljoin(url, name))
        actual = hashlib.sha256(response.body()).hexdigest()
        result["asset_http_hash_checks"].append({
            "file": name, "http_status": response.status,
            "sha256": actual, "expected_sha256": expected,
            "matches_import_manifest": response.status == 200 and actual == expected,
        })
    ctx.close()
    browser.close()

result["status"] = "passed" if all(v["status"] == "passed" for v in result["viewports"]) and all(a["matches_import_manifest"] for a in result["asset_http_hash_checks"]) else "failed"
result["limitations"] = [
    "Confirms imported preview, resources and synthetic interactions only",
    "No OpenDesign generation run, real Host, model, production service or export was executed",
    "Preview URL is valid for the current daemon session",
]
(HERE / "browser-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "viewports": [{"viewport": v["viewport"], "status": v["status"], "checks": len(v["checks"]), "error": v.get("error")} for v in result["viewports"]], "six_assets_match": all(a["matches_import_manifest"] for a in result["asset_http_hash_checks"])}, ensure_ascii=False))
