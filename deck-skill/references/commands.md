# 内容主链命令

在仓库 worktree 中先准备本地工具；不要共用另一个 checkout 的 Python 环境：

```bash
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install -e './deck-tools[dev]'
cargo install --path rust --root ~/.local
export DECK_TOOLS_PYTHON="$PWD/.venv/bin/python"
ln -s "$PWD/deck-skill" ~/.codex/skills/deck
```

软链接目标已存在时，先查看它，不覆盖其他 Skill。下文的 `deck` 指 `~/.local/bin/deck`；若它不在 PATH，直接用完整命令路径。`DECK_PROJECT` 是作者指定的新作品目录，`SOURCE_FILE` 是作者指定的一份原材料；不要根据示例搜索 HOME 或补读相邻目录。

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
