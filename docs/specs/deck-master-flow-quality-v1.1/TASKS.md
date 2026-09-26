# TASKS v1.1：9 项任务、依赖与验证点

基线是 `codex/flow-quality@c93f5a2`。每项任务独立提交；合并前运行 `python3 -m pytest -q tests`，必须全绿。

```
T1 ──┬─> T4 ─> T5 ─> T6
T2 ──┘         │
T3 ────────────┘
T7 ─> T8 ─> T9（最后，含 AC-17 真实会话）
```

T1/T2/T3/T7 之间没有依赖，可以并行。T9 依赖其他全部任务。

| # | 任务 | 主要改动位置 | 验证点（先写测试） | 对应 AC |
|---|---|---|---|---|
| T1 | 工作单补齐任务事实，方法按任务类型派发 | `service.task_summary`（:294）新增 `project_context`；用 kind/intent 映射替换 :310-313 写死的 URI；Task 记录 `method_release`；:697 的最终说明改为按缺口生成 | ① create 返回的工作单含完整 task，`presentation_mode_source` 正确；② compose/initial 与 review 的 method_resources 不同，path 可读，sha256 与文件一致；③ 输入变化后，旧任务的 context_status=stale | AC-01、AC-02、AC-03 |
| T2 | CLI 任务字段与 `--task-file` | `cli.py` create 子命令（:79 附近） | ① 各参数都落到 Document.task；② CLI 显式值覆盖 task-file，未传的参数不覆盖；③ `--decision` 与文件里的 decisions 同时出现 → exit 2 `task_field_conflict`；④ 未知字段 → exit 2 | AC-04、AC-05 |
| T3 | 目录作为材料入口 | `sources.discover_sources`；create 返回 adopted/skipped/errored 三份清单；ID 改为 `src-<uuid8>` | ① 目录中含 `.git`、`node_modules`、`~$x.docx`、0 字节文件、`--out` 自身、指向根外的符号链接 → 全部进 skipped 并注明原因；② 名为 `output/` 的普通子目录不被跳过；③ 显式点名的坏文件 → exit 2，且没有产生 Document；④ 旧项目的 `src-N` 不变 | AC-06、AC-07 |
| T4 | `inputs show/update` 与 content_basis | 新增 `service.inputs_update`，复用项目锁和 operation 记录；Document 增加 `content_basis`；实现 input_digest | ① `examples/input-context-*.json` 的 digest 可复算；② 同 op 重试结果相同，同 op 不同内容 → exit 5；③ base 过期 → exit 5；④ 新材料读取失败时当前状态不变；⑤ 只改显示名 → 不派任务；⑥ 更新后，开放任务变为 superseded，并派出 input_revision；⑦ 页面、产物、outputs 全部保留 | AC-08、AC-09、AC-10 |
| T5 | `content_update` 接收，并修复 task_inputs_current | `tasks.py` 接收分支（:859-874 旁新增 input_revision 分支）；`task_inputs_current`（:293）增加 task 比对；delivery/handoff 读 input_alignment | ① 只 upsert p03 → p01/p02 的槽位和字节不变，p03 清除 SVG/预览、保留历史蓝图；② page_order 出现幽灵页、重复或遗漏 → 拒绝；③ upsert 与 remove 均为空且没有 unchanged_reason → 拒绝；④ **只改 task 字段后，旧 scoped 结果被拒绝**（当前 c93 会误收，先写复现测试）；⑤ needs_reconciliation 时 delivery/handoff → exit 3，review 导出带标注；⑥ c93 旧项目仍可加载，显示为 legacy_current | AC-11、AC-12、AC-13 |
| T6 | 最终审阅按缺口派发 | `review.py` 定义唯一的 `REVIEW_DIMENSIONS`；最终 review Task 生成 `review_units` | ① 在代码中 rg 六维名称，只有一处定义；② 已有有效 conversion/readability 的项目，最终工作单只要求缺失的维度；③ 输入更新后，content/privacy 重新列入 units；④ 逐页审阅的 pass 不能直接当作最终 pass | AC-14 |
| T7 | 方法单一源 | 合并 src 镜像 `content-methods.md:68`；取消跟踪 `src/deck_master/resources/skill/`；新增 `resolve_root()`；删除 skills-references（build_hook:23、pyproject:54、test_install）；删除 deck-master 下的 prompts/ 和 schemas/；按 `methods/` 草案改正文 | ① wheel 与 sdist→wheel 里的 `resources/skill` 字节等于 canonical；② wheel 中没有 `skills-references`；③ 在 CWD 放一份假 SKILL.md，`resolve_root` 也不采用；④ rg 查 `deck_brief|narrative_plan|claim_map|D1|D2` 在 canonical 中无结果；⑤ doctor 的 compose 步骤通过 | AC-15 |
| T8 | 删除旧 Skill | `git rm` 14 个 deck-* 和 4 个 ppt-*，以及 manifest.json、stage-contracts.json；RESOLVER 改为一行；AGENTS.md、帮助文案改为指向主入口 | ① `ls skills/` 只剩 deck-master 和 RESOLVER.md；② 在 src/tools/tests/pyproject/AGENTS.md 中 rg 旧 Skill 名无结果（历史文档除外）；③ legacy run 检测测试仍通过 | AC-16 |
| T9 | Codex 注册、回滚、旧布局迁移、端到端 | install activate/rollback（SPEC §8）；发布包候选加入 `skill/deck-master/` | 在隔离 HOME 下验证：① 全新安装后，链接 `~/.codex/skills/deck-master` → `current/skill/deck-master`，且 SKILL.md 可读；② 目标路径已被真实目录或其他链接占用 → exit 5，current 不切换；③ 按本机现状构造旧 companion 布局和 19 条断链（15 条 deck-*、4 条 ppt-*）→ 迁移后只删这 19 条，第三方 Skill 原样保留，再跑一次结果不变；④ current 目录里有其他文件 → 拒绝；⑤ 回滚到没有 skill 的旧版本 → 链接被移除，结果含 `host_skill_unregistered`；⑥ 在仓库外新开 Codex 会话走通 7 步场景 | AC-17、AC-18 |

## 交付顺序建议

1. 先写 T5④ 的复现测试：只改 task 后，旧结果当前会被接收。这是 c93 真实存在的缺陷。
2. 第一批：T1、T2、T3、T7 并行。
3. 第二批：T4 → T5 → T6。
4. 第三批：T8，然后 T9。T9 的第⑥点必须由老板在本机实际安装并运行，AI 不能代替。

## 每项提交前的自检

- 没有残留 console.log、print 调试语句、TODO 或 FIXME；
- 没有混入与本任务无关的改动；
- 新字段都是可选的，c93 的项目夹具可以加载；
- 提交说明写明做了什么、没做什么、如何验证。
