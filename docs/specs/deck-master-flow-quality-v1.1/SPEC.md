# Deck Master｜Flow Quality 精简版 Spec v1.1

**版本：v1.1 · 2026-09-25（替代 v1.0，范围约缩 40%）**
**开发基线：`codex/flow-quality@c93f5a2`**
**状态：开发输入。不是已实现能力、测试通过声明，也不是安装／合并授权。**

配套文件：`TASKS.md`（9 项任务与依赖）、`ACCEPTANCE.md`（18 条验收）、`MIGRATION.md`（旧命令映射与本机旧安装迁移）、`methods/`（方法正文草案）、`examples/`（合成往返样例）。

---

## 0. 一句话目标

用户给出任务和材料后，系统要能完整接住并交给执行者。用户补材料、换用途或换会话后，项目能在原地继续，只改该改的页，并且只有与当前要求一致的稿件才能交付。Skill 只保留一个入口、一份方法源，只注册到 Codex。

## 1. 本版做什么、不做什么

### 1.1 做（9 项，详见 TASKS.md）

| # | 结果 |
|---|---|
| T1 | 工作单携带完整任务事实，方法按任务类型给出 |
| T2 | CLI 接通受众、场景、呈现方式、页数上限和既定决定，并支持 `--task-file` |
| T3 | 目录可以作为材料入口：递归读取、跳过工具目录，并报告被跳过和出错的文件 |
| T4 | 新增 `inputs show / inputs update`：原子保存、幂等、版本冲突检测，并记录 `content_basis` |
| T5 | `compose/input_revision` 只提交变化页（`content_update`），并修复 `task_inputs_current` 漏比对任务事实的问题 |
| T6 | 最终审阅按 `review_status` 的实际缺口派发，六维只在一处定义 |
| T7 | 方法单一源：合并 src 镜像的独有内容，从 canonical 构建，删除 D1/D2 与旧术语 |
| T8 | 直接删除旧 Skill，RESOLVER 只指向主入口 |
| T9 | 安装时把 Skill 注册到 `~/.codex/skills/deck-master`，回滚时一起恢复；一次性迁移本机旧布局；最后做真实端到端验收 |

### 1.2 明确推迟（v1.0 有，本版不做）

| v1.0 条目 | v1.1 处理 |
|---|---|
| `method_bindings` 方法快照、`method read` 命令 | 改为 Task 记录 `method_release {release_id, methods_sha256}`，只用于追溯 |
| `source scan`、`--source-manifest`、`--exclude` | 推迟。目录直接用 `--source`，混杂目录由 Host 自己挑文件后逐个传 `--source` |
| `source read` 命令 | 推迟。工作单给出原件和提取文件的真实路径，Host 直接读取 |
| `task request-input`、`input_request` | 推迟。缺少关键决定时 Host 在对话中询问，答复后用 `inputs update` 写入 |
| `superseded_requirement` | 不加，见 §5.4 |
| `task_origins`、`usage_role`、`role_origin` | 不加，来源只增加 `usage_note` |
| GUI「任务与材料」编辑区及 3 个 HTTP API | 不加。工作台只显示「待按新要求更新」 |
| `runtime.json`、安装事务记录、`doctor --step host` | 不加。只管理一条 Skill 链接，回滚时恢复 |
| `.agents/skills` 注册、Claude Code 注册、多 Host 选项 | 不做。只注册到 Codex 的 `~/.codex/skills` |
| 旧 Skill 迁入 `docs/legacy` 并改名 `REFERENCE.md` | 不做，直接删除（git 历史可查），另附一页旧→新命令映射 |
| 「新会话成功后才删除镜像」的前置条件 | 取消。镜像随 T7 在构建测试通过后删除 |

### 1.3 不变的边界

- 不改编译器、渲染器和 DrawingML 算法。
- 不新增永久对象，仍为 Document / Page / Artifact / Task / Review 五类。
- 不新增审批、评分、Planner 或多 Agent 接力。
- 保留 PR33 已建立的逐页蓝图→SVG→预览→审阅返修、逐 finding 关闭、迟到结果保护、真实读回和交付核对。

## 2. 权威分工

| 事实 | 唯一权威 |
|---|---|
| 当前任务与有效决定 | `Document.task` |
| 当前来源 | `Document.sources` |
| 当前正文与页序 | `Document.pages` |
| 正文按哪一版输入完成 | `Document.content_basis`（新增） |
| 某任务派发时的输入 | `Task.dispatch_revision` 与 `produced_against` |
| 可编辑方法 | `skills/deck-master/`（仓库内唯一） |

## 3. 任务输入与 CLI（T1、T2）

### 3.1 字段语义（沿用 service.create 已有参数）

`title, brief, audience, scenario, presentation_mode(live|read_alone|mixed), page_limit(int|null), existing_decisions(string[])`

- `page_limit` 表示最多多少页，不是目标页数。用户说「正好 N 页」时，写进 brief 或决定里。
- `existing_decisions` 只收用户明确确认的决定，并且始终是**完整有效集合**。Host 自己的推断不写进来。
- 未给 audience/scenario 就视为未指定，不触发问卷。
- 工作单要标出 `presentation_mode` 是显式给出还是默认值（`presentation_mode_source: provided|default`）。默认值不能说成用户确认。

### 3.2 CLI

`create` 新增 `--audience`、`--scenario`、`--presentation-mode`、`--page-limit`、可重复的 `--decision` 和 `--task-file`。其余参数保持不变。

合并规则如下：

- 显式传入的 CLI 标量覆盖 task-file 中的同名值；没传的参数不能用 argparse 默认值去覆盖文件里的值。
- `--brief` 与 `--brief-file` 互斥，brief 合并后必须非空。
- `--decision` 与 task-file 里的 `existing_decisions` 同时出现时直接拒绝（`task_field_conflict`，exit 2），不做拼接。
- task-file 是 JSON 对象，只能含 §3.1 的字段，出现未知字段即拒绝。

### 3.3 工作单的任务投影（T1）

`create`、`continue`、`task status` 返回的工作单新增 `project_context`：

```json
{
  "project_context": {
    "task": {"title": "…", "brief": "…", "audience": "…", "scenario": "…",
             "presentation_mode": "live", "presentation_mode_source": "provided",
             "page_limit": 8, "existing_decisions": ["…"]},
    "input_digest": "<§5.1 计算>",
    "dispatch_revision": "<派发时 revision>",
    "current_revision": "<当前 revision>",
    "context_status": "current | stale | terminal",
    "input_alignment": "no_content | current | needs_reconciliation | legacy_current"
  }
}
```

- 任务仍有效时，`task` 和 `sources` 取自 `dispatch_revision` 快照，不从当前 Document 临时拼入新输入。
- 输入已变而任务未结束时，返回 `context_status=stale`，并提示用 `continue` 取得新任务。

### 3.4 方法按任务类型派发（T1）

用一个静态映射替换 `service.py:310-313` 里写死的 3 个 URI：

| Task.kind / intent | 方法 |
|---|---|
| compose / initial | source-reading、content-methods（content-examples 按需） |
| compose / input_revision | source-reading、content-methods、input-update |
| blueprint、reconstruct | blueprint-svg |
| review（page_visual / final） | review-and-repair |
| repair | review-and-repair；内容类问题加 content-methods，视觉类加 blueprint-svg |

`method_resources` 每项给出 `{id, relative_path, path, sha256}`，其中 `path` 是当前安装包内的真实可读路径。Task 派发时记录 `method_release: {release_id, methods_sha256}`，用于回溯当时用的是哪版方法，不做快照。

同时修复 `service.py:697` 的最终审阅说明：改为按 §6 的实际缺口生成，不能继续写死 3 维。

## 4. 材料：目录入口（T3）

- `read_source` 仍只处理单文件。在 sources.py 新增 `discover_sources(paths)`，负责展开目录。
- 递归展开用户给定的目录，结果稳定排序。
  - 跳过这些目录：`.git`、`.venv`、`venv`、`node_modules`、`__pycache__`、`.deckmaster`。
  - 跳过 Office 锁文件 `~$*`、0 字节临时文件，以及当前项目的 `--out` 目录。
  - **不得**按「output」之类的目录名笼统跳过。
- 不跟随指向授权根之外的符号链接；这类链接列入 skipped 并注明原因。
- create 响应返回三份清单：`sources_adopted`、`sources_skipped`（附原因）、`sources_errored`（附 code：`source_unreadable` / `source_unsupported`）。
- 显式点名的单个文件读取失败时，整个 create 失败（exit 2），不留下半成品 Document。目录中不支持的文件只进 skipped，不阻断创建。
- 图片、扫描件的 `pending_visual` 状态保持现状：它表示 Host 需要看图，不算错误，也不等于已读。
- 新增来源一律用 `src-<uuid8>`，并由同一个 helper 保证不重复。旧项目的 `src-N` 保持不变。
- 来源行新增可选字段 `usage_note`，说明本任务怎么用这份材料。

## 5. 持续修改（T4、T5）

### 5.1 content_basis 与 input_alignment

Document 新增可选字段 `content_basis: {input_digest, input_revision_id, resolved_by_task_id}`。

`input_digest` 的计算方式：对 `Document.task` 全字段，加上按 source_id 排序的来源语义字段（`source_id, original_sha256, extract_sha256, usage_note, external_use, restriction`），做规范化 JSON 后取 SHA256。存储路径、显示名、时间、Task 列表、reviews、outputs 都不参与计算。

规范化方式：对 `{"task": Document.task, "sources": [...]}` 做 `json.dumps(sort_keys=True, ensure_ascii=False, separators=(',',':'))`，UTF-8 编码后取 SHA256。未设置的 `usage_note` 计为空字符串。`examples/input-context-*.json` 中的 digest 按此算法计算，可以作为实现的对照值。

`input_alignment` 是派生值，不存储：

| 值 | 条件 |
|---|---|
| `no_content` | 还没有页面 |
| `current` | 有页面，且 `content_basis.input_digest` 等于当前 `input_digest` |
| `needs_reconciliation` | 有页面，且两者不等 |
| `legacy_current` | 旧项目没有 `content_basis`；不要求重新验收 |

### 5.2 inputs 命令

- `deck-master inputs show --project P`：返回当前 task、sources、content_basis、input_alignment 和 revision。
- `deck-master inputs update --project P --patch FILE --base-revision R --operation-id O`

patch 格式：

```json
{
  "task_patch": {"audience": "…", "existing_decisions": ["…完整集合…"]},
  "source_changes": {
    "add": [{"path": "materials/new.md", "usage_note": "…"}],
    "replace": [{"source_id": "src-3", "path": "materials/interface-v2.md", "usage_note": "…"}],
    "remove": ["src-5"],
    "metadata": [{"source_id": "src-2", "usage_note": "…"}]
  },
  "reason": "用户原话概述：改变了什么"
}
```

规则：

- `task_patch` 是字段级补丁，没出现的字段保持原值。空字符串清空允许为空的字段，`[]` 清空决定，`null` 只能用于 `page_limit`。
- `replace` 和 `remove` 必须指向现存的 source_id，同一 ID 不能在一次请求里既 replace 又 remove。`remove` 不删除原文件。
- 同路径、同字节的 add 视为 no-op。`metadata` 只能改 `usage_note` 和显示名，不能改哈希或正文。
- path 相对 patch 文件所在目录解析。
- `base-revision` 和 `operation-id` 都必填：
  - 同一个 operation_id、同样规范化内容的重试，返回原结果。
  - 同一个 operation_id、不同内容，返回 exit 5 `input_revision_conflict`。
  - base 已过期，同样返回 exit 5 `input_revision_conflict`。

### 5.3 更新事务顺序（在现有项目锁内完成）

1. 规范化 patch，查询已提交的 operation。命中就返回原结果，不重读源文件。
2. 在暂存区读取所有新材料。任何一份失败都整体拒绝，不写当前状态。
3. 加锁后复核 base_revision，然后计算新的 `input_digest`。digest 没变时返回 `unchanged`；如果只改了显示名，保存新 revision，但不派任务。
4. 旧项目第一次更新时，把旧 digest 写入 `content_basis`。
5. 在同一个提交中完成以下三件事：
   - 保存新输入；
   - 把所有开放的内容、制作、审阅 Task 标为 `superseded`；
   - 派发 `compose, intent=input_revision`，其 `scope_pages` 为全稿，`dispatch_revision` 为新 revision。无页项目则派 `initial`。
6. 保留全部 Page、蓝图、SVG、PPT、Review。outputs 不清除，由 §5.5 控制是否可交付。
7. 返回 `input_alignment=needs_reconciliation`、被替代的任务、差异摘要、新工作单和工作台 URL。

### 5.4 content_update 接收（T5）

`initial` 保持完整 pages 数组的现行语义。`input_revision` 只接受 `content_update`，不接受顶层 pages 或 page_order，以免走到 tasks.py:859-874 清空全部槽位的分支：

```json
"content_update": {
  "input_digest": "<必须等于派发时 digest>",
  "upsert_pages": [ /* 只放变化或新增的完整 Page v2 */ ],
  "remove_page_ids": [],
  "page_order": ["p01","p02","p03"],
  "impact_summary": "…",
  "unchanged_reason": "…（upsert/remove 都为空时必填，且要具体）"
}
```

接收规则：

- `page_order` 必须等于「旧页 − 删除页 + 新增页」，不重复、不遗漏、没有幽灵页。
- 某页的规范化字节没变，就视为未改，槽位全部保留。
- 改了的页：保留原蓝图作为历史参考，清掉 SVG 和预览，由现有 reconstruct 流程重建。新页从蓝图开始。删掉的页退出当前集合，对象保留在历史里。
- 所有 Page 校验通过后，一次性切换 Document，并设 `content_basis = 本次 digest`。无影响的采用不会自动产生 pass。
- input_revision 结果里不能同时带 Artifact 或 Review。

`task_inputs_current`（tasks.py:293）修复：在 scoped fallback 中加上 `dispatched['task'] != document['task']` 时返回 False。已结束的任务只能重放原操作；superseded 状态的迟到结果一律拒绝（exit 5）。

**旧 finding 的处理（不新增 resolution）：**

- 删掉的页，其 finding 随页面退出当前范围，历史保留。
- 某个要求被新输入撤销时，Host 按新输入改页，由新一轮 content 审阅对当前页用现有 `fixed` 关闭，并在说明中引用 input revision。
- 页面没改但要求已撤销的少数情况，finding 继续保持开放并报告给用户，本版不做自动豁免。这是已知限制。

### 5.5 更新期间的出口

`check_summary`、`continue`、`view`、`export`、`handoff-check` 统一读取 `input_alignment`：

- `needs_reconciliation` 状态下：
  - `export --purpose review|working` 允许，产物标注「待按新要求更新」；
  - `export --purpose delivery` 和 `handoff-check` 拒绝，code 为 `input_reconciliation_pending`，exit 3。
- 工作台顶部显示只读提示「待按新要求更新」和差异摘要，没有编辑控件。
- 新输入之后，content 和 privacy 必须按新依据复查。物理文件没变的页面，其 conversion 和 readability 观察继续有效。

## 6. 最终审阅按实际缺口派发（T6）

- 在 review.py 中定义唯一的 `REVIEW_DIMENSIONS = (content, blueprint_content, blueprint_fidelity, conversion, readability, privacy)`。`REQUIRED_KINDS`、`PAGE_VISUAL_KINDS`（其子集）、最终审阅说明和校验全部从这里取值，不在别处手写。
- 最终 review Task 从 `editing.review_status()` 计算 `review_plan.units: [{kind, page_ids, reason: missing|stale|open_finding|changed_input}]`，并存入 `Task.review_units`。
- 说明文字由 units 生成。已经有效的维度不再要求；Host 额外发现问题照常提交。
- content 和 privacy 可以一次覆盖多页，接收后分别计入各页。
- 逐页审阅的有效观察作为 prior evidence 带进最终工作单，但不能直接复制成最终 pass。

## 7. Skill 与方法单一源（T7、T8）

### 7.1 单一源（T7）

1. 把 `src/deck_master/resources/skill/references/content-methods.md:68`（同页区分「原始要求」和「方案建议」）合入 canonical，然后比对其余文件，没有其他独有内容。
2. 停止跟踪 `src/deck_master/resources/skill/`，把它加入 .gitignore（作为构建产物）。
3. 新增 `method_resources.resolve_root()`：
   - 安装包内存在 `deck_master/resources/skill` 时用它；
   - 否则，当模块位于本仓库 src 下（根目录 pyproject 的 name 匹配）时用 `skills/deck-master`；
   - 不从 CWD 或上级目录借用方法文件。
   - `doctor.py:21` 和工作单的 `method_resources` 都改走这个函数。
4. 删除 `resources/skills-references`：
   - build_hook.py:23 不再生成它；
   - pyproject.toml:54 删除对应条目；
   - 改写 tests/rebuild/test_install.py 中引用它的断言。
5. `tools/build_release.py:14` 保留检查构建产物 `resources/skill/SKILL.md`。build_hook 仍从 canonical 复制，保证 wheel、sdist→wheel 的内容一致。
6. 删除 `skills/deck-master/prompts/`（4 个文件）和 `schemas/`（7 个文件）。当前 src/tools/tests 中没有消费者，build_hook 也不复制它们；实施时用 rg 再确认一次。
7. 方法正文：
   - content-methods 去掉旧术语 deck_brief、narrative_plan、claim_map（第 15-19 行附近）和 D1/D2 段（第 224 行附近）；
   - content-examples 去掉 D1/D2 结构，改成自包含的合成样例；
   - 新增 references/input-update.md；
   - SKILL.md 按 `methods/` 草案合并。

### 7.2 删除旧 Skill（T8）

- 直接 `git rm` 以下内容：
  - 14 个 `skills/deck-*`：autopilot、brief、builder、builder-high-density、doctor、init、learn、planner、producer、quality、review、setup、sourcing、upgrade；
  - 4 个 `skills/ppt-*`：deck-pro-max、library、master、quality-gate；
  - `skills/manifest.json` 和 `skills/stage-contracts.json`。
- 重写 `skills/RESOLVER.md`，只保留一行：所有 Deck Master 相关请求 → `skills/deck-master/SKILL.md`。
- AGENTS.md、CLI 帮助、活动文档中指向旧 Skill 的路由改指主入口。历史 spec 和事故记录不改。
- cli.py 中识别旧 run 的 legacy marker 检测保留，因为它负责给出正确的迁移提示。

## 8. Codex 注册、回滚与本机旧布局迁移（T9）

### 8.1 注册

- 发布包候选目录 `releases/<id>/` 新增 `skill/deck-master/`，从 wheel 的 `resources/skill` 提取。这里没有新的可编辑源。
- `install activate` 默认建立一条受管理的链接：`~/.codex/skills/deck-master` → `PREFIX/.deck-master/current/skill/deck-master`。
  - Codex skill 根目录取 `$CODEX_HOME/skills`，未设置时为 `~/.codex/skills`。
  - 链接指向 `current`，所以 current 切换时 Skill 自动跟随。
- 判断归属：链接目标**恰好等于**上述路径，就是受管理链接。
  - 不存在或属于受管理链接：创建或校正。
  - 是真实目录、真实文件，或指向其他目标：切换 current **之前**拒绝（`host_skill_conflict`，exit 5），并报告路径。不覆盖。
- `--no-host-registration` 用于 CI 或非交互场景。此时结果要分开报告 `cli_active` 和 `host_unregistered`。
- 不改 `~/.codex/config.toml`，不碰 `~/.codex/skills/.system` 和其他第三方 Skill，不注册 Claude Code 或 `.agents/skills`。

### 8.2 回滚

`rollback` 切到 previous 后检查 `current/skill/deck-master/SKILL.md` 是否存在：

- 存在：链接自动有效，报告 skill 版本和 CLI 版本一致。
- 不存在（previous 是旧格式）：删除受管理链接，报告 `host_skill_unregistered`。不能留下一条断链，也不能让新方法搭配旧 CLI。

### 8.3 一次性迁移本机旧 companion 布局

本机实测现状（2026-09-25）：

- `~/.deck-master/current` 是**真实目录**，里面只有 `companion-manifest.json`（schema v3，release main-cc8cf46，adoption_policy `bundled_symlink_only`）。
- 没有 `releases/`、`previous` 和 `bin`。
- `~/.codex/skills/` 下有 15 个 `deck-*` 符号链接，都指向 `~/.deck-master/current/skills/<name>`，其中包括 `deck-master` 本身。这些链接**全部是断链**。

现有 `_activate_locked` 看到非符号链接的 current 会拒绝（refuse to replace user-owned path），所以必须先迁移。迁移规则如下：

1. 仅当 `PREFIX/.deck-master/current` 同时满足以下两点时，才识别为旧 companion 布局：
   - 是真实目录；
   - 只包含 `companion-manifest.json`，且其 `schema_version` 和 `adoption_policy` 与上述一致。

   目录里还有其他内容时，视为用户所有，拒绝处理并报告。
2. 把它移到 `PREFIX/.deck-master/legacy-companion-<时间戳>/`，只移动，不删除。
3. 在 Codex skill 根目录下，**只删除**同时满足以下三点的条目：
   - 是符号链接；
   - 名字匹配 `deck-*`；
   - `readlink` 以 `PREFIX/.deck-master/current/skills/` 开头。

   其他条目一律不碰，只报告。
4. 然后走正常的 activate 和 §8.1 注册。
5. 迁移结果逐条列出「移动了什么、删除了哪些链接、跳过了哪些条目」。重复执行必须幂等。
6. 迁移只在 `install activate` 中自动触发，并在结果中单列。测试用隔离 HOME 构造同样的布局。

## 9. 错误码（保留退出码 0/2/3/4/5）

| code | exit | 场景 |
|---|---|---|
| `task_field_conflict` | 2 | `--decision` 与 task-file 决定并存，或 brief 冲突，或出现未知字段 |
| `source_unreadable` / `source_unsupported` | 2 | 显式文件读取失败或格式不支持（目录内的只进 skipped） |
| `input_revision_conflict` | 5 | base 过期，或 operation_id 复用但内容不同 |
| `stale_input_context` | 5 | 旧任务结果晚于输入更新提交 |
| `input_reconciliation_pending` | 3 | 待更新状态下请求 delivery 或 handoff |
| `method_resource_missing` | 4 | `resolve_root` 找不到方法文件 |
| `host_skill_conflict` | 5 | Codex 下同名条目不属于本安装器 |
| `host_skill_unregistered` | 0（结果标注） | 用了 `--no-host-registration`，或回滚到没有 Skill 的旧版本 |

每项都要带 path/field、当前状态和下一步动作。

## 10. 兼容

- c93 项目可以直接读取。新字段均为可选，旧对象按原语义加载。旧项目算 `legacy_current`，不要求重新审阅。
- 旧二进制遇到 `content_update` 时要明确失败，不能静默忽略。
- 安装回滚不回滚已发生的调用和费用事实。

## 11. 完成定义

以下全部满足才算完成：

- TASKS.md 中 9 项的验证点全部通过；
- ACCEPTANCE.md 中 18 条验收有真实证据；
- 在仓库外新开 Codex 会话，自然语言走通 7 步场景（AC-17）。

只改了字段、JSON 能通过或拼出一份范例，都不算完成。缺少真实 Host 条件时，可以交付工程候选，但要写明哪些没有验证。
