# B0-1 夹具说明

本夹具全部为合成数据，不含任何客户材料。正文模板来自仓库内 `docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/compose.json`（其中 p09 页），图片由脚本现场生成。

## 1. 结构

| 页 | 标题 | blueprint | svg | svg_preview | ppt_preview | 用途 |
| --- | --- | --- | --- | --- | --- | --- |
| p01 | 将设备条件收集前移，减少总部重复补问 | 有 | — | — | 有 | 首次打开页 |
| p02 | 服务点提交流程需要补齐版本信息 | 有 | 有 | 有 | 有 | 全槽位页（第 2、3、8 步） |
| p03 | 知识助手按条件匹配资料并给出引用 | — | 有 | 有 | — | 草稿与待处理任务页（第 7 步） |
| p04 | 总部专家接手的问题带完整上下文 | — | — | — | — | 只有正文（第 4、5 步） |

其他状态：
- 整套 `outputs.pptx`：真实 python-pptx 生成的 4 页 deck。
- `ppt_preview`：用 `soffice --headless --convert-to pdf` 把这份 deck 转成 PDF，再用 `pdftoppm -r 96` 渲染成 PNG。不是手工图片。
- `svg_preview`：用 `rsvg-convert -w 1280` 渲染。
- 审阅 `rv-b01`：kind 为 readability，status 为 fail，subjects 为 `[pptx, p02 page]`。含一条未关闭的发现 `f-b01`：impact 为 must_fix，页面为 p02，element 为 `atom:p02:block:service:heading`，resolution 为 open。
- 待处理任务：用 `service.open_host_task` 打开一个 repair 任务，作用于 `["p03"]`，instruction 为“夹具任务：把 p03 的脚注移到页面底部”，状态为 `awaiting_host`。

## 2. 环境依赖

- 仓库 `.venv`（Python 3.12.12）。已包含 `pillow`、`python-pptx`（仓库依赖）。
- 命令行工具：`rsvg-convert`（librsvg）、`soffice`（LibreOffice）、`pdftoppm`（poppler）。
- 浏览器走查用的 Playwright 1.63.0 装在独立 venv 里（`uv venv -p 3.12 /tmp/dm-b0-1/pwvenv && uv pip install -p /tmp/dm-b0-1/pwvenv playwright`），使用 Chromium 153.0.8010.12。

## 3. 重建步骤

```bash
mkdir -p /tmp/dm-b0-1
# 把第 4 节的脚本保存为 /tmp/dm-b0-1/build_fixture.py
<repo>/.venv/bin/python /tmp/dm-b0-1/build_fixture.py      # 每次运行都会删除并重建 /tmp/dm-b0-1/project 和 work/
<repo>/.venv/bin/deck-master --json view --project /tmp/dm-b0-1/project --open --no-open   # 启动服务，输出 review_url
curl -s <review_url>api/health                                # {"status":"ok","project_identity":"…"}
# 结束后关闭服务：
<repo>/.venv/bin/python -c "import sys;sys.path.insert(0,'<repo>/src');from deck_master.web import stop_service;print(stop_service('/tmp/dm-b0-1/project'))"
```

注意：`deck-master view --project P --no-open` 实测**不会启动服务**，只返回 `view_status: not_running`。必须同时带 `--open --no-open` 才会启动（见 05 文档新发现 N01）。

脚本末尾会打印一段 JSON，重建成功时内容应为：

```json
{"view_status": "awaiting_host",
 "pages": {"p01": ["blueprint","ppt_preview"], "p02": ["blueprint","svg","svg_preview","ppt_preview"], "p03": ["svg","svg_preview"], "p04": []},
 "pending": [["repair","awaiting_host"]],
 "reviews": [["rv-b01","fail",["p02"],true]],
 "pptx": true}
```

`revision_id` 与 task_id 每次重建都会重新生成（带随机成分），所以不同构建之间对不上是正常的。三次走查记录到的值如下：

| 用途 | 起始 revision_id（前 12 位） | 夹具任务 task_id |
| --- | --- | --- |
| 1280×800 走查 | 24189de3624f（完整值 24189de3624f4427a367d6a281c0e9e6） | 9c3e723d8e4f |
| 1440×900 走查 | 12ea250df986 | — |
| 补测（G3、未编辑导出、审阅记录） | 夹具任务打开后的 revision；走查后变为 c6f6d769bfbf | 0287f0aa55f1 |

## 4. 构造脚本（原样，未提交到仓库）

```python
"""B0-1 fixture: 4-page synthetic project built with the same public calls as
tests/rebuild/test_workbench_e2e.py (service.create -> continue -> accept compose),
then slot attachment like _four_slot_project, a review with an open finding,
and one awaiting_host repair task."""
import copy, json, shutil, subprocess, sys
from pathlib import Path
REPO = Path("/Users/dingcheng/dm-webui-b0-1")  # 改为你的仓库 worktree 路径
sys.path.insert(0, str(REPO / "src"))
import deck_master.service as service
from deck_master.store import Store
from deck_master.models import bump_revision
from deck_master.pipeline import artifact as adopt
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/tmp/dm-b0-1")
PROJECT = ROOT / "project"
WORK = ROOT / "work"
if PROJECT.exists(): shutil.rmtree(PROJECT)
if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir(parents=True)
ENV = REPO / "docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/compose.json"

material = WORK / "material.txt"
material.write_text("正文材料\n(尾部约束)合成数据不可回写。", encoding="utf-8")
service.create(PROJECT, brief="设备运维汇报（B0-1 合成夹具）", sources=[material])
resp = service.continue_project(PROJECT)
task = resp["pending_tasks"][0]
base = json.loads(ENV.read_text())
tmpl = base["pages"][0]
ids = ["p01", "p02", "p03", "p04"]
titles = ["将设备条件收集前移，减少总部重复补问", "服务点提交流程需要补齐版本信息",
          "知识助手按条件匹配资料并给出引用", "总部专家接手的问题带完整上下文"]
pages = []
for pid, title in zip(ids, titles):
    p = json.loads(json.dumps(tmpl, ensure_ascii=False).replace("p09", pid))
    p["customer_visible"]["title"] = title
    pages.append(p)
env = copy.deepcopy(base); env["pages"] = pages; env["page_order"] = ids
service.accept_result(PROJECT, task_id=task["task_id"], operation_id=task["operation_id"],
                      produced_against=task["produced_against"], result_payload=env)
store = Store(PROJECT)

# --- slot artifacts --------------------------------------------------------
def font(sz):
    for f in ("/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/PingFang.ttc"):
        if Path(f).exists(): return ImageFont.truetype(f, sz)
    return ImageFont.load_default()

def blueprint_png(pid, title):
    img = Image.new("RGB", (1280, 720), (238, 232, 220)); d = ImageDraw.Draw(img)
    d.text((60, 50), f"原图（夹具蓝图）· {pid}", fill=(80, 60, 40), font=font(28))
    d.text((60, 110), title, fill=(30, 30, 30), font=font(40))
    for i, x in enumerate((80, 480, 880)):
        d.rectangle((x, 260, x + 320, 460), outline=(120, 90, 60), width=4)
        d.text((x + 20, 340), ["服务点", "知识助手", "总部专家"][i], fill=(60, 40, 20), font=font(32))
    out = WORK / f"{pid}-blueprint.png"; img.save(out); return out

def svg_file(pid, title):
    s = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
<rect width="1280" height="720" fill="#12213d"/>
<text x="60" y="90" font-size="42" fill="#ffffff" font-family="Hiragino Sans GB, PingFang SC, sans-serif">{title}</text>
<text x="60" y="140" font-size="24" fill="#9fb3d9" font-family="Hiragino Sans GB, sans-serif">SVG 制作结果（夹具）· {pid}</text>
<rect x="80" y="260" width="320" height="200" rx="12" fill="#2a4a80"/><text x="130" y="370" font-size="32" fill="#fff" font-family="Hiragino Sans GB, sans-serif">服务点提交</text>
<rect x="480" y="260" width="320" height="200" rx="12" fill="#2a6a80"/><text x="540" y="370" font-size="32" fill="#fff" font-family="Hiragino Sans GB, sans-serif">知识助手</text>
<rect x="880" y="260" width="320" height="200" rx="12" fill="#5a4a80"/><text x="940" y="370" font-size="32" fill="#fff" font-family="Hiragino Sans GB, sans-serif">总部专家</text>
<text x="60" y="660" font-size="20" fill="#9fb3d9" font-family="Hiragino Sans GB, sans-serif">演示数据；54÷120=45%，不代表自动解决率。</text>
</svg>'''
    out = WORK / f"{pid}.svg"; out.write_text(s, encoding="utf-8"); return out

def svg_preview(svg):
    out = svg.with_name(svg.stem + "-svg-preview.png")
    subprocess.run(["rsvg-convert", "-w", "1280", "-o", str(out), str(svg)], check=True); return out

# real PPTX -> soffice PDF -> pdftoppm PNG for ppt_preview
from pptx import Presentation
from pptx.util import Inches, Pt
prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
for pid, title in zip(ids, titles):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    tb = sl.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(12), Inches(1.2))
    tb.text_frame.text = title; tb.text_frame.paragraphs[0].runs[0].font.size = Pt(36)
    tb2 = sl.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(12), Inches(0.8))
    tb2.text_frame.text = f"PPT 成品（夹具 python-pptx 生成，经 soffice 渲染）· {pid}"
    for i, name in enumerate(["服务点提交", "知识助手", "总部专家"]):
        box = sl.shapes.add_shape(1, Inches(0.8 + i * 4.1), Inches(3), Inches(3.6), Inches(2))
        box.text_frame.text = name
pptx_path = WORK / "deck.pptx"; prs.save(pptx_path)
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(WORK), str(pptx_path)],
               check=True, capture_output=True)
subprocess.run(["pdftoppm", "-png", "-r", "96", str(WORK / "deck.pdf"), str(WORK / "ppt")], check=True)
renders = sorted(WORK.glob("ppt-*.png"))
assert len(renders) == 4, renders

doc = store.load_document()
b = bump_revision(doc, {"operation_id": "b01-attach-slots", "kind": "task_update",
                        "description": "B0-1 fixture slots", "read_set": []})
E = {e["page_id"]: e for e in b["pages"]}
# p01: blueprint + ppt_preview; p02: all slots; p03: svg + svg_preview; p04: content only
E["p01"]["blueprint"] = adopt(store, blueprint_png("p01", titles[0]), "blueprint", page_id="p01")
E["p01"]["ppt_preview"] = adopt(store, renders[0], "ppt_preview", page_id="p01")
bp2 = blueprint_png("p02", titles[1]); s2 = svg_file("p02", titles[1])
E["p02"]["blueprint"] = adopt(store, bp2, "blueprint", page_id="p02")
E["p02"]["svg"] = adopt(store, s2, "svg", page_id="p02")
E["p02"]["svg_preview"] = adopt(store, svg_preview(s2), "svg_preview", page_id="p02")
E["p02"]["ppt_preview"] = adopt(store, renders[1], "ppt_preview", page_id="p02")
s3 = svg_file("p03", titles[2])
E["p03"]["svg"] = adopt(store, s3, "svg", page_id="p03")
E["p03"]["svg_preview"] = adopt(store, svg_preview(s3), "svg_preview", page_id="p03")
b["outputs"]["pptx"] = adopt(store, pptx_path, "pptx")
store.commit_change(base_revision=doc["revision_id"], document=b, operation_id="b01-attach-slots")

# --- review with an open finding (same shape as test_review_findings_are_addressable) --
doc = store.load_document(); p2 = next(e for e in doc["pages"] if e["page_id"] == "p02")
review = {"schema_version": "deck_review.v1", "review_id": "rv-b01", "kind": "readability", "status": "fail",
          "subjects": [doc["outputs"]["pptx"], p2["page"]],
          "dependencies": [{"kind": "content", "identity": "page:p02", "sha256": p2["page"]["sha256"]}],
          "reviewer": {"type": "host_self", "id": "host-1", "execution_ref": None, "independence_confirmed": False},
          "observations": ["夹具审阅记录：p02 标题字号偏小"],
          "findings": [{"finding_id": "f-b01", "kind": "readability", "impact": "must_fix", "page_id": "p02",
                        "element_refs": ["atom:p02:block:service:heading"], "message": "字号过小",
                        "expected": "≥10pt", "actual": "6pt", "evidence": [], "resolution": "open"}],
          "created_at": "2026-09-25T00:00:00Z", "replaces": None}
ref = store.put_json_object(review)
b = bump_revision(doc, {"operation_id": "b01-add-review", "kind": "task_update", "description": "B0-1 fixture review", "read_set": []})
b["reviews"] = [ref]
store.commit_change(base_revision=doc["revision_id"], document=b, operation_id="b01-add-review")

# --- one awaiting_host repair task ------------------------------------------
t = service.open_host_task(store, kind="repair", page_ids=["p03"], instruction="夹具任务：把 p03 的脚注移到页面底部")
doc = store.load_document()
from deck_master.view import project_view
v = project_view(PROJECT)
print(json.dumps({"revision_id": doc["revision_id"], "fixture_task": t["task_id"], "view_status": v["view_status"],
                  "pages": {p["page_id"]: [k for k, r in p["slots"].items() if r] for p in v["pages"]},
                  "pending": [(x["kind"], x["status"]) for x in v["pending_tasks"]],
                  "reviews": [(r["review_id"], r["status"], r["page_ids"], r["current_output"]) for r in v["reviews"]],
                  "pptx": bool(v["outputs"].get("pptx"))}, ensure_ascii=False, indent=1))
```
