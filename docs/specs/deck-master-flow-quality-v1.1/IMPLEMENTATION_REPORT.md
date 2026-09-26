# Flow Quality v1.1 工程候选与验收记录

日期：2026-09-26。分支：`codex/flow-quality`。

**当前进展：PR #39 的五项评审问题已补充修复与本地回归，远端门禁以 PR 当前提交的 Checks 为准。AC-17 真实 Codex 会话和用户本机迁移尚未执行。** 自动测试、合成材料与真实 CLI 输出不替代专业内容验收。

最新修复与 **528 项回归**见 [修复验证](../../qa/pr39-flow-quality/README.md)。下文 511 项测试、隔离安装结果和 dc2636e 安装候选是前一轮证据；该候选不包含后续修复，安装验收需从最终提交重新构建。

评审历史：在 `859d479` 核对时，[PR #39](https://github.com/MainQuestAI/Deck-Master/pull/39) 对 `d98e4b0` 提出的 1 项 P1、4 项 P2 中，仅工作台布局已由 `dc2636e` 修复；其余为删页/重排后旧 PPT 可能继续交付、历史恢复未恢复 content_basis、取消修订后无法续作、CI 缺少 rg。该版本两组 unit 失败、真实渲染通过。本次已补充这些修复及 AC-11/AC-13 的负向回归，原记录保留用于追溯。

## 范围与来源

从用户提供的 README、SPEC、TASKS、ACCEPTANCE、MIGRATION 开始核对。原包 37 个文件、36 条校验记录均通过；ZIP 与解压目录逐字节一致，原始规格完整保留在本目录。此报告是追加文件，不改动原规格及其校验清单。

接手时分支为 `863fa83`，已经包含 T1–T9 的初版实现。因此本轮以规格审查、负向复现、修复与运行验证为主，没有重复重建这些功能。原始基线 `c93f5a2` 的复现确实接受了只改受众后提交的旧 scoped 结果；当前代码以 `stale_input_context` 拒绝。

未扩展已砍掉的功能：不增加方法快照、method read、独立材料扫描/读取命令、材料清单文件、请求输入命令、撤销要求的关闭状态、用途标签、GUI 输入编辑区、runtime.json 或其他 Host 注册。目录直接进入 `--source`，用户答复由 Host 对话取得后用 `inputs update` 写入。

## 本轮修复

| 对应任务 | 修复与结果 |
|---|---|
| T1 | 工作单补齐 intent、staging 路径、安装 release 标识；材料与设计上下文读取派发时的版本，原文件及提取结果的路径真实可读。 |
| T3 | 材料先冻结字节再读取和保存；显式坏文件直接拒绝，目录坏文件进入 errored；处理目录链接循环，避免读取内容与落盘原件不一致。 |
| T4 | 保留材料限制信息；只改显示名不误判任务过期；显式阅读模式标记为 provided；事务回执可在提交前后故障中正确重放。 |
| T5 | input_revision 必须提交 content_update，不能通过整稿 pages 绕过局部更新；拒绝旧结果、迟到结果及非法增删组合；未变页的正文、蓝图、SVG、预览槽位与字节保留。 |
| T5 / 工作台 | 待更新时 delivery/handoff 拒绝，review/working 可导出并标注；更新提示只显示业务原因，放到页面网格之外，正文编辑与反馈保持可用。 |
| T6 | 输入变化后 content/privacy 的旧覆盖不能继续充当有效审阅，即使正文无变化；已有其他有效审阅保留，最终工作单只列当前缺口。 |
| T7–T8 | 方法保持 canonical 单一源；对直接 wheel 和 sdist→wheel 做真实字节比较；旧 Skill 清理及 legacy 命令提示保持一致。 |
| T9 | 按本机真实 manifest 结构识别迁移；提前检查目标占用，避免切换一半；只匹配旧 `current/skills/` 子树；回滚同步 Skill 状态。 |

本机 manifest 的实际 schema 是 `deck_master_companion_manifest.v3`，`adoption_policy` 位于 `skills[]` 内，而非顶层。安装器及隔离迁移测试均已按此修正。真实 HOME 只读复核仍为旧真实目录和 15 条断链，未修改配置、链接或第三方 Skill。

## 验证结果

- 最终代码全量测试：**511 passed in 90.59s**。日志：[pytest-final.log](../../../dist/flow-quality-20260926/pytest-final.log)。
- `ruff check src tools tests`、JavaScript 语法检查、`git diff --check` 通过。
- 最终 wheel 在隔离 HOME 的 **18 条真实 CLI 检查通过**：候选安装、激活、包内方法定位、占用拒绝、15 条旧链接迁移、幂等重试、回滚、目录材料、更新及导出。详见 [installed-cli-summary.json](../../../dist/flow-quality-20260926/installed-cli-summary.json) 与 [逐条命令输出](../../../dist/flow-quality-20260926/commands/)。
- 直接 wheel、sdist→wheel 中的 **9 个方法文件**与 canonical 逐字节一致，无 skills-references。证据：[wheel](../../../dist/flow-quality-20260926/package-verification.json)、[sdist→wheel](../../../dist/flow-quality-20260926/sdist-verification.json)。
- 真实浏览器检查了待更新提示、正文布局和编辑控件：1280px 视口下正文区域 1060px、侧栏 220px，无横向溢出。截图及数据：[截图](../../../dist/flow-quality-20260926/ui-proof.png)、[检查结果](../../../dist/flow-quality-20260926/ui-proof.json)。这是合成项目的界面验证，不是 AC-17。
- 基线缺陷对照：[scoped-input-regression.json](../../../dist/flow-quality-20260926/scoped-input-regression.json)。原包校验：[spec-package-verification.json](../../../dist/flow-quality-20260926/spec-package-verification.json)。本机只读状态：[user-install-readonly.json](../../../dist/flow-quality-20260926/user-install-readonly.json)。

真实 CLI 验证使用合成材料与合成 Page/SVG 输入，其中 PPTX 由真实编译器生成，用于验证导出行为；不作为 Host 首稿或业务质量证据。回滚至无 Skill 的旧版本使用旧格式发布记录夹具，验证真实 CLI 的结构兼容行为，未安装或执行历史旧二进制。

## 18 条验收对照

A 为自动测试，R 为真实命令或浏览器输出，H 为用户运行的新 Codex 会话。A 的主要入口为 [test_flow_quality.py](../../../tests/rebuild/test_flow_quality.py)，安装相关测试位于 [tests/rebuild](../../../tests/rebuild/)。

| AC | 状态 | 已有证据与边界 |
|---|---|---|
| 01 | A 通过 | create、continue、task status 的完整任务事实及阅读模式来源。 |
| 02 | A+R 通过 | 按 kind/intent 派发方法；真实安装方法路径、文件哈希和 release 标识正确。 |
| 03 | A 通过 | 输入改变后旧开放任务显示 stale。 |
| 04 | A 通过 | CLI 五类任务参数、task-file 合并及显式参数优先级。 |
| 05 | A 通过 | decisions 双来源、未知字段、brief 冲突返回 exit 2。 |
| 06 | A+R 通过 | 目录噪声、输出自身、根外链接跳过；普通 output 子目录保留。 |
| 07 | A 通过 | 显式坏文件不留下 Document；UUID 材料 ID 与旧 ID 兼容。 |
| 08 | A 通过 | 两份 input-context 的规定 digest 可复算。 |
| 09 | A 通过 | 幂等、冲突、过期 base、失败原子性、仅改显示名；补测回执故障恢复。 |
| 10 | A 通过 | superseded 与 input_revision 派发，原有页面、产物、审阅、outputs 保留。 |
| 11 | A 通过 | p01/p02 正文 hash 与 expected-effects 一致，真实非空测试槽位保持；p03 定向更新且禁用事实不进入结果。 |
| 12 | A+R 通过 | c93 原缺陷复现，当前旧 scoped / superseded 结果拒绝。 |
| 13 | A+R 通过 | 待更新时 delivery/handoff exit 3；review/working 可导出且标注；legacy_current 兼容。 |
| 14 | A 通过 | 六维唯一来源、真实缺口、输入变化后重审、逐页 pass 不冒充最终 pass。 |
| 15 | A+R 通过 | 两条打包路径字节一致，CWD 假文件无效，真实安装 compose doctor 通过。 |
| 16 | A+R 通过 | skills 只剩 deck-master 与 RESOLVER.md；无旧 Skill 实现引用。保留两个旧命令名称的迁移映射及其回归测试，legacy-map 正常。见 [扫描记录](../../../dist/flow-quality-20260926/scope-verification.json)。 |
| 17 | **H 待用户执行** | 仓库外新会话的 7 步场景尚未执行，不能宣布产品端到端验收通过。 |
| 18 | A+R 通过 | 隔离 HOME 验证注册、占用拒绝、15 链接迁移、第三方保护、重试与无 Skill 旧格式回滚。真实 HOME 迁移仍留给用户。 |

## 最终安装候选

- 发布标识：`dc2636e481d5-3f3af84b7243`
- 代码提交：`dc2636e481d52e210b97d1ac5c042377398f13e7`，构建时 `source_dirty=false`。
- [release.json](../../../dist/flow-quality-20260926/candidate-final/release.json)
- [wheel](../../../dist/flow-quality-20260926/candidate-final/deck_master-1.0.0.dev2-py3-none-any.whl)
- wheel SHA256：`3f3af84b72437b55d4d2e989785d4ba9898bfdf976939c2898002b6633713898`

`dist/flow-quality-20260926/` 是本机验证与候选目录，按仓库约定未提交到 Git。源代码、测试和本报告已提交；没有合并主线。该目录中的早期 `candidate/` 已被 `candidate-final/` 取代，安装请使用上面的最终候选。

## 用户执行的两项检查

先在本机完成候选安装和一次迁移。以下命令未替用户执行：

```bash
cd /Users/dingcheng/Coding-Project/02-key-project/Deck-Master

.venv/bin/python -m deck_master install candidate \
  --prefix "$HOME" \
  --manifest "$PWD/dist/flow-quality-20260926/candidate-final/release.json"

CODEX_HOME="$HOME/.codex" .venv/bin/python -m deck_master install activate \
  --prefix "$HOME" \
  --release-id dc2636e481d5-3f3af84b7243

"$HOME/.deck-master/bin/deck-master" doctor --step compose
ls -l "$HOME/.codex/skills/deck-master"
```

检查激活输出中的迁移报告：旧目录移至 `legacy-companion-<timestamp>` 并保留；移除的旧链接应为 15 条；唯一受管 Skill 指向 `current/skill/deck-master`；第三方 Skill 与 config.toml 不变。

随后在仓库外新开 Codex 会话，按 [ACCEPTANCE.md 的 AC-17](ACCEPTANCE.md#ac-177-步场景从仓库外新开的-codex-会话启动) 运行全部 7 步，保存命令、退出码、工作单、截图，以及第 4、5 步前后 p01/p02 的 hash。第二个新会话也属于该验收的一部分。

正常升级有 `previous` 发布时，回滚命令为：

```bash
CODEX_HOME="$HOME/.codex" "$HOME/.deck-master/bin/deck-master" install rollback --prefix "$HOME"
```

首次从旧 companion 目录迁移没有可执行的 previous 发布，不能把这条命令当作首次迁移的回退承诺；旧目录备份仍会保留。规格原文里的 `deck-master rollback` 不是当前命令，应使用上面的 `install rollback`。
