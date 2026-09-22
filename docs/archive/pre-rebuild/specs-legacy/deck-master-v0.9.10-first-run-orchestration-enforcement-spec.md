# Deck Master v0.9.10 First-Run Setup + Orchestration Enforcement Spec

## 1. 目标

v0.9.10 修复两个产品级缺口：

- 首次真实使用 Deck Master 时必须先完成 Setup，登记本机安装根目录、active workspace、默认 runs dir、Review Cockpit URL 和 Agent skill 状态。
- 用户点名 Deck Master 后，Deck Master 必须持续作为顶部编排器。规划校准、外部 PPT 生产、质量检查和最终交付路径都要回写到 Deck Master run。

本轮优先做约束、门禁和回写，不重写自动规划算法。

## 2. 配置状态源

真实安装状态写入：

```text
~/.deck-master/config.json
```

字段：

- `schema_version`
- `setup_completed_at`
- `install_root`
- `active_workspace`
- `default_runs_dir`
- `review_cockpit_url`
- `agent_targets`

Setup 和状态检查事件写入：

```text
~/.deck-master/setup_events.jsonl
```

## 3. CLI

新增命令：

```bash
deck-master setup --workspace <path> --runs-dir <path> --target codex --target claude-code
deck-master setup-status [--workspace <path>]
deck-master orchestration-check --run-dir <path>
deck-master import-plan --run-dir <path> --input <plan.md|plan.json> --source human
deck-master import-render-result --run-dir <path> --input <render-result.json>
```

`setup --repair-workspace` 会补齐 workspace 标准目录和占位质量文件。该动作只创建缺失项，不覆盖已有文件。

## 4. 真实 Run 门禁

以下会产生或改变 run 产物的命令必须先通过 `setup-status`：

- `plan`
- `start-conversation`
- `autoplan`
- `build-brief`
- `build-claim-map`
- `search-library`
- `decide-sourcing`
- `create-generation-tasks`
- `build-preview`
- `quality-gate`
- `export`
- `import-context-pack`
- `create-run-from-context-pack`
- `import-plan`
- `import-render-result`
- `prepare-generation-handoff`
- `import-generation-result`
- `refresh-preview-from-generation`
- `prepare-quality-review`
- `import-quality-review`
- `delivery`
- UAT、benchmark、metrics 等会写 run 状态的命令

未完成 Setup 时命令返回错误，并给出下一条可执行命令：

```text
deck-master setup --workspace <path> --target codex
```

开发和测试允许显式绕过：

```bash
--dev-allow-unsetup
DECK_MASTER_DEV_SKIP_SETUP=1
```

## 5. Workspace 与 Review Cockpit 绑定

`setup --workspace <path>` 会登记 active workspace。未显式传 `--runs-dir` 时，默认 runs dir 使用：

```text
<active-workspace>/runs
```

如果 workspace 校验结果为 `pending_manual_review`，真实 run 默认阻断。用户可以执行：

```bash
deck-master setup --workspace <path> --repair-workspace --target codex
```

修复完成后，Review Cockpit 应读取 active workspace 下的 runs。

## 6. 编排一致性检查

`orchestration-check` 检查 run 是否具备：

- `request.json`
- `context_manifest.json`
- `deck_brief.json`
- `claim_map.json`
- `narrative_plan.json`
- `page_tasks.json`
- `sourcing_plan.json`
- `preview_manifest.json`
- `quality_reports/*_gate.json`

输出必须包含：

- 当前状态
- 缺失产物
- 下一条 Deck Master 命令
- 是否允许进入外部 PPT 生产

如果缺少 `preview_manifest.json`，不能进入外部 PPT 生产。

## 7. 人工规划回写

当自动规划跑偏，允许人工或 Agent 校准规划，但校准结果必须导回 run：

```bash
deck-master import-plan --run-dir <path> --input <plan.md|plan.json> --source human
```

导入动作必须：

- 备份旧 `narrative_plan.json` 和 `page_tasks.json` 到 `overrides/plan_<timestamp>/`
- 写入新 `narrative_plan.json`
- 写入新 `page_tasks.json`
- 追加事件 `plan.override.imported`

README、汇报文档和后续外部工具任务只能引用导回 Deck Master 后的规划。

## 8. 外部工具 Handback

PPT Master / PPT Deck Pro Max 完成 SVG、PPTX、PDF 或预览图后，必须通过 Deck Master 登记：

```bash
deck-master import-render-result --run-dir <path> --input <render-result.json>
```

导入动作必须：

- 校验 `deck_render_result.v1`
- 写入 `external_results/render_result.json`
- 更新 `preview_manifest.json` 的最终产物、渲染状态和页面预览路径
- 追加事件 `external_result.imported`

导入后再执行：

```bash
deck-master quality-gate render --run-dir <path> --artifact <path>
deck-master quality-gate delivery --run-dir <path> --artifact <path>
```

最终汇报只能引用 Deck Master 已登记的最终产物路径。

## 9. Skill 约束

`skills/deck-master/SKILL.md` 的 First Checks 必须先运行：

```bash
~/.deck-master/bin/deck-master setup-status
```

`references/agent-instructions.md` 必须明确：用户点名 Deck Master 时，它是顶部编排器；不能把核心规划、外部生产、质量检查和交付状态只留在外部目录。

## 10. 事件

新增事件：

- `setup.completed`
- `setup.status.checked`
- `plan.override.imported`
- `orchestration.checked`
- `external_result.imported`

## 11. 验收标准

单元测试：

- 未 Setup 时，真实 run 命令被阻断。
- `setup-status` 能识别 skill、runs dir、workspace 和 Review Cockpit 配置。
- workspace 缺失标准目录时返回 `needs_repair` 或 `blocked`。
- `setup --repair-workspace` 创建缺失目录和占位文件。
- `import-plan` 能备份旧 plan、写入新 plan、追加事件。
- `orchestration-check` 能识别缺失 `context_manifest`、缺失 `preview_manifest`、缺失 quality gate。
- `import-render-result` 能更新 `preview_manifest.json` 并追加事件。

回归测试：

- `start-conversation -> autoplan -> quality-gate` 仍可通过开发绕过开关跑测试。
- 已安装 skill 校验仍通过。
- Review Cockpit 可读取 active workspace 的 run。
- `python3 -m unittest discover -s tests` 通过。

真实场景 smoke：

- 对医药客户样本工作坊执行 `setup-status`。
- 导入人工校准版规划。
- 执行 `orchestration-check`，下一步指向 context / preview / quality 补齐。
- Review Cockpit 能看到该 run，状态不再只停留在 `planned`。
