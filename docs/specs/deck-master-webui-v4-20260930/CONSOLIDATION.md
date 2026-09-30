# webui-v4 冲刺计划与治理合并（唯一入口）

日期：2026-09-30。经用户决定：**A/B 双线合并为单一冲刺**，一次 goal 执行完成剩余全部开发、集成与测试，形成一组 PR 后向用户发起最终评审。本文件是冲刺的唯一入口；HANDOFF-A/HANDOFF-B 与 EXECUTION 的双线批次表自此成为历史参考（各卡任务卡仍为工作分解与评审单元）。

## 0. 冲刺基线（开工前核对）

- **基线 SHA**：`origin/main` = `21b3d6d09b0b96c136186d10acfdb962f3c6d880`（A01/B01/B02/A02/A03/B03 六卡全部合入；PR #67-#71）。
- **冲刺支线**：`codex/webui-v4-completion`（自基线新建）；唯一活动工作树 `/Users/dingcheng/.codex/worktrees/webui-a/Deck-Master`；`webui-b` 工作树休眠（保留不删）。
- **测试基线**：`PYTHONPATH=src <主仓库>/.venv/bin/python -m pytest tests/rebuild -q` = **954 passed**（约 2m50s）；`ruff check src/ tests/rebuild/` clean。
- **环境要点**：工作树无 venv，借用 `/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/.venv`；浏览器验证用 playwright-cli（`~/.zcode/skills/playwright/scripts/playwright_cli.sh`，`run-code` 只接受 `async page => {}` 形式）；矩阵类 UI 改动必须断言表头/表体几何对齐（A03 教训）。

## 1. 已完成进度（6/15 卡，18/45 新 AC）

| 卡 | 交付 | PR | 评审结论 |
|---|---|---|---|
| A01 | 设计系统/状态组件/PR66 有限移植 | #67 | 无 P1，3 P2 修复 |
| B01 | next_actions/attention/prompt_summary 读契约 | #68 | 无 P1，2 P2 修复 |
| B02 | effective_actions + view --ui v2 入口 | #68 | 无 P1，2 P2 修复（G54 回填） |
| A02 | launcher 搜索/项目卡 + 连接面板 | #69 | 无 P1，P2 历史导出修复 |
| A03 | 总览待办 + 8 列矩阵（G02 关闭） | #70 | 初审 3 P1 全修复复验 |
| B03 | 正文/结构变更集候选 + 原子采用 | #71 | 两轮评审通过（P0 毒化已修） |

证据链：`evidence/{a01,a02,a03}-browser-verification.json`、`{b01,b02,b03}-slice.json`（各含 review 节）。

## 2. 剩余范围（9 卡 + 回填项）

依赖图（✓=已在 main）：

```
A02✓ ─→ A04 ─→ A05 ─┬─→ A08 ─→ B07
B03✓ ─┬→ B04 ─┬─→ A07 ─┘
      ├→ A05（B03 切片）        A07 也依赖 B05
      └→ B06 ─→ A06 ─→ A08
B02✓ ─→ B05 ─→ A07
```

**冲刺执行顺序**（串行，逐卡评审，按 PR 分组）：

| 序 | 卡 | 交付摘要 | 前置 | 归属 PR |
|---|---|---|---|---|
| 1 | A04 | 整稿阅读（网格/连续/并排/列数）与单页六层制作链 | A02✓ | PR-M1 |
| 2 | B04 | 候选 keep_current/reopen 持久决定 | B03✓ | PR-M1 |
| 3 | B05 | 个人工作区状态安全清理（plan/commit-clear） | B02✓ | PR-M1 |
| 4 | A05 | 内容/材料/标注动作 + 批量生成请求（G14-G16、G21-G25） | A04+B03✓ | PR-M2 |
| 5 | B06 | 风格保持约束 + 真实制作闭环切片（正向跨页/30页真实项目保持待材料） | B03✓ | PR-M2 |
| 6 | A06 | 风格校准 UI + 候选决策 UI（Page/Artifact 分型、正文 diff、keep/reopen 消费 B04） | A04+B03✓+B04+B06 | PR-M3 |
| 7 | A07 | 任务/交付/恢复（草稿恢复、历史恢复、导出 UI、G36-G42、G45） | A02✓+B04+B05 | PR-M3 |
| 8 | A08 | 界面集成与设计验收（六状态生产对应、设计差异单） | A03✓+A05+A06+A07 | PR-M4 |
| 9 | B07 | 安装/压力/导出/回退与切换准备（G43-G47、G49、G54 收口） | 全部 | PR-M5（最终） |

**回填项搭车**（不单开卡）：G54 端点格式门→B07；registry listing 的 page_count/sample→B07；runs 面无编辑器时持久化 no-op→A07；历史 drafts 跨面一致性→A05/A06。

**按设计保持 open（不冒充完成）**：真实 Host 生成/风格正向证据（材料具备时 B06/B07 实证）、实际 HOME 迁移与 AC-17（用户执行）、默认入口切换与发布（用户授权）、30 秒真实使用者观察（需真人；A08 记录待验）、W12 压力失败根因复验（B07 同门槛重测）。

## 3. PR 组结构（向用户发起评审的交付物）

1. **PR-GOV**（本支线首个提交，可先行合入）：本文件 + 治理指针更新。
2. **PR-M1** = A04 + B04 + B05（互不依赖的三张基础卡）。
3. **PR-M2** = A05 + B06。
4. **PR-M3** = A06 + A07。
5. **PR-M4** = A08（集成与设计验收，含两视口全工作面浏览器证据与设计差异单）。
6. **PR-M5** = B07（安装/压力/回退；独立复核后作为最终评审入口）。

每个 PR 的门：全量套件通过 + ruff + 该卡证据（核心/HTTP/浏览器分层，合成标注）+ 每卡独立 code-review（P1 零残留才可进组）+ CI 绿后合并 main，再开下一组。PR-M5 合并后向用户提交**最终评审包**：六个 PR 链接、各卡 AC 关闭矩阵、open 项清单（真实 Host/安装/用户执行项）、证据索引。

## 4. 冲刺纪律（沿用既有约定）

一次一卡；实施 → 独立评审 → 修复 → 复验 → 入组。改字段/语义先更新 INTERFACES 及消费者。证据必须含准确 head/base、命令与退出码、路径；合成证据标注。发现他卡缺陷回填 GAP-MATRIX 不顺手改。无发布授权不切默认入口。浏览器证据用真实服务 + 合成项目（fixture 落 `evidence/`，复用 `create_sample` 与 `tests/rebuild` 助手模式）。

## 5. 完成定义

- 9 卡全部按上述顺序合入 main（含 B07 在最终整合 SHA 上的重建验证）。
- 45 条新 AC 中工程层全部关闭；真实层（Host/30页/安装）如实标注 open 并给出原因与复现入口。
- 向用户发起最终评审：PR 组、AC 矩阵、open 清单、下一步建议（发布授权/真实项目验收/HOME 迁移）。
