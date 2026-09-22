# Deck Master v0.9.12 Skill Suite Runtime - Master Stack Breakdown

## 0. 大轮次目标

把 Deck Master 从单一 skill 升级为可安装、可发现、可路由、可回收结果的 Skill Suite Runtime。

本轮完成后，用户应该能够：

1. 安装 Deck Master 后得到完整 suite 或明确的缺口报告。
2. 点名 Deck Master 时，Agent 先做 non-mutating readiness check，再进入 setup 或 run。
3. 在 Deck Master run 内调用 PPT Library / PPT Deck Pro Max / PPT Quality Gate / PPT Master，但所有外部结果必须通过 Deck Master import 才能影响 run state。
4. 仍然可以单独使用 companion skill。
5. Deck Master 能记录历史页检索、生成 handoff、质量审查、反馈事件，并形成可审查闭环。

## 1. 拆分原则

不按代码目录拆，而按 runtime 风险边界拆：

- Stack A 先解决安装、状态、路由、非突变保护。
- Stack B 再接入 companion contracts，先 dry-run / import，不做深业务算法。
- Stack C 最后收口反馈、治理、Review Cockpit 状态和 release QA。

## 2. 版本/PR 建议

| Stack | 建议版本 | PR 目标 | 是否可独立合并 |
|---|---|---|---|
| Stack A | v0.9.12a | Suite Runtime Foundation | 是 |
| Stack B | v0.9.12b | Companion Workflow Contracts | 是，依赖 A |
| Stack C | v0.9.12c | Production Closure & Governance | 是，依赖 A+B |

也可以合并成一个 v0.9.12 大 PR，但必须保持三段提交边界和三套验收记录。

## 3. 关键不变式

1. `setup-status` / `suite-status` 必须 non-mutating。
2. setup 未 production_ready 前，不允许创建或修改 production run。
3. companion skill 输出必须 import 后才影响 Deck Master run state。
4. bad JSON 不得覆盖已有 artifact。
5. install / repair 不得覆盖真实目录。
6. Deck Master 不新增内置 LLM provider。
7. 测试必须使用 temporary HOME；真实机器检查只允许 non-mutating status。
8. v0.9.12 不创建平行运行链路；已有 CLI、artifact reader、generation session、Review Cockpit 路径必须优先复用。
9. 新 artifact 路径必须兼容旧 reader，或同步更新所有 reader 并补回归测试。
10. Status / readiness / inspection 类命令不得写 `setup_events.jsonl`、`install_log.jsonl`、run events、workspace 文件或 production run artifact；只有 `setup`、`suite-install`、`suite-repair`、`import-*`、`record-* --apply` 这类显式 mutating 命令可以写入。
11. Companion output 只能作为 adapter input；Deck Master 内部状态源继续使用现有 canonical artifact，例如 `deck_generation_result.v1`、`deck_external_quality_review.v1`、`deck_quality_report.v1`、`library_results/selection.json.by_beat`。
12. Stack B 开始引入共享 `imports/import_log.jsonl` writer；所有新增 import 必须先写 canonical artifact，再记录 import log。
13. Review Cockpit 在 v0.9.12c 至少展示 suite readiness、blocking quality findings、pending feedback events；只有 CLI/JSON 且无 UI 可见状态时，release QA 必须标记为 degraded。

## 4. Stack A / v0.9.12a：Suite Runtime Foundation

目标：建立 suite 安装、状态、capability readiness、routing guard 和 first-run setup 的基础。

核心产出：

- `companion-manifest.v2`
- Companion Skill Source Matrix
- pure-read setup/suite/skill inspection API
- `setup-status.v2`
- `suite-status`
- `suite-install`
- `suite-repair`
- `setup-status --include-suite`
- Deck Master skill docs routing rewrite
- non-mutating setup-first guard

Done 后，Deck Master 还不需要真正调用 PPT Library / PPT Deck Pro Max / PPT Quality Gate 的业务能力，但必须知道哪些 capability ready、blocked、missing、optional_missing。

## 5. Stack B / v0.9.12b：Companion Workflow Contracts

目标：把 companion skills 接入 Deck Master run，但只做 contract、dry-run、import 和状态登记，不重写 companion 内部算法。

核心产出：

- shared `imports/import_log.jsonl` writer
- PPT Library read-only adapter
- `library-status`
- `search-library` 现有命令增强；`library-search` 如需新增，只能作为兼容 alias
- `import-library-selection`
- `external/ppt_library/library_results.json`，同时兼容现有 `library_results/selection.json` reader
- `sourcing_plan.json` 映射
- PPT Quality Gate structured findings adapter，归一化到现有 external quality review / quality report
- PPT Deck Pro Max generation handoff dry-run import，归一化到现有 generation session / generation result 状态机
- companion skill docs：standalone vs Deck Master run

Done 后，Deck Master 可以完成：检索历史页 -> import selection -> 形成 sourcing plan；创建 generation handoff -> import generation result；导入质量审查 findings。

## 6. Stack C / v0.9.12c：Production Closure & Governance

目标：完成业务闭环、反馈治理、Review Cockpit 状态、E2E QA 和 release hardening。

核心产出：

- `library_feedback_events.jsonl`
- `record-library-feedback --dry-run` default
- `record-library-feedback --apply` 只作为 experimental 显式能力，不进入默认验收
- suite readiness banner / Review Cockpit 最小状态集成，使用 `scripts/preview/server.py` 与 `scripts/preview/static/*`
- import log / metrics / readiness 报告收口
- E2E suite smoke
- release notes / QA report

Done 后，v0.9.12 可以作为完整业务轮次发布：用户入口、suite 安装、companion 路由、结果回收、质量审查、反馈事件和发布验证都闭环。

## 7. 推荐执行顺序

```text
A0 Pure-read inspection contract
A1 Companion source matrix freeze
A2 Suite install/status foundation
A3 First-run routing docs + guard
A4 Stack A QA
B0 Shared import log writer
B1 PPT Library adapter
B2 Quality Gate findings adapter
B3 Deck Pro Max handoff/result adapter
B4 Stack B QA
C1 Feedback event queue
C2 Review Cockpit/readiness integration
C3 Full suite smoke + release QA
```

## 8. 大轮次总验收

- 空 temporary HOME 下，suite install 可安装 required skill links。
- 重复 suite install idempotent。
- `setup-status --include-suite --output json` 和 `suite-status --output json` 不新增 HOME 文件、不改 mtime、不写 run artifact。
- setup 未 ready 时，Deck Master 不创建 production run。
- `setup-status --include-suite --output json` 返回 install/workspace/production/suite/capability/task_readiness。
- malformed external companion skill 会被识别为 `schema_incompatible` 或 `capability_missing`，并给出 next action。
- PPT Library missing CLI 时，library sourcing blocked，但 Deck Master status/setup 不被全局阻断。
- PPT Library selection import 保留 `run_id / beat_id / page_task_id / slot_id / candidate_id`，并兼容现有 `library_results/selection.json` 读取链路。
- PPT Quality Gate findings import 能映射到 Deck Master external quality gate classes，并输出现有 `deck_quality_report.v1`。
- PPT Deck Pro Max generation handoff 复用现有 generation session 状态机；companion result import 先归一化到现有 generation result schema，再影响 run state。
- feedback 默认只写 event queue，不默认写外部 PPT Library DB。
- 所有 external result 都进入 `imports/import_log.jsonl`。
- Review Cockpit 显示 suite readiness、blocking findings、pending feedback events。
- v0.9.11 production guards 保持有效。
