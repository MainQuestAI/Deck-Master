from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from workspace_audit_scenarios import generate_workspace_audit_runs

ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPT = ROOT / "scripts" / "preview" / "server.py"

BREAKPOINTS = [
    {"id": "desktop-1600", "width": 1600, "height": 1280, "label": "1600 宽桌面"},
    {"id": "desktop-1440", "width": 1440, "height": 1280, "label": "1440 宽桌面"},
    {"id": "desktop-1280", "width": 1280, "height": 1180, "label": "1280 宽桌面"},
]

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

PLAYWRIGHT_WAIT_SELECTORS = {
    "empty": "text=请选择或创建一个方案项目",
    "run-init-wait-preview": "text=待准备",
    "generation-running": "text=生成中",
    "needs-review": "text=待审阅",
    "needs-evidence": "text=待补证据",
    "pending-approval": "text=待审批",
    "export-ready": "text=可交付",
    "delivered-review": "text=已交付",
}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _materialize_scene_runs(scene_root: Path, scenario_manifest: dict[str, Any]) -> dict[str, Path]:
    scene_dirs: dict[str, Path] = {}
    for item in scenario_manifest["runs"]:
        slug = str(item["run_id"])
        source_dir = Path(item["run_dir"])
        target_parent = scene_root / slug
        target_run_dir = target_parent / slug
        target_parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, target_run_dir)
        scene_dirs[slug] = target_parent
    return scene_dirs


def _find_chrome(explicit_path: str | None = None) -> str:
    if explicit_path:
        chrome_path = Path(explicit_path).expanduser().resolve()
        if chrome_path.exists():
            return str(chrome_path)
        raise FileNotFoundError(f"指定的 Chrome 路径不存在: {chrome_path}")
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("未找到可用的 Chrome/Chromium，可通过 --chrome-path 指定。")


def _find_playwright() -> str | None:
    for candidate in ("playwright", str(Path.home() / ".npm-global" / "bin" / "playwright")):
        path = shutil.which(candidate) if candidate == "playwright" else candidate
        if path and Path(path).exists():
            return str(Path(path).resolve())
    return None


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(base_url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/runs", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = str(exc)
        time.sleep(0.3)
    raise RuntimeError(f"预览服务未在 {timeout_seconds:.0f} 秒内启动: {last_error}")


def _start_server(runs_dir: Path, port: int) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT), "--runs-dir", str(runs_dir), "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )


def _stop_server(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _capture_with_playwright(
    playwright_path: str,
    url: str,
    output_path: Path,
    *,
    width: int,
    height: int,
    wait_selector: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        playwright_path,
        "screenshot",
        "--browser",
        "chromium",
        "--channel",
        "chrome",
        "--color-scheme",
        "dark",
        "--timeout",
        "30000",
        "--wait-for-timeout",
        "1200",
        "--wait-for-selector",
        wait_selector,
        "--viewport-size",
        f"{width},{height}",
        url,
        str(output_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Playwright 截图失败")
    if not output_path.exists():
        raise RuntimeError(f"截图未生成: {output_path}")


def _capture_screenshot(chrome_path: str, url: str, output_path: Path, width: int, height: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={width},{height}",
        "--virtual-time-budget=5000",
        f"--screenshot={output_path}",
        url,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Chrome 截图失败")
    if not output_path.exists():
        raise RuntimeError(f"截图未生成: {output_path}")


def _render_readme(report: dict[str, Any]) -> str:
    lines = [
        "# 桌面方案工作台截图审计矩阵",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 预览入口：`{report['base_url']}`",
        f"- 截图引擎：`{report['capture_engine']}`",
        f"- 总截图数：{report['counts']['screenshots']}",
        "",
        "## 场景清单",
        "",
        "| 场景 | 断点 | 文件 |",
        "| --- | --- | --- |",
    ]
    for scene in report["scenes"]:
        for capture in scene["captures"]:
            lines.append(
                f"| {scene['label']} | {capture['breakpoint_label']} | `{capture['relative_path']}` |"
            )
    lines.extend(
        [
            "",
            "## 审计维度",
            "",
            "- 首屏焦点",
            "- 状态可理解性",
            "- 预览可见性",
            "- 操作层级",
            "- 风险可追溯性",
            "- 审批完整度",
            "- MainQuest 视觉一致性",
            "- 专业工具质感",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_workspace_screenshot_audit(output_root: str | Path, *, chrome_path: str | None = None) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    screenshots_dir = root / "screenshots"
    generated_runs_dir = root / "generated-runs"
    empty_runs_dir = root / "empty-runs"
    scene_runs_dir = root / "scene-runs"

    if root.exists():
        shutil.rmtree(root)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    empty_runs_dir.mkdir(parents=True, exist_ok=True)

    playwright_path = _find_playwright()
    chrome = _find_chrome(chrome_path) if not playwright_path else ""
    scenario_manifest = generate_workspace_audit_runs(generated_runs_dir)
    scene_dirs = _materialize_scene_runs(scene_runs_dir, scenario_manifest)
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    report = {
        "schema_version": "deck_master_workspace_screenshot_audit.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output_root": str(root),
        "base_url": base_url,
        "capture_engine": playwright_path or chrome,
        "scenario_manifest": str(generated_runs_dir / "audit_runs_manifest.json"),
        "counts": {"scenes": 0, "screenshots": 0},
        "scenes": [],
    }

    captures: list[tuple[str, str, str]] = [("无项目空态", "", "empty")]
    captures.extend((item["label"], item["url_query"], item["run_id"]) for item in scenario_manifest["runs"])

    process: subprocess.Popen[bytes] | None = None
    current_server_key = ""
    try:
        for scene_label, url_query, slug in captures:
            server_key = "empty" if slug == "empty" else slug
            if server_key != current_server_key:
                _stop_server(process)
                runs_dir = empty_runs_dir if server_key == "empty" else scene_dirs[slug]
                process = _start_server(runs_dir, port)
                _wait_for_server(base_url)
                current_server_key = server_key

            scene_entry = {"slug": slug, "label": scene_label, "url_query": url_query, "captures": []}
            for breakpoint in BREAKPOINTS:
                relative_path = f"screenshots/{slug}-{breakpoint['id']}.png"
                output_path = root / relative_path
                url = f"{base_url}/{url_query}" if url_query else f"{base_url}/"
                wait_selector = PLAYWRIGHT_WAIT_SELECTORS.get(slug, "body")
                if playwright_path:
                    try:
                        _capture_with_playwright(
                            playwright_path,
                            url,
                            output_path,
                            width=breakpoint["width"],
                            height=breakpoint["height"],
                            wait_selector=wait_selector,
                        )
                    except RuntimeError:
                        if not chrome:
                            raise
                        _capture_screenshot(
                            chrome,
                            url,
                            output_path,
                            breakpoint["width"],
                            breakpoint["height"],
                        )
                else:
                    _capture_screenshot(
                        chrome,
                        url,
                        output_path,
                        breakpoint["width"],
                        breakpoint["height"],
                    )
                scene_entry["captures"].append(
                    {
                        "breakpoint_id": breakpoint["id"],
                        "breakpoint_label": breakpoint["label"],
                        "width": breakpoint["width"],
                        "height": breakpoint["height"],
                        "relative_path": relative_path,
                        "absolute_path": str(output_path),
                    }
                )
                report["counts"]["screenshots"] += 1
            report["scenes"].append(scene_entry)
            report["counts"]["scenes"] += 1
    finally:
        _stop_server(process)

    _write_json(root / "audit_report.json", report)
    _write_text(root / "README.md", _render_readme(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="生成方案工作台桌面截图审计矩阵。")
    parser.add_argument("output_root", help="输出目录，包含截图和样例项目")
    parser.add_argument("--chrome-path", default=None, help="Optional Chrome/Chromium executable path")
    args = parser.parse_args()
    report = generate_workspace_screenshot_audit(args.output_root, chrome_path=args.chrome_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
