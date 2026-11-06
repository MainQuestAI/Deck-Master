# 内容主链命令

## 开发期环境准备

以下是开发期安装命令，已有可用环境时从“新建与读材料”开始。

在仓库 worktree 中先准备本地工具；不要共用另一个 checkout 的 Python 环境：

```bash
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install -e './deck-tools[dev]'
cargo install --path rust --root ~/.local
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
ln -s "$PWD/deck-skill" ~/.codex/skills/deck
```

`scripts/install.sh` 在迁移期默认只链接兼容入口 `deck`。`--skill-dir PATH` 同样只链接这一个入口。`--skills-root DIR` 才会在该目录下同时链接 `deck`、`deck-master`、`deck-content`、`deck-design` 和 `deck-review`，两个参数不能一起用。

软链接已指向本源时，重复安装不改链接。指向其他位置、或同名路径是普通目录时，脚本退出 2，并打印该路径和目标。只移走这一项，不要删除它指向的目录，然后重新运行；或者换一个安装路径。不要静默覆盖。

下文的 `deck` 指 `~/.local/bin/deck`。安装用了非默认 `--prefix` 时，二进制在 `<prefix>/bin/deck`。`<prefix>/bin` 不在 PATH 时，每条命令都用这个完整路径。`DECK_PROJECT` 是作者指定的新作品目录，`SOURCE_FILE` 是作者指定的一份原材料；不要根据示例搜索 HOME 或补读相邻目录。

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
BASE=$("$DECK_TOOLS_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$DECK_PROJECT/current.json")
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
BASE=$("$DECK_TOOLS_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$DECK_PROJECT/current.json")
deck --project "$DECK_PROJECT" put --base "$BASE" "$DECK_PROJECT/pages.json"
deck --project "$DECK_PROJECT" show
deck --project "$DECK_PROJECT" export md > "$DECK_PROJECT/manuscript.md"
```

页 id 用于选页，沿用已有值；新增页使用未占用值。块、条目、表格列、行与单元格不用手写 id，保存会补齐。表格单元格不填 column_id 时按列顺序对应；从已有页改表格则沿用其列引用。

## 局部修改

`deck --project "$DECK_PROJECT" get --pages p2` 只返回所选页，但保留任务与框架，并省略 order。读取后修改目标页的作者字段，再用此次返回的 version 保存；不需要读写其他页。

- 只改文字时，提交该页完整 `content`；只改讲稿时，只交该页 id 与 notes。
- 新增页：交新页面及包含它的完整 order；删除页：交 `{id}` 和去掉该页的完整 order；重排只交 order。
- `put` 也接受 get 的完整输出。不改 materials、image、svg 或 preview；保存不会用它们更新材料或产物。
- 同一提交可以安全重试，没有实质变化就不新增版本。冲突时命令退出 5 并给当前冲突单元，先读取后合并作者意图，再保存。
- `deck --project "$DECK_PROJECT" restore N` 把历史稿恢复为新版本，不删除后来的历史。

`export md` 向 stdout 输出正文、讲稿、待补与出处，不要求稿件完整。重定向前选一个新文件名；交稿前实际阅读该文件。当前内容阶段无需渲染器、生图、编译或界面。

## 原图、SVG 与构建

内容完成不自动进入这一节。设计或兼容入口在授权范围内使用。

1. `deck run start image --pages p1,p2` 准备任务。读取该次工作目录里的完整 task.md，按 attachments.json 定位素材。每次调用前 `deck run call <run> <page>`，再把 task.md 原文作为 ImageGen 的 prompt，把清单中的文件作为附件。结果未知时先核实，决定重试才加 `--retry`。
2. `deck run result <run> <page> <图片文件>` 交回。首次结果可以自动采用；重交的修正版、取消后或依据已变的结果只保存。确认使用后 `deck run adopt <run> <page>`。`deck run show` 看状态，`deck run cancel <run>` 停止后续调用和自动采用。
3. `deck run start svg --pages p1,p2` 准备 SVG。按原图的布局和关系重建，正文取 content.json，文字绑定 atoms.json。先读 [svg-subset.md](svg-subset.md)。错漏文字、局部排版和依据明确的连线可以沿用原图直接改。主结构要重排时先改蓝图。
4. `deck run result <run> <page> <SVG文件>` 编译、渲染并回读。工具报错就改具体元素。Host 打开预览 PNG，对照原图检查端点、方向、分支、层级、侧栏和阅读顺序。
5. `deck build` 构建 PPTX，`deck export pptx` 取最近构建路径。`missing_pages` 是没有 SVG、因此没有进入这次 PPTX 的页。`stale_pages` 是 SVG 依据与当前正文、原图或样式不一致。`stale_images` 在 `deck show` 的 `artifact_status` 里，指原图依据已变；只改讲稿不会让原图过期。构建成功不会清掉这两项。`export pptx` 的 `input_changed` 才表示构建之后 SVG、讲稿或构建设置又变了。

`soffice` 不可用时，SVG 的 `deck run result` 失败并说明如何安装 LibreOffice。停在这一步。不要改调 `compile_job`，不要手写 PPTX。

## 意见

`deck review list --status open` 读取未处理意见，可用 `--page` 限定。作者明确要求保存时：

```bash
deck review add --method self_check --page p3 '这一页的问题'
```

当前 Host 自查用 `self_check`，另一执行或模型用 `other_model`，真人用 `human`。不要省略 `--method`，默认值是 `human`。落实并核对之后才 `deck review resolve <意见ID>`。审查默认只返回报告，不因为开了审查入口就改稿或生图。

## 可选：核对案例算式

用装有 deck-tools 的解释器：

```bash
python -m deck_tools.case_numbers path/to/numbers.json
```

只读该文件。退出码 0 表示显式算式与期望一致，1 表示不一致，2 表示输入无效。不写回文件，也不判断来源、归因或 ROI。写稿、导出和审查都不依赖这次运行。
