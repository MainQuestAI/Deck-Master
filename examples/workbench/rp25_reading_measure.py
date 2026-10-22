"""RP-25: 30-page synthetic browser read workload; no Host or model calls.

Run with a fresh output directory argument. Requires system Chromium.
Times include Python server + driver CPU separately from Chromium TaskDuration;
not a total machine CPU benchmark. No historical 19-second baseline is used.
"""

import json, time, sys, collections, hashlib
from datetime import datetime, timezone
import deck_master
from pathlib import Path
from urllib.parse import urlsplit
from deck_master.samples import create_sample
from deck_master.web import WorkbenchServer
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1])
out.mkdir()
project = out / "project"
create_sample(project, page_count=30)
server = WorkbenchServer(project)
counts = collections.Counter()
rows = []
errors = []
started = datetime.now(timezone.utc).isoformat()
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        cdp = page.context.new_cdp_session(page)
        cdp.send("Performance.enable")

        def metrics():
            return {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}

        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda r: counts.update([urlsplit(r.url).path]))

        def measure(name, action):
            counts.clear()
            m = metrics()
            start = time.monotonic()
            cpu = time.process_time()
            action()
            end = metrics()
            rows.append(
                dict(
                    name=name,
                    wall=time.monotonic() - start,
                    server_cpu=time.process_time() - cpu,
                    browser_task=end["TaskDuration"] - m["TaskDuration"],
                    requests=dict(counts),
                    pool=page.evaluate("async()=> (await import('/v2/images.js')).imagePool.snapshot()"),
                )
            )

        def ready():
            page.wait_for_function(
                "()=>document.querySelectorAll('.slide-tile canvas').length>0 && !document.querySelector('.slide-tile [data-image-state=loading]')"
            )

            assert page.locator(".slide-tile [data-image-state=failed]").count() == 0

        def cold():
            page.goto(server.start() + "studio/")
            page.get_by_role("button", name="整稿画廊", exact=True).click()
            ready()

        measure("cold", cold)

        def warm():
            for _ in range(3):
                page.get_by_role("button", name="制作总览", exact=True).click()
                page.wait_for_function("()=>!document.querySelector('.gallery-view')")
                page.get_by_role("button", name="整稿画廊", exact=True).click()
                ready()

        measure("warm_3_roundtrips", warm)
        measure("idle_16s", lambda: page.wait_for_timeout(16000))
        assert not errors, errors
        assert rows[2]["requests"].get("/api/thumbnails", 0) == 0
        assert rows[2]["requests"].get("/api/thumbnail-file", 0) == 0
        assert rows[2]["requests"].get("/api/view/summary", 0) == 1
        assert all(row["pool"]["network_peak"] <= 6 and row["pool"]["decode_peak"] <= 2 for row in rows)
        (out / "provenance.json").write_text(
            json.dumps(
                {
                    "module": deck_master.__file__,
                    "started_utc": started,
                    "completed_utc": datetime.now(timezone.utc).isoformat(),
                    "images_sha256": hashlib.sha256(
                        (Path(deck_master.__file__).parent / "resources/static/v2/images.js").read_bytes()
                    ).hexdigest(),
                    "synthetic_pages": 30,
                    "model_calls": 0,
                    "errors": errors,
                },
                indent=2,
            )
        )
        (out / "measure.json").write_text(json.dumps(rows, indent=2))
        print(json.dumps(rows, indent=2))
        browser.close()
finally:
    server.stop()
