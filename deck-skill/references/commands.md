# 内容主链命令

## 开发期环境准备

以下是开发期安装命令，已有可用环境时从“新建与读材料”开始。

在仓库 worktree 中先准备本地工具；不要共用另一个 checkout 的 Python 环境：

```bash
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install -e './deck-tools[dev]'
cargo install --path rust --root "$PWD/.dev-prefix"
export PATH="$PWD/.dev-prefix/bin:$PATH"
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
mkdir -p ~/.codex/skills
for role in deck-master deck-content deck-design deck-review; do
  ln -s "$PWD/deck-skill/$role" "$HOME/.codex/skills/$role"
done
```

`scripts/install.sh` 默认将四个职责目录整体软链接到 `~/.codex/skills`，`--skills-root DIR` 更换目录。不再安装兼容入口 `deck`，`--skill-dir` 已取消。上面的手动链接示例适用于尚无同名入口的开发环境；升级请运行安装脚本。

标准安装的四职责入口经 current 指向同一份完整安装副本；重复安装保留 current 链接，旧本源链接迁移到 current。只删除指向本源 `deck-skill/` 的旧 `deck` 软链接，并将仅含三条托管链接的旧包装目录升级为整目录软链接。包装目录有用户文件，或同名路径被其他入口（包括旧 Python 线）占用时，脚本在写入前退出 2，打印路径和目标。先移走该项；若为软链接，只删链接，不删目标目录，再安装。非本源的 `deck` 保留并提示可能抢触发。

标准安装下文的 `deck` 指 `~/.local/bin/deck`；上述开发示例使用独立 `.dev-prefix/bin/deck`，不能覆盖标准薄入口。安装用了非默认 `--prefix` 时，二进制在 `<prefix>/bin/deck`。新开的会话沿用自己的 PATH，不会保留安装时临时 export。先运行 `command -v deck`：结果若不是 `<prefix>/bin/deck`，下面每条命令都用 `<prefix>/bin/deck`。`DECK_PROJECT` 是作者指定的新作品目录，`SOURCE_FILE` 是作者指定的一份原材料；不要根据示例搜索 HOME 或补读相邻目录。

## 新建与读材料

```bash
deck new "$DECK_PROJECT" --title '方案内容稿'
deck --project "$DECK_PROJECT" material add "$SOURCE_FILE"
deck --project "$DECK_PROJECT" material text m1
```

`material add` 返回材料与抽取结果；`material text` 返回 `{id, status, path}`。实际读取该 path，必要时查看指定原件；解析状态不是内容正确性或业务验收。对每份指定材料重复上述动作，材料编号使用命令实际返回值。

## 保存作者任务与框架

```bash
deck --project "$DECK_PROJECT" get > "$DECK_PROJECT/current.json"
```

从返回的 `version` 取基线。下面是合成示例，实际工作用已读材料改写，保存为作品目录中的 `framing.json`：

```json
{
  "brief": {
    "title": "设备资料检索一期建议",
    "audience": "业务与 IT 负责人",
    "task_type": "首次提案",
    "goal": "判断是否先验证资料适用性检索及后续摘要的价值",
    "constraints": ["本期只读，正式处理由人工执行"],
    "page_limit": null
  },
  "framing": {
    "thesis": "建议先验证资料适用性检索，再按实际增量决定是否增加生成摘要。",
    "pillars": [{
      "title": "版本与权限决定资料能否用于当前任务",
      "points": ["先取得设备条件，再返回适用原文；摘要不能替代适用性核对。"]
    }],
    "facts": ["合成材料要求只读，没有要求必须生成答案。"],
    "assumptions": ["能够取得设备型号与版本，并维护资料适用范围。"],
    "questions": ["跨文档摘要能否减少包含核查在内的总处理时间？"]
  }
}
```

```bash
BASE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$DECK_PROJECT/current.json")
deck --project "$DECK_PROJECT" put --base "$BASE" "$DECK_PROJECT/framing.json"
```

`brief`、`framing`、`style` 是完整单元，内部省略字段会按默认值处理；改目标时先读取原 brief 再修改，不能只交一个 goal 丢掉其他任务信息。不改的顶层单元直接省略。

## 写正文

再 `get` 读取保存后的版本，写 `pages.json`。下面用段落、要点和表格各说明一种实际内容关系；不是每页必须出现这三类块。

```json
{
  "order": ["p1", "p2"],
  "pages": [
    {
      "id": "p1",
      "purpose": "解释一期为何先解决资料适用性",
      "layout": "先说判断，再按使用步骤解释",
      "content": {
        "title": "先找到适用资料，再判断摘要能增加什么",
        "body_blocks": [
          {"type": "paragraph", "text": "只读检索可先返回适用原文。生成摘要是额外能力，其价值需扣除核查与维护工作后判断。"},
          {"type": "bullets", "heading": "拟议用法", "items": [
            {"text": "记录型号和版本，筛选可访问且适用的资料。"},
            {"text": "展示原文出处，由人工核对后沿现有流程处理。"}
          ]}
        ]
      },
      "refs": ["合成材料：只读范围"],
      "todo": ["确认资料适用范围的维护安排"]
    },
    {
      "id": "p2",
      "purpose": "说明不同条件下的下一步选择",
      "layout": "按同一任务比较两种条件与动作",
      "content": {
        "title": "是否扩展摘要，取决于完整任务的净增量",
        "body_blocks": [{
          "type": "table",
          "columns": [{"label": "观察条件"}, {"label": "建议动作"}],
          "rows": [
            {"cells": [{"display_text": "检索已够用，摘要增加核查工作"}, {"display_text": "保留检索，先改善资料适用性"}]},
            {"cells": [{"display_text": "摘要减少总处理时间且依据可核查"}, {"display_text": "再核对扩展范围与维护成本"}]}
          ]
        }]
      },
      "refs": ["本稿建议，实际增量待验证"]
    }
  ]
}
```

```bash
deck --project "$DECK_PROJECT" get > "$DECK_PROJECT/current.json"
BASE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$DECK_PROJECT/current.json")
deck --project "$DECK_PROJECT" put --base "$BASE" "$DECK_PROJECT/pages.json"
deck --project "$DECK_PROJECT" show
deck --project "$DECK_PROJECT" export md > "$DECK_PROJECT/manuscript.md"
```

页 id 用于选页，沿用已有值；新增页使用未占用值。块、条目、表格列、行与单元格不用手写 id，保存会补齐。表格单元格不填 column_id 时按列顺序对应；从已有页改表格则沿用其列引用。

## 局部修改

`deck --project "$DECK_PROJECT" get --pages p2` 只返回所选页，但保留任务与框架，并省略 order。读取后修改目标页的作者字段，再用此次返回的 version 保存；不需要读写其他页。

- 只改文字时，提交该页完整 `content`；只改讲稿时，只交该页 id 与 notes。
- 新增页：交新页面及包含它的完整 order；删除页：交 `{id}` 和去掉该页的完整 order；重排只交 order。
- `put` 也接受 get 的完整输出。不改 materials、image、svg、native 或 preview；保存不会用它们更新材料或产物。
- 同一提交可以安全重试，没有实质变化就不新增版本。冲突时命令退出 5 并给当前冲突单元，先读取后合并作者意图，再保存。
- `deck --project "$DECK_PROJECT" restore N` 把历史稿恢复为新版本，不删除后来的历史。

`export md` 向 stdout 输出正文、讲稿、待补与出处，不要求稿件完整。重定向前选一个新文件名；交稿前实际阅读该文件。当前内容阶段无需渲染器、生图、编译或界面。

## 原图、SVG 与构建

内容完成不自动进入这一节。设计入口在授权范围内使用。

按 [视觉资产](visual-assets.md) 选择实际需要的资源：`deck asset add <素材ID> <文件> --page p1 --page p3 --source <来源> --license <许可>`。`--page` 可重复或逗号分隔，省略则为公共素材；同 ID 替换整条记录，保留的范围、来源和许可需一起传入。SVG 添加时渲染成 PNG，PNG/JPEG 保持原样。任务只附上本页有效素材，以 attachments.json 为准。

1. `deck run start image --pages p1,p2` 准备任务。读取该次工作目录里的完整 task.md，按 attachments.json 定位素材。每次调用前 `deck run call <run> <page>`，再把 task.md 原文作为 ImageGen 的 prompt，把清单中的文件作为附件。结果未知时先核实，决定重试才加 `--retry`。
2. `deck run result <run> <page> <图片文件>` 交回。首次结果可以自动采用；重交的修正版、取消后或依据已变的结果只保存。确认使用后 `deck run adopt <run> <page>`。`deck run show` 看状态，`deck run cancel <run>` 停止后续调用和自动采用。
3. `deck run start svg --pages p1,p2` 准备 SVG。按原图的布局和关系重建，正文取 content.json，文字绑定 atoms.json。先读 [svg-subset.md](svg-subset.md)。错漏文字、局部排版和依据明确的连线可以沿用原图直接改。主结构要重排时先改蓝图。
4. `deck run result <run> <page> <SVG文件>` 编译、渲染并回读。工具报错就改具体元素。Host 打开预览 PNG，对照原图检查端点、方向、分支、层级、侧栏和阅读顺序。
5. `deck build` 构建 PPTX，`deck export pptx` 优先取当前构建输入匹配的成品路径，没有匹配时取最近历史成品并提示。`missing_pages` 是没有 SVG（native 作品则是没有已采用 native）、因此没有进入这次 PPTX 的页。`stale_pages` 是已采用 SVG 或 native 的依据与当前正文、目的、布局、原图文件或样式不一致。`stale_images` 只比较原图依据。它在 `deck get` / `deck show` 的 `artifact_status` 里，也在 `deck build` 和 `deck export pptx` 里。这两条命令另给 `warnings`：`code` 为 `stale_image`、`level` 为 `warning`，列出原图依据已变的页号。不并入 `stale_pages`，不改变退出码，也不把回读 status 从 pass 改成 fail。只改讲稿不会让原图或页面过期。构建成功不会清掉这两项。`export pptx` 的 `input_changed` 才表示构建之后 SVG、native、讲稿或构建设置又变了。

`soffice` 不可用时，SVG 的 `deck run result` 失败并说明如何安装 LibreOffice。停在这一步。不要改调 `compile_job`，不要手写 PPTX。
已完成的 SVG 任务重交同一文件时，返回 `reused: true` 并沿用原回读，不重新检查，也不返回本次 `checked_version`；缺原回读时 findings 为 null。该返回不表示当前正文已经重新检查。

## 意见

`deck review list --status open` 读取未处理意见，可用 `--page` 限定。作者明确要求保存时：

```bash
deck review add --method self_check --page p3 '这一页的问题'
```

当前 Host 自查用 `self_check`，另一执行或模型用 `other_model`，真人用 `human`。`--method` 必填，没有默认值，省略会报错。落实并核对之后才 `deck review resolve <意见ID>`。审查默认只返回报告，不因为开了审查入口就改稿或生图。

## 可选：核对案例算式

用装有 deck-tools 的解释器：

```bash
python -m deck_tools.case_numbers path/to/numbers.json
```

只读该文件。退出码 0 表示显式算式与期望一致，1 表示不一致，2 表示输入无效。不写回文件，也不判断来源、归因或 ROI。写稿、导出和审查都不依赖这次运行。


`deck material text <id>` 返回抽取文本 path 和项目内不可变原件副本 original_path。
原件缺失时 original_path 为 null，已有文本仍可读；解析未完成仍报 needs_tool。
解析成功不代表已看过图，系统不保存历史视觉阅读是否完成；按本次任务查看必要图表、流程或扫描页，纯 TXT/MD 不增加看图要求。


PPTX 默认优先下载与当前构建输入匹配的成品，没有匹配时下载最近可用历史成品并提示。
input_changed 只表示构建输入匹配，不表示正文或视觉已最新；来源 version_id 标识构建时作品版本。


## 读取和修改作品风格

标准安装会自动定位自己的工具环境，无需设置开发用 DECK_TOOLS_PYTHON。
先读取完整作品，保留当前 canvas、fonts 和 assets，再修改需要的字段：

```bash
deck get > snapshot.json
python3 - <<'PYTHON'
import json
from pathlib import Path
snapshot = json.loads(Path("snapshot.json").read_text())
style = snapshot["deck"]["style"]
style["palette"] = ["#164267", "#F5F7FA", "#D97706"]
Path("style-patch.json").write_text(json.dumps({"style": style}, ensure_ascii=False))
print(snapshot["version"])
PYTHON
deck put --base <上一步输出的版本号> style-patch.json
deck doctor --fonts "Noto Sans CJK SC"
```

色板为无品牌示例；品牌项目使用自己的值。doctor 的字体参数换成当前实际选用的字体；缺工具或字体按错误提示处理。修改已有作品时不能用默认画布、默认字体或空 assets 覆盖原值。
共享视觉规则只提供绘图语言；实际 palette/fonts/canvas 由作品动态进入任务。既有 task.md 不后台更新，软件更新也不批量使历史图片过期，需要新风格时显式准备新任务。

## native 还原

新作品按 [native 还原](native-reconstruction.md) 逐页制作。内容规划、生图与原图采用沿用上文流程。

```bash
deck run start native --pages p1,p2
deck run result <run> p1 <p1-plan.json>
deck run adopt <run> p1 --note '逐项对照后的实际结论'
deck run result <run> p2 <p2-plan.json>
deck run adopt <run> p2 --note '逐项对照后的实际结论'
deck build
deck export pptx
```

任务目录提供 content.json、atoms.json、style.json、attachments.json 与还原方法。坐标来自本页已采用原图，image op 的 file 相对 plan 所在目录。`run result` 先校验再渲染，返回 findings 与 side_by_side 路径；打开并排图，修正后再交回。native 只生成候选，必须用非空 `--note` 明确采用。`run show` 查看状态，`run cancel` 停止任务。

正文、目的、布局、样式或原图文件变化后，已采用的 SVG 或 native 列在 `stale_pages`。重新 adopt 会按当时的正文更新 native 依据，`stale_pages` 可以因此变空；原图没重生时该页仍在 `stale_images`，并出现在 build 与 export pptx 的 `warnings` 里。不并入、不阻断的规则见上文第 5 步。只改讲稿不使页面过期，但需要重新 build。native 作品缺页列在 missing_pages，不回退 SVG。build 只收已采用的 plan，讲稿取当前 page.notes；export 仍优先匹配当前构建输入。

validate-plan 与 crop 保留为文件辅助工具，用 deck-tools 所在 venv 的 Python 调用：

```bash
python -m deck_tools validate-plan <page-job.json>
python -m deck_tools crop <crop-job.json>
```

辅助 job 的 page 含 `id`、当前 `content`、`notes`、`source_image`（已采用原图路径）、`plan`（plan.json 路径），路径用完整路径。crop job 为 `{work, page, id, box:[x,y,w,h]}`，把本页原图指定区域裁到 `native/<页>/assets/<id>.png`，由 plan 引用。裁片在交回时随候选保存，不依赖源文件之后仍在原处。

plan v1 的固定外形：

```json
{"schema":"deck.native_plan.v1","page":"p1","canvas_px":{"w":800,"h":450},"background":"FFFFFF","ops":[]}
```

六类原语均以 `op` 区分。所有坐标、字号、线宽、圆角、列宽和行高用原图像素；输出幻灯片宽固定 13.333 in，高 = 13.333 × 原图高 / 宽，坐标按同一比例换算；整套模式下各页 `canvas_px` 必须一致，不一致直接报错。颜色为 RGB 十六进制，可带 `#`。

| op | 字段 |
| --- | --- |
| text | `text, atom_id, bbox:[x,y,w,h], size, color, weight`（`bold` 或数值），`align`（left/center/right），`valign`（top/center/bottom），可选 `repeat:true`；可用 `font` 指定已安装字体，默认 Noto Sans CJK SC |
| shape | `type`（pptxgenjs 形状名，或 custom），`bbox, fill, line:{color,width,arrowheads?}, transparency`（0–100），`radius, flip:{h,v}`；custom 加 `points:[[x,y],...]`（bbox 内局部点），可用 `closed:true` 闭合，`fill:"none"` 不填充 |
| arrow | `start:[x,y], end:[x,y], color, width, arrowheads:{start?,end?}`；箭头端用 pptxgenjs 名称，如 triangle |
| icon | `icon_id:"tabler-outline/<名称>", bbox, color` |
| image | `file, bbox`；不得附正文或 atom，每张面积不超过画布 40% |
| table | `bbox, col_widths:[...], row_heights:[...], margin, header_style:{size,color,fill,weight,align,valign,margin}, cells:[[{text,atom_id,margin?,repeat?},...],...]`；表头算第一行，可指定与 text 同形的文字样式及 `line:{color,width}`；margin 为非负数字或 `[上,右,下,左]` 四个非负数字，单位为原图像素，默认表头 `[5,8,5,8]`、正文 `[7,9,7,9]`；优先级为 cell.margin > header_style.margin（仅表头）> table.margin（全部单元格）> 默认值 |

文字和表格单元格必须逐项匹配当前 content 的 atoms；用现有 `atoms` 文件命令取得编号。讲稿只放 page.notes，不放 plan。表格的行列尺寸合计等于 bbox；空字符串正文也可作为对应 atom 的原生文本。

同一 atom 默认只出现一次。原图确实重复时，多出来的 text 或单元格加布尔值 `repeat: true`。列名可以不画，改写入顶层 `omitted: [{atom_id, reason}]`；`reason` 为非空字符串，且该 atom 必须是表格列名。其他 atom 不能这样省略。

`run result` 和 validate-plan 在硬性检查通过后，可能多返回 `warnings`。没有提示时不带这个字段。`repeated_atom` 表示去掉空白后不少于 8 个字的 atom 被画了多次，且多出来的次数没有 `repeat: true`。列名在每一组横排卡片上各作一次标题时不报。`orphan_column_label` 表示列名只作为一个 text 出现，该列文字分成至少两组横排，且列名字号小于这些文字的中位字号。`warnings` 不改变退出码。构建不重跑 validate-plan，回读也不重复这两项。

`deck run result` 保存候选和素材，并返回渲染 PNG 与并排图；每次重交后重新看图。`deck run adopt --note` 保存本次结论并采用；构建后检查整套输出。

图标索引与搜索可直接调用随包的工具；`<icons>` 是 deck_tools 包内的 `resources/icons/tabler-outline`：

```bash
python -m deck_tools.vendor.cyberppt.select_icon search --index <icons>/index.json --query "anchor" --limit 5
```
