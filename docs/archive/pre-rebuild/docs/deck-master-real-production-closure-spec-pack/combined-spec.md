# Deck Master v0.9.14–v0.9.16 Real Production Closure — 完整 Spec

> 主仓基线：`origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177`



---

<!-- SOURCE: README.md -->

# Deck Master Real Production Closure Spec Pack

**迭代名称**：Real Production Closure
**规划版本**：v0.9.14 → v0.9.15 → v0.9.16
**主仓基线**：`MainQuestAI/Deck-Master origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177`
**状态**：待开发基线包
**最终目标**：把 Deck Master 从“可追踪的方案生产运行时”收口为“可以产出真实、可验证、可交付 Deck 的专家型 Private Beta / v1.0 RC 候选”。

## 一、这轮只解决什么

这轮只解决四件事：

1. **真实生产**：Production Run 不再由 placeholder generator 冒充完成。
2. **真实构建与渲染**：形成 HTML、PDF、PPTX 和逐页预览等真实产物。
3. **状态可信**：任何 `completed / ready / deliverable` 都必须由可解析、未过期、来源一致的真实 artifact 支撑。
4. **可发行、可证明**：release tree 自包含，并用真实案例 benchmark 证明效率和质量。

本轮不继续增加新的 P5 团队模块、Connector、Dashboard、行业模板或更多独立 Gate。

## 二、包内文件

| 路径 | 用途 |
|---|---|
| `00-master-spec.md` | 总目标、硬决策、范围、状态机与最终验收 |
| `01-baseline-gap-register.md` | 当前版本事实、Gap 与阻断项 |
| `02-cross-repo-contracts.md` | Deck Master、PPT Deck Pro Max、PPT Library、PPT Master 的边界 |
| `stacks/` | 三个顺序开发 Stack |
| `tasks/` | 16 个可直接交给 Agent 的任务 Spec |
| `schemas/` | 下一轮 canonical contract JSON Schema |
| `acceptance/` | QA、RC、真实 benchmark 的验收文件 |
| `agents/` | Codex / Claude Code 执行协议、提示词与评审协议 |
| `combined-spec.md` | 便于通读的一体化版本 |

## 三、建议执行顺序

```text
A0
 └─ A1
     ├─ A2（PPT-Deck-Pro-Max）
     ├─ A3（Deck Master Agent handoff/handback）
     └─ A4（PPT Master build/render）
          └─ A5（主链路与工作台）

B1
 ├─ B2
 ├─ B3
 └─ B4
     └─ B5

C1
 ├─ C2
 ├─ C3
 └─ C4
     └─ C5
```

Stack A、B、C 必须按顺序合并。单个 Stack 内允许并行，但 canonical schema 与状态语义必须先冻结。

## 四、开发完成后的产品口径

允许对外表述：

> Deck Master 可以在本地 Agent 工作流中，把客户材料、方案规划、历史资产、页面生产、构建渲染、质量审查、人工决策和交付产物统一到一个可追踪 Run，并对真实产物做可验证的交付判断。

不允许表述：

- “无人工即可稳定生成所有高质量 PPT”；
- “所有 PPTX 都是原生可编辑”；
- “已达到企业多人在线协作产品”；
- “已通过 10× 效率验证”，除非真实 benchmark 达到本包门槛。


---

<!-- SOURCE: 00-master-spec.md -->

# Deck Master v0.9.14–v0.9.16 Real Production Closure Master Spec

## 0. 文档控制

| 字段 | 内容 |
|---|---|
| 主仓基线 | `origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177` |
| 迭代目标版本 | v0.9.14、v0.9.15、v0.9.16 |
| 目标阶段 | 专家型 Private Beta → v1.0 RC 候选 |
| 主责任仓库 | `MainQuestAI/Deck-Master` |
| 关联仓库 | `MainQuestAI/PPT-Deck-Pro-Max`、`MainQuestAI/PPT-Library` |
| 默认执行环境 | local-first、Agent-facing、Codex 优先 |
| Provider 政策 | Deck Master 保持零内置 LLM Provider |
| 评审基线 | 以开发分支内提交的实际 implementation spec 为准 |

---

## 1. 一页结论

当前 Deck Master 已经有较完整的 Run OS、Suite、Review Workspace、质量治理和回归体系，但默认 generation 仍可产出伪 `.pptx` / `.png` placeholder，PPT Master 仅提供 fixture-safe HTML，交付验证也没有把“无法解析”强制判为阻断。

下一轮的唯一业务目标是：

> **让一个 Production Run 从真实客户材料出发，经过 Agent 生产、确定性构建、渲染、审查和人工批准，得到真实、可解析、未过期、来源可追踪的客户交付包；系统不得再用 placeholder 或仅有状态文件的结果冒充完成。**

完成本轮后，Deck Master 应具备：

- 真实 Agent 生产 handoff / handback；
- HTML、PDF、逐页 PNG 和有效 PPTX；
- artifact checksum、格式验证、来源指纹和 stale 判断；
- 单一 final readiness；
- 自包含 release tree；
- 至少 3 个真实案例 benchmark；
- 可审计的 v1.0 RC 候选证据。

---

## 2. 业务成功标准

### 2.1 必须实现

1. Production Run 中 placeholder 泄漏率为 0。
2. Generation `completed` 必须存在通过格式验证的真实产物。
3. 默认 client delivery 产出：
   - HTML；
   - PDF；
   - 逐页 PNG；
   - 有效 PPTX。
4. PPTX 必须声明 `editability`：
   - `native`；
   - `hybrid`；
   - `flat_image`。
5. `flat_image` 允许用于本轮 RC，但不得表述为“完全可编辑”。
6. 所有最终 artifact 必须有：
   - run-relative path；
   - media type；
   - size；
   - SHA-256；
   - producer；
   - source fingerprint；
   - created_at；
   - validation status。
7. Export、Review Workspace、Benchmark 统一读取同一份 `deck_final_readiness.v1`。
8. Release tree 不依赖原始 Git checkout。
9. 至少 3 个真实项目完整跑通。
10. 所有真实项目必须有人审，不允许以自动 Gate 代替最终批准。

### 2.2 量化门槛

| 指标 | RC 最低值 |
|---|---:|
| Production placeholder 泄漏 | 0 |
| 最终 artifact 可解析率 | 100% |
| run/session/source 绑定完整率 | 100% |
| 客户可见 P0 | 0 |
| 真实案例数量 | ≥ 3，推荐 5 |
| 首轮页面接受率中位数 | ≥ 65% |
| 单案例首轮接受率 | 不低于 50% |
| Review-ready 用时 / 人工基线 | ≤ 60% |
| 最终交付页数一致率 | 100% |
| Final readiness 与 Export 判定一致率 | 100% |
| Clean install 成功率 | 100%（规定环境） |
| Upgrade + rollback smoke | 全部通过 |

---

## 3. 硬架构决策

### D1：Deck Master 继续保持零内置 LLM Provider

Deck Master 不直接内置模型推理。它负责：

- 构造任务包；
- 调用或引导 Agent 使用 Product Capability Skill；
- 校验 handback；
- 维护 Run State；
- 构建、渲染和质量治理；
- 给出下一步。

语义生产由 Codex、Claude Code 或其他外部 Agent 完成。

### D2：Production 不允许 bundled placeholder generator

当前 placeholder adapter 只能保留在：

```text
tests/fixtures/
examples/
run_mode=fixture
run_mode=dev + explicit flag
```

任何 `run_mode=production` 调用 placeholder 都必须返回硬错误，并写入 typed event。

### D3：PPT Deck Pro Max 是生产编排能力，不是 Deck Master 的状态源

PPT Deck Pro Max 负责：

- 接收 Deck Master page task / brief / visual system；
- 形成专家生产项目；
- 组织 Agent 分页生产；
- 形成页面 artifact 和预览；
- 导出符合 Deck Master contract 的 result。

Deck Master Run 仍是唯一 canonical 状态源。

### D4：PPT Master 是确定性 Build / Render 能力

PPT Master 负责：

- 读取 `deck_build_manifest.v1`；
- 组装页面；
- 生成 HTML；
- 生成 PDF；
- 生成逐页 PNG；
- 生成有效 PPTX；
- 输出 `deck_render_result.v2`。

它不负责重新判断主叙事，也不负责生成客户内容。

### D5：完成状态以 artifact truth 为准

任何状态不得只看命令 return code。必须同时满足：

```text
process success
+ result schema valid
+ artifact exists
+ path safe
+ signature valid
+ checksum matches
+ source fingerprint fresh
+ expected page count matches
```

### D6：Final Readiness 只能有一个

新增：

```text
<run>/final_readiness.json
schema_version = deck_final_readiness.v1
```

以下模块必须读取它：

- CLI `final-readiness`；
- Review Workspace；
- Export；
- Benchmark RC；
- Delivery validation；
- `run-state` 的最终阶段。

### D7：发行包必须自包含

`~/.deck-master/current/bin/deck-master` 不得再硬编码原始仓库路径。Release 必须包含运行所需的：

- Python runtime source；
- skills；
- capability runtime；
- schemas；
- reference packs；
- static assets；
- capability lock；
- version manifest。

### D8：跨仓库能力必须锁版本

每个 release 必须生成 `deck_capability_lock.v1`，记录：

- source repository；
- source SHA；
- vendor / package path；
- content checksum；
- license；
- sync time；
- compatibility contract version。

---

## 4. 本轮范围

### 4.1 In Scope

- Generation result v2；
- Build manifest；
- Render result v2；
- Artifact manifest；
- Final readiness；
- PPT Deck Pro Max bridge；
- Agent dispatch package；
- HTML / PDF / PNG / PPTX 构建；
- artifact format validation；
- stale / lineage；
- Export 与 Review Workspace 强制统一；
- fixture / production 隔离；
- self-contained release；
- install / upgrade / rollback；
- real benchmark；
- CI / RC gate。

### 4.2 Out of Scope

- 新增企业服务端；
- 用户登录和真正 RBAC；
- 云端任务队列；
- 新建更多 Connector；
- 新增行业专用 planner；
- 大规模重写 Narrative Engine；
- 自研 LLM Provider；
- 重做 PPT Library 索引引擎；
- 原生协同编辑；
- 自动替代最终人工审查。

---

## 5. 目标主链路

```text
Setup / Suite Ready
        ↓
Context Intake
        ↓
Brief / Claim / Narrative / Page Tasks
        ↓
PPT Library real selection or explicit imported selection
        ↓
Sourcing Plan
        ↓
Generation Session Prepare
        ↓
Deck Master Agent Dispatch Package
        ↓
PPT Deck Pro Max Bridge Project
        ↓
External Agent produces real page artifacts
        ↓
Generation Result v2 Import + Artifact Validation
        ↓
Build Manifest
        ↓
PPT Master Build / Render
        ↓
Render Result v2 + Artifact Manifest
        ↓
Draft / Evidence / Brand / Confidentiality / Render / Delivery Gates
        ↓
Human Review / Approval
        ↓
Final Readiness
        ↓
Export Delivery Package
        ↓
Outcome / Metrics / Benchmark
```

---

## 6. Production Profiles

| Profile | 必需产物 | 使用场景 | 是否允许 fixture |
|---|---|---|---|
| `fixture` | HTML 或样例 preview | 单测、演示 | 允许 |
| `dev` | 自选 | 本地开发 | 仅显式允许 |
| `production_html` | HTML、PDF、逐页 PNG | Web / 留档交付 | 禁止 |
| `production_pptx` | HTML、PDF、逐页 PNG、PPTX | 客户 PPT 交付 | 禁止 |
| `benchmark` | 由 case 声明 | 真实评测 | 禁止真实 case 使用 fixture |
| `client_delivery` | 同 `production_pptx` | 默认正式交付 | 禁止 |

---

## 7. 状态模型

### 7.1 Generation Session v2

推荐状态：

```text
prepared
awaiting_agent_execution
running
result_files_present
results_imported
quality_required
ready_for_build
blocked
failed
```

禁止继续使用含义不清的 `completed` 作为业务完成态。

Legacy 映射：

| v1 | v2 |
|---|---|
| created | prepared |
| dispatched | awaiting_agent_execution |
| running | running |
| completed | result_files_present，仅在真实 result 存在时 |
| partial | result_files_present |
| results_imported | results_imported |
| preview_refreshed | quality_required 或 ready_for_build |
| quality_required | quality_required |
| blocked / failed | 不变 |

### 7.2 Build / Render

```text
build_prepared
building
build_completed
rendering
render_completed
artifact_validation_failed
quality_required
ready_for_review
```

### 7.3 Run 最终阶段

```text
needs_generation_execution
needs_generation_import
needs_build
needs_render
needs_artifact_repair
needs_quality_gate
needs_review
needs_approval
ready_for_client_export
delivered
```

---

## 8. 三个 Stack

### Stack A — v0.9.14 Real Production Runtime

解决真实生成、Agent handback、Build / Render 和主链路写回。

完成条件：

- Production placeholder 不可执行；
- PPT Deck Pro Max bridge 跑通；
- 至少一套真实页面 artifact 可导入；
- HTML / PDF / PNG / PPTX 可生成；
- Generation → Build → Render 状态自然推进。

### Stack B — v0.9.15 Artifact Truth & Final Readiness

解决格式真伪、过期状态、交付验证和统一 readiness。

完成条件：

- 伪 PPTX、伪 PNG、损坏 PDF 全部阻断；
- parse failure 为 P0；
- stale artifact 阻断；
- Export 和 UI 只认 final readiness；
- delivery package 具备 lineage。

### Stack C — v0.9.16 Release, Benchmark & RC

解决独立安装、升级回滚、真实 benchmark 和 RC 证据。

完成条件：

- Release tree 自包含；
- Clean install、upgrade、rollback 通过；
- 至少 3 个真实案例达标；
- 生成可下载 release artifact；
- RC checklist 全部通过。

---

## 9. 跨仓库职责

| 能力 | Deck Master | PPT Deck Pro Max | PPT Library |
|---|---|---|---|
| Run state | Owner | Consumer | Consumer |
| Narrative / Page tasks | Owner | Input | Input |
| 历史页搜索 | Orchestrate / Import | 可消费 | Owner |
| 页面生产 | Dispatch / Validate | Owner | 不负责 |
| HTML 页面装配上下文 | Contract owner | Producer | 不负责 |
| Build / Render | PPT Master owner | 可提供页面源 | 不负责 |
| Quality / Review | Owner | 自身 QA 可导入 | 不负责 |
| Artifact truth | Owner | 必须提供 metadata | 必须提供 selection metadata |
| Release | Owner | 被锁定和打包 | 被锁定或外部安装 |
| Final readiness | Owner | 不得自行声明 | 不得自行声明 |

---

## 10. 兼容与迁移

1. `deck_generation_result.v1`：
   - fixture/dev 继续读取；
   - production 仅在完成 v2 normalization、文件签名和 checksum 后接受。
2. `deck_render_result.v1`：
   - 保留 legacy read；
   - production final readiness 默认判为 `migration_required`。
3. 旧 suite symlink：
   - 先生成 migration plan；
   - 不静默覆盖 real directory；
   - 安装必须可回滚。
4. 旧 release tree：
   - 保留一版回滚；
   - 新版采用 versioned release directory + `current` symlink。
5. 旧 Review Workspace：
   - API 兼容；
   - 最终状态字段切换到 final readiness；
   - 老字段保留一个小版本并标记 deprecated。

---

## 11. Definition of Done

本轮只有同时满足以下条件才算完成：

- 代码实现完成；
- 全量单测通过；
- Contract tests 通过；
- Fixture E2E 通过；
- Production failure matrix 通过；
- 浏览器 smoke 通过；
- Temporary HOME full suite ready；
- Clean release install 通过；
- Upgrade / rollback 通过；
- 3 个真实案例完成；
- Benchmark 达标；
- 0 placeholder 泄漏；
- 0 客户可见 P0；
- 文档与实际 CLI 一致；
- actual implementation spec 和 deviation log 已提交；
- Draft PR 评审与最终 QA 完成。

任何单项未达成，均不得标记 v0.9.16 RC ready。


---

<!-- SOURCE: 01-baseline-gap-register.md -->

# Baseline & Gap Register

## 1. 基线

### 已确认基线

- Deck Master：`origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177`
- 当前 suite version：`0.9.13`
- Required capabilities：
  - deck-master
  - deck-planner
  - deck-review
  - ppt-master
  - ppt-library
  - ppt-deck-pro-max
  - ppt-quality-gate
- 当前 Provider policy：`zero_builtin_llm_provider`
- 当前 CI：compileall、全量 unittest、fixture autoplan smoke
- 当前工作台：方案项目工作台，支持页面、风险、审批、交付状态。

### 关联仓库基线

- PPT Deck Pro Max：当前公开主线已包含 Expert Mode、Visual Composition、Asset Pipeline 和 image-led HTML assemble 能力。
- PPT Library：当前公开主线为本地优先 PPTX 资产库 CLI，支持页级搜索、版本治理、关键页、复用追踪和 compose。
- 具体开发起点 SHA 必须由 Codex 在任务 A0 中重新核验并写入 capability lock。

---

## 2. 当前成熟能力

| 区域 | 当前事实 |
|---|---|
| Run OS | request、context、brief、claim、narrative、page task、sourcing、generation、review、quality、render、export 已有状态骨架 |
| Suite | 可构建 release tree、安装 required skill、检查 readiness、迁移 legacy skill |
| Generation Session | 有 run_id/session_id 绑定、result import、preview refresh |
| Quality | Draft、Evidence、Brand、Confidentiality、Render、Delivery 等 Gate 已有 |
| Review Workspace | 页面动作、来源、风险、审批、交付预览和截图审计已有 |
| Benchmark | case、runner、report、RC report 机制已有 |
| CI | 单测和 fixture smoke 已有 |

---

## 3. P0 Gap

### G-P0-01：Production Generator 仍可伪造完成

当前 bundled adapter 会把普通文本写入 `.pptx` 和 `.png` 文件，然后输出 completed result。

**影响**：

- 业务完成态不可信；
- artifact extension 与真实格式不一致；
- 后续 Gate 可能被伪产物穿透。

**本轮处理**：A2、A3、B1、B5。

### G-P0-02：PPT Master 仅有 fixture-safe HTML

当前 render 只能输出简单 HTML，不能代表真实客户交付。

**本轮处理**：A4。

### G-P0-03：Delivery Parse Failure 未强阻断

当前交付验证在 PPTX 解析异常时可能继续，不一定产生 P0。

**本轮处理**：B1、B2。

### G-P0-04：Release Tree 仍依赖 Git Checkout

当前安装脚本生成的 launcher 指向原始仓库脚本。

**本轮处理**：C1、C2。

### G-P0-05：没有单一 Final Readiness

Run state、Review readiness、Export、Delivery 和 Benchmark 存在不同判断口径。

**本轮处理**：B3、B4。

---

## 4. P1 Gap

| Gap | 影响 | 任务 |
|---|---|---|
| Generation result 缺 checksum / source fingerprint | 无法判断伪造和过期 | A1、B1 |
| Build 和 Render 边界不清 | 产物状态混乱 | A4 |
| PPTX editability 未声明 | 用户预期失真 | A4、B2 |
| Production / fixture 边界不够硬 | 演示能力可能混入交付 | A3、B5 |
| Cross-repo 版本未锁 | 同一 release 不可复现 | A0、C1 |
| PPT Deck Pro Max handback 非 canonical | 需要人工拼接 | A2 |
| PPT Library 真实检索 readiness 与 suite readiness 可能分离 | Source 决策质量不可控 | A5、B3 |
| 真实 benchmark 缺失 | 无法证明业务成熟 | C3 |
| 浏览器动作 smoke 不完整 | UI 回归风险 | B4、C4 |

---

## 5. 不在本轮解决的 Gap

- Planner 仍有 generic template 骨架；
- Team / Enterprise 只是本地合同原型；
- Native editable PPTX 质量可能仍依赖外部 build adapter；
- 复杂 PDF、飞书和 OpenViking ingestion 仍可通过外部流程；
- PPT Library 模型、OCR 和 embedding 的效果不由 Deck Master 本轮重写。

---

## 6. 开发前必须核验

以下内容必须由 Codex 在 A0 中核验：

1. Deck Master 当前全量测试数和结果。
2. `origin/main` 是否仍为 14fc43d。
3. PPT Deck Pro Max 当前 main SHA。
4. PPT Library 当前 main SHA。
5. 当前本机 suite status。
6. 当前 installed skill symlink / real directory 冲突。
7. Playwright、LibreOffice、python-pptx / PptxGenJS 可用性。
8. 真实 benchmark 项目的可用范围和脱敏规则。

核验结果写入：

```text
docs/specs/real-production-closure/implementation/baseline-lock.json
```


---

<!-- SOURCE: 02-cross-repo-contracts.md -->

# Cross-Repository Contracts

## 1. 总原则

1. Deck Master 是 contract owner 和 state owner。
2. PPT Deck Pro Max 是页面生产 orchestrator。
3. PPT Library 是历史资产检索 owner。
4. PPT Master 是 deterministic build / render owner。
5. 所有外部能力在 active Run 内产生的结果必须回写 Deck Master。
6. 所有路径必须为 Run-relative；禁止把本地绝对路径作为 canonical artifact path。
7. Production 不接受只写状态、不写真实 artifact 的成功结果。

---

## 2. Deck Master → PPT Deck Pro Max

### 输入：Generation Handoff Package

建议路径：

```text
<run>/handoffs/ppt_deck_pro_max/<session_id>/
  handoff_manifest.json
  request.json
  deck_brief.json
  claim_map.json
  narrative_plan.json
  page_tasks.json
  sourcing_plan.json
  visual_system/
  evidence/
```

`handoff_manifest.json` 至少包含：

- schema_version
- run_id
- session_id
- production_profile
- page task ids
- expected result schema
- output directory
- source fingerprint
- workspace references
- quality policy
- prohibited fixture flags

### PPT Deck Pro Max Bridge CLI

目标命令：

```bash
python scripts/run_deck_pipeline.py deck-master-import \
  --handoff <handoff_manifest.json> \
  --project-dir <session_project_dir>

python scripts/run_deck_pipeline.py deck-master-export \
  --project-dir <session_project_dir> \
  --run-id <run_id> \
  --session-id <session_id> \
  --output-dir <generation_results_dir>
```

Bridge 必须：

- 保留 run_id、session_id、task_id、page_id；
- 不修改 Deck Master 原始 artifact；
- 输出真实 artifact；
- 写 checksum；
- 标记 producer version / source SHA；
- 对未完成页输出 failed / partial，而不是假 completed。

---

## 3. PPT Deck Pro Max → Deck Master

输出使用 `deck_generation_result.v2`。

每页至少需要：

- 一个真实页面源：
  - HTML fragment；
  - page HTML；
  - SVG；
  - PNG；
  - native PPTX page；
  - 其他被 PPT Master 支持的 source。
- 一个真实 preview；
- artifact metadata；
- source fingerprint；
- producer provenance。

不允许：

- 文本文件改后缀；
- 0 字节文件；
- placeholder token；
- Run 外路径；
- run_id / session_id 不匹配；
- created_at 早于 handoff；
- 缺 checksum。

---

## 4. Deck Master → PPT Master

输入：`deck_build_manifest.v1`

建议路径：

```text
<run>/build/
  build_manifest.json
  source_snapshot.json
  theme/
  page_sources/
```

Build manifest 冻结：

- page order；
- page source artifact；
- profile；
- expected page count；
- visual system；
- fonts；
- output targets；
- source fingerprint；
- editability requirement。

PPT Master 不得自行改变 page order 或替换内容。

---

## 5. PPT Master → Deck Master

输出：

```text
<run>/render_results/render_result.json
<run>/artifacts/artifact_manifest.json
<run>/rendered/deck.html
<run>/rendered/deck.pdf
<run>/rendered/deck.pptx
<run>/rendered/pages/page_001.png
...
```

使用：

- `deck_render_result.v2`
- `deck_artifact_manifest.v1`

---

## 6. Deck Master ↔ PPT Library

PPT Library 继续通过真实 CLI 或 imported selection 工作。

Production 要求：

- `library_source` 只能是 `ppt_library` 或 `imported`；
- `fixture` 必须阻断，除非 run profile 明确为 fixture；
- selection 必须有 run_id；
- candidate 必须保留：
  - canonical_slide_id；
  - source file ref；
  - page number；
  - screenshot path；
  - confidence / score；
  - source mode；
  - query trace id；
  - index version（如果可用）。

Deck Master 不接管 PPT Library 的数据库和索引生命周期，但 Final Readiness 必须展示该 Run 是否使用真实检索、导入结果或 fixture。

---

## 7. Artifact Kind

Canonical kind：

```text
page_html
html_fragment
page_svg
page_png
page_jpeg
page_pptx
deck_html
deck_pdf
deck_pptx
asset_bundle
quality_report
source_snapshot
```

Canonical editability：

```text
native
hybrid
flat_image
not_applicable
unknown
```

Canonical validation：

```text
validated
invalid
unvalidated
stale
missing
```

---

## 8. Source Fingerprint

每个 build / render 必须计算：

```text
SHA256(
  ordered page_id
  + selected generation result sha256
  + selected library source sha256/ref
  + visual system hash
  + theme hash
  + build profile
)
```

任何输入变化后，旧 build / render 自动标记 stale。

---

## 9. Typed Events

新增或统一事件：

```text
generation.handoff.prepared
generation.awaiting_agent_execution
generation.result.rejected
generation.results.validated
build.manifest.created
build.started
build.completed
render.completed
artifact.validation.failed
artifact.stale.detected
final_readiness.updated
release.activated
release.rolled_back
benchmark.real_case.completed
```

事件必须包含：

- run_id；
- session/build id；
- refs；
- severity；
- message；
- source fingerprint（适用时）。

---

## 10. 错误分级

| 场景 | Severity |
|---|---|
| 文件扩展名与实际格式不符 | P0 |
| Production 使用 fixture / placeholder | P0 |
| run/session mismatch | P0 |
| 最终页数不一致 | P0 |
| artifact stale | P0 |
| required format missing | P0 |
| parse failure | P0 |
| PPTX flat-image 但客户要求 native | P1 |
| 非关键页面预览缺失 | P1 |
| 部分 metadata 缺失但可补算 | P1 |
| 视觉优化建议 | P2 |


---

<!-- SOURCE: stacks/v0.9.14-stack-a-real-production-runtime.md -->

# Stack A — v0.9.14 Real Production Runtime

## 1. 目标

把当前“placeholder generation + fixture HTML render”替换为真实 Agent 生产与确定性构建链路。

## 2. 范围

- v2 generation contract；
- PPT Deck Pro Max bridge；
- Agent handoff / handback；
- PPT Master build / render；
- Production profile；
- 状态机；
- Review Workspace 可见性。

## 3. 任务

| ID | 任务 | 主仓库 |
|---|---|---|
| A0 | Baseline & Contract Freeze | Deck-Master |
| A1 | Generation Result v2 | Deck-Master |
| A2 | PPT Deck Pro Max Bridge | PPT-Deck-Pro-Max |
| A3 | Agent Execution & Handback | Deck-Master |
| A4 | PPT Master Build / Render | Deck-Master |
| A5 | Runtime / Workspace Integration | Deck-Master |

## 4. 核心实现

### 4.1 取消 Production Placeholder

现有 fake generator：

- 迁移到测试 fixture；
- Production command 不再自动写假 `.pptx` / `.png`；
- 未配置执行器时进入 `awaiting_agent_execution`；
- Agent 完成后显式 import result。

### 4.2 Bridge Project

每个 generation session 创建独立 bridge project：

```text
<run>/external/ppt_deck_pro_max/<session_id>/
```

该目录可以由 PPT Deck Pro Max 使用，但不可成为最终状态源。

### 4.3 Build Profiles

本 Stack 必须实现：

- `production_html`
- `production_pptx`
- `client_delivery`

输出：

- HTML；
- PDF；
- page PNG；
- valid PPTX。

PPTX 第一阶段可为 flat-image，但必须明确标记。

### 4.4 CLI

新增或扩展：

```bash
deck-master generation-session prepare
deck-master generation-session dispatch
deck-master generation-session import-results
deck-master build prepare
deck-master build run
deck-master build status
deck-master render
deck-master artifact-status
```

不得要求普通用户手工拼接 JSON。

## 5. 验收

1. Production Run 无 placeholder。
2. Agent 未执行时状态为 waiting，而不是 completed。
3. 真实页面 artifact 可导入。
4. HTML、PDF、PNG、PPTX 均可打开。
5. 每个 artifact 有 checksum。
6. 页面数量一致。
7. run-state 自然推进到 quality / review。
8. Fixture E2E 仍可运行。
9. Existing CLI compatibility test 通过。
10. 全量测试通过。

## 6. Stack Exit Gate

只有完成一条真实样例链路：

```text
real context
→ plan
→ real generation artifact
→ build
→ render
→ artifact validation
```

才能合并 Stack A。


---

<!-- SOURCE: stacks/v0.9.15-stack-b-artifact-truth-readiness.md -->

# Stack B — v0.9.15 Artifact Truth & Final Readiness

## 1. 目标

确保系统的“完成、可审、可交付”与真实 artifact 完全一致。

## 2. 任务

| ID | 任务 |
|---|---|
| B1 | Artifact Validation |
| B2 | Delivery Validation & Lineage |
| B3 | Final Readiness |
| B4 | Export & Review Workspace Enforcement |
| B5 | Fixture Isolation & Regression |

## 3. Artifact Validation

必须检查：

- 文件存在；
- 非 0 字节；
- 扩展名；
- magic bytes；
- MIME；
- 包结构；
- 可解析；
- checksum；
- path traversal；
- source fingerprint；
- placeholder token；
- page count；
- stale。

### 文件签名最低要求

| 格式 | 检查 |
|---|---|
| PNG | `89 50 4E 47 0D 0A 1A 0A` |
| JPEG | `FF D8 FF` |
| PDF | `%PDF-` |
| PPTX | ZIP + `[Content_Types].xml` + `ppt/presentation.xml` |
| HTML | 可解析且包含预期 page container |
| SVG | XML 根节点为 svg |

## 4. Delivery Lineage

最终交付必须记录：

- Run；
- Build；
- source fingerprint；
- artifact hashes；
- Gate versions；
- review decisions；
- approvals；
- export time；
- producer versions；
- editability。

## 5. Final Readiness

强制维度：

```text
setup
suite
workspace
planning
sourcing
generation
build
render
artifact_validation
quality
review
approval
export
```

任一 required check blocked，最终状态必须 blocked。

## 6. Review Workspace

新增可见项：

- Production profile；
- artifact validity；
- stale；
- file size；
- SHA；
- producer；
- editability；
- missing required formats；
- final readiness blocking reasons。

## 7. 验收

- 伪 PPTX / PNG / PDF 全部 P0；
- parse failure P0；
- stale P0；
- Export 不再重复实现 readiness；
- UI 与 CLI 结论一致；
- 无 active override 的 P1 继续阻断；
- 浏览器 smoke 覆盖 artifact invalid、stale、ready。


---

<!-- SOURCE: stacks/v0.9.16-stack-c-release-benchmark-rc.md -->

# Stack C — v0.9.16 Release, Benchmark & RC

## 1. 目标

形成可独立安装、可升级回滚、可通过真实案例验证的 RC 候选版本。

## 2. 任务

| ID | 任务 |
|---|---|
| C1 | Self-contained Release Tree |
| C2 | Install / Upgrade / Rollback |
| C3 | Real Benchmark |
| C4 | CI / RC / Release Artifact |
| C5 | Docs & Release Closure |

## 3. 发行目录

```text
~/.deck-master/
  releases/
    0.9.16/
      bin/
      runtime/
      skills/
      capabilities/
      schemas/
      contracts/
      reference-packs/
      static/
      product-capability-manifest.json
      capability-lock.json
      release-manifest.json
  current -> releases/0.9.16
  previous -> releases/0.9.15
```

Launcher 必须通过自身相对路径寻找 runtime。

## 4. 安装事务

```text
download / build
→ stage
→ checksum verify
→ temp HOME smoke
→ activate current symlink
→ suite-status
→ rollback on failure
```

## 5. Real Benchmark

最低 3 个真实案例：

- 一份售前 / 商业方案；
- 一份技术方案或技术标；
- 一份产品 / 运营 / GTM 方案。

每个案例记录：

- manual baseline；
- context size；
- target pages；
- production profile；
- generation time；
- review-ready time；
- page acceptance；
- revision count；
- asset reuse；
- evidence coverage；
- P0/P1；
- final artifact validity；
- human notes。

客户原始资料不得提交到公开仓库。仓库只保留脱敏 case metadata 和 metrics。

## 6. RC 门槛

- Clean install pass；
- Upgrade from 0.9.13 pass；
- Rollback pass；
- 真实案例 ≥ 3；
- median acceptance ≥ 65%；
- review-ready time ≤ 60% baseline；
- artifact validity = 100%；
- placeholder = 0；
- client-visible P0 = 0；
- browser smoke pass；
- release archive / checksum / manifest 可下载。

## 7. Exit Gate

v0.9.16 只有在 `acceptance/rc-checklist.md` 全部勾选并附真实证据后，才能标记为 RC candidate。


---

<!-- SOURCE: tasks/A0-baseline-contract-freeze.md -->

# A0 — Baseline & Contract Freeze

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A0` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | None |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

锁定三仓实际开发起点、能力版本和本轮 canonical contract，防止后续按不同假设并行开发。

## 3. In Scope

- 核验三仓 HEAD。
- 核验全量测试。
- 核验本机 suite、依赖和安装冲突。
- 提交 implementation spec、baseline lock、capability lock 草案。
- 冻结 schema 名称、状态语义和 CLI 名称。

## 4. Out of Scope

不实现业务功能；不修复现有代码。

## 5. 必须实现

1. 新增 `baseline-lock.json`。
2. 新增 `implementation-spec.md`。
3. 新增 `implementation-spec.json`。
4. 新增 `spec-deviation-log.md`。
5. 生成三仓 source SHA 和 dependency inventory。
6. 确认真实 benchmark 候选项目。

## 6. 允许 / 预期修改路径

- `docs/specs/real-production-closure/implementation/`
- `docs/contracts/`
- `product-capability-manifest.json`（仅必要 metadata）
- `capability-lock.json`（新增）

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- JSON parse。
- Schema lint。
- `git diff --check`。
- 记录全量测试基线，不允许伪造通过。

## 8. 成功标准

- 所有 SHA 明确。
- 所有 contract 名称无冲突。
- 每个后续 Task 的依赖可定位。
- 评审明确以实际 implementation spec 为 baseline。

## 9. 风险

最大的风险是跨仓库 HEAD 变化。必须先 pin，再开发。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/A1-generation-contract-v2.md -->

# A1 — Generation Result v2 & Session Migration

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A1` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A0 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

建立可信 generation handback，消除 ambiguous completed 和缺 artifact metadata 的问题。

## 3. In Scope

- `deck_generation_result.v2`。
- Generation session v2 状态。
- v1 normalize / migration。
- run/session/path/fingerprint/checksum validation。
- typed events。

## 4. Out of Scope

不实现 PPT Deck Pro Max 生产；不实现 build。

## 5. 必须实现

1. 增加 v2 validator。
2. Completed/partial 必须有真实 artifact。
3. 所有 artifact 必须 run-relative。
4. 导入时计算或校验 SHA。
5. v1 仅在安全 normalization 后接受。
6. Production 禁止 v1 placeholder。
7. 状态改为 `result_files_present → results_imported → quality_required / ready_for_build`。
8. 错误写 rejected import log。

## 6. 允许 / 预期修改路径

- `scripts/generation/handback.py`
- `scripts/generation/session.py`
- `scripts/validators/`
- `scripts/runtime/run_state_resolver.py`
- `docs/contracts/`
- `tests/test_generation_*`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- valid v2 import。
- run mismatch。
- session mismatch。
- absolute / traversal path。
- checksum mismatch。
- missing artifact。
- legacy valid migration。
- legacy placeholder rejection。
- stale fingerprint。

## 8. 成功标准

- v2 contract tests 100% pass。
- Production 无 artifact 不可完成。
- 旧 fixture 测试仍可通过显式 fixture profile。

## 9. 风险

迁移可能破坏现有 tests，必须增加 profile-aware compatibility。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/A2-ppt-deck-pro-max-bridge.md -->

# A2 — PPT Deck Pro Max Bridge

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A2` |
| Repository | `MainQuestAI/PPT-Deck-Pro-Max` |
| Depends on | A0, A1 contract freeze |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让 PPT Deck Pro Max 可直接消费 Deck Master handoff，并导出 canonical v2 generation results。

## 3. In Scope

- Bridge import。
- Bridge project manifest。
- Page/task ID 保留。
- Agent dispatch context。
- Real artifact export。
- Producer provenance。
- Bridge tests。

## 4. Out of Scope

不维护 Deck Master Run State；不自行声明 final readiness；不重写 Deck Master planner。

## 5. 必须实现

1. 新增 `deck-master-import`。
2. 新增 `deck-master-export`。
3. 将 Deck Master task 映射到 clean page / visual composition / asset jobs。
4. 导出每页 result JSON。
5. 未完成页不得 completed。
6. 输出 producer version、source SHA、artifact checksum。
7. 禁止向 Deck Master Run 外写 canonical state。
8. Bridge 支持 image-led HTML 页面源。

## 6. 允许 / 预期修改路径

- `scripts/run_deck_pipeline.py`
- `scripts/deck_master_bridge.py`（新增）
- `references/deck_master_*.schema.json`
- `tests/test_deck_master_bridge.py`
- `README*` bridge section

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- import fixture handoff。
- malformed handoff。
- ID round-trip。
- page artifact export。
- missing page。
- partial batch。
- checksum。
- no path escape。

## 8. 成功标准

- Deck Master handoff 可一条命令导入。
- 至少 3 页真实 HTML/PNG artifact 导出。
- v2 schema valid。
- 不出现假后缀文件。

## 9. 风险

现有 PPT Deck Pro Max pipeline 状态可能与 Deck Master page task 不一一对应，需要显式 mapping 文件。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/A3-agent-execution-handback.md -->

# A3 — Agent Execution Package & Handback

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A3` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A1, A2 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把 Production generation 从假 subprocess 改为真实 Agent 驱动任务包，并自动验证回写。

## 3. In Scope

- prepare / dispatch / import。
- Codex-first skill instructions。
- Bridge invocation guidance。
- Execution receipt。
- Batch import。

## 4. Out of Scope

不内置模型 API；不在 CLI 后台异步等待 Agent。

## 5. 必须实现

1. 移除 Production bundled fake execution。
2. `dispatch` 输出可直接供 Agent 执行的 package。
3. 状态为 `awaiting_agent_execution`。
4. 支持 batch result import。
5. 每次 import 写 receipt。
6. 已导入结果幂等。
7. Agent 失败可恢复。
8. Fixture adapter 迁入 test-only。

## 6. 允许 / 预期修改路径

- `scripts/capabilities/ppt_deck_pro_max.py`
- `scripts/generation/dispatch.py`（新增）
- `scripts/generation/session.py`
- `skills/ppt-deck-pro-max/`
- `skills/deck-master/playbooks/`
- `tests/`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- Production dispatch。
- Fixture dispatch。
- no executor。
- batch partial import。
- duplicate import。
- retry。
- receipt and event。

## 8. 成功标准

- Production 命令不生成 placeholder。
- Agent package 包含完成任务所需上下文。
- Agent 完成后可一条 import 命令回写。

## 9. 风险

需要避免 Agent package 泄露超出 Run 的客户资料；只打包允许的 source refs。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/A4-ppt-master-build-render.md -->

# A4 — PPT Master Production Build / Render

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A4` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A1, A2/A3 result shape |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把真实页面源组装为客户可用 HTML、PDF、逐页 PNG 和有效 PPTX。

## 3. In Scope

- Build manifest。
- HTML assemble。
- Playwright render。
- PDF。
- page PNG。
- PPTX output。
- artifact manifest。
- editability declaration。

## 4. Out of Scope

不生成主叙事；不重新改写页面内容；不实现模型推理。

## 5. 必须实现

1. 新增 build prepare/run/status。
2. HTML 页面顺序必须与 manifest 一致。
3. PDF 和 PNG 由最终 HTML 渲染。
4. PPTX 至少支持 flat-image，有 native adapter 时标记 native/hybrid。
5. 输出 checksum、size、media type。
6. 字体缺失写 warning。
7. Build source fingerprint。
8. 任一 required output 失败时不能 completed。

## 6. 允许 / 预期修改路径

- `scripts/runtime/build.py`（新增）
- `scripts/runtime/render.py`
- `scripts/capabilities/ppt_master.py`（新增或重建）
- `product_capabilities/ppt-master/runtime/`
- `docs/contracts/`
- `tests/test_build_runtime.py`
- `tests/test_render_runtime.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- 3/12/60 页。
- Unicode / 中文。
- missing image。
- invalid page source。
- HTML open。
- PDF signature。
- PNG signature。
- PPTX parse。
- page count。
- source fingerprint。
- editability metadata。

## 8. 成功标准

- Client delivery 4 类产物全部存在且有效。
- 页数一致。
- Render result v2 valid。
- 不再调用 fixture-only HTML 作为 Production 默认。

## 9. 风险

浏览器、字体和 LibreOffice/PPTX 生成环境差异；需要明确 dependency doctor。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/A5-runtime-workspace-integration.md -->

# A5 — Runtime & Review Workspace Integration

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A5` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A1-A4 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让真实 generation/build/render 状态进入 Run State、Next Step 和方案工作台。

## 3. In Scope

- Run stage。
- Next command。
- Workspace APIs。
- Artifact cards。
- Build/render actions。
- Source mode visibility。

## 4. Out of Scope

不做最终 final readiness（B3）；不重构整套前端。

## 5. 必须实现

1. 新增 needs_generation_execution / needs_build / needs_render。
2. Workspace 展示 producer、profile、format、editability。
3. Fixture / imported / real 明确 badge。
4. Artifact invalid 显示阻断。
5. 页面预览使用真实 page PNG/HTML。
6. API 继续兼容旧字段。

## 6. 允许 / 预期修改路径

- `scripts/runtime/run_state_resolver.py`
- `scripts/runtime/next_step.py`
- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/*`
- `tests/test_run_state_resolver.py`
- `tests/test_preview_server.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- 状态推进。
- API payload。
- no preview。
- build pending。
- render complete。
- fixture badge。
- browser desktop smoke。

## 8. 成功标准

- 用户能从工作台看清当前卡在 Agent、Build、Render 还是质量。
- 不再出现 completed 但无真实预览。

## 9. 风险

UI 可能同时读取旧 readiness，B3 前需保持兼容层。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/B1-artifact-validation.md -->

# B1 — Artifact Validation

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B1` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | Stack A complete |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

建立统一 artifact truth validator。

## 3. In Scope

- magic bytes。
- MIME。
- package parse。
- checksum。
- path safety。
- placeholder detection。
- stale detection。
- validation report。

## 4. Out of Scope

不判断商业质量和视觉审美。

## 5. 必须实现

1. 实现 PNG/JPEG/PDF/PPTX/HTML/SVG validator。
2. PPTX 检查 ZIP 核心文件。
3. HTML 检查 page container 和数量。
4. placeholder token / tiny file 规则。
5. checksum mismatch 阻断。
6. 输出 `artifact_validation_report.v1`。
7. Production invalid 一律 P0。

## 6. 允许 / 预期修改路径

- `scripts/validation/artifacts.py`（新增）
- `scripts/validation/signatures.py`（新增）
- `scripts/validators/`
- `tests/test_artifact_validation.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

覆盖所有格式的 valid/corrupt/fake/empty/path traversal/checksum mismatch/stale。

## 8. 成功标准

- 伪后缀 100% 检出。
- parse error 不被吞掉。
- validator 可被 generation、render、delivery 复用。

## 9. 风险

过严的最小尺寸规则可能误伤，规则应 profile-aware。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/B2-delivery-validation-lineage.md -->

# B2 — Delivery Validation & Lineage

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B2` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | B1 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

修复交付验证的弱失败，并建立最终版本 lineage。

## 3. In Scope

- delivery validator。
- required formats。
- page count。
- source fingerprint。
- gate snapshot。
- review snapshot。
- final lineage。

## 4. Out of Scope

不决定最终 ready；该结论由 B3 聚合。

## 5. 必须实现

1. Parse failure 生成 P0。
2. 必需产物缺失 P0。
3. 页数不一致 P0。
4. stale P0。
5. 客户要求 native 但 flat-image 为 P1。
6. 写 `final_version_lineage.json`。
7. 保存 gate / approval refs 和 hashes。
8. 验证结果可重跑且幂等。

## 6. 允许 / 预期修改路径

- `scripts/delivery/validate.py`
- `scripts/delivery/lineage.py`（新增）
- `scripts/quality/gate_runner.py`
- `tests/test_delivery_validation.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- invalid pptx。
- missing PDF。
- page mismatch。
- stale。
- flat/native requirement。
- gate snapshot。
- idempotency。

## 8. 成功标准

- 任何不可解析交付文件都不能 pass。
- lineage 可追到每页输入和 producer。

## 9. 风险

Lineage 文件可能较大，应保存 refs 和 hashes，不复制全部内容。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/B3-final-readiness.md -->

# B3 — Canonical Final Readiness

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B3` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | B1, B2 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

建立唯一最终 readiness，消除 CLI、UI、Export、Benchmark 的口径分散。

## 3. In Scope

- readiness schema。
- check registry。
- blocker aggregation。
- CLI。
- run-state integration。
- freshness。

## 4. Out of Scope

不修复各个 Gate 的业务规则。

## 5. 必须实现

1. 新增 `runtime/final_readiness.py`。
2. 输出 `final_readiness.json`。
3. required checks 按 profile 配置。
4. 每个 check 返回 status、reason、refs。
5. status 只允许 ready/degraded/blocked。
6. Run 最终 stage 读取它。
7. 所有 consumer 禁止复制判断逻辑。

## 6. 允许 / 预期修改路径

- `scripts/runtime/final_readiness.py`
- `scripts/runtime/run_state_resolver.py`
- `scripts/deck_master.py`
- `docs/contracts/`
- `tests/test_final_readiness.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- all ready。
- each single blocker。
- multiple blockers。
- degraded optional。
- stale refresh。
- profile variation。
- deterministic order。

## 8. 成功标准

- CLI/UI/export 同一 run 返回同一结论。
- 每个 blocker 有可执行 next action。

## 9. 风险

旧 API 可能依赖旧字段；需保留 derived compatibility fields。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/B4-export-review-workspace.md -->

# B4 — Export & Review Workspace Enforcement

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B4` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | B3 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让 Export 和工作台严格服从 final readiness。

## 3. In Scope

- Export gate。
- UI final readiness。
- artifact inspection。
- approval。
- delivery package。

## 4. Out of Scope

不重写页面审查交互。

## 5. 必须实现

1. Client export 前强制 final readiness ready。
2. Internal export 可降级但必须标记。
3. Delivery package 包含 artifact manifest、lineage、readiness、approvals。
4. UI 展示 blockers、stale、editability。
5. API 不再自行推断 export ready。
6. 浏览器动作 smoke。

## 6. 允许 / 预期修改路径

- `scripts/orchestrate/export_queue.py`
- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/*`
- `tests/test_export_queue.py`
- `tests/test_preview_server.py`
- browser smoke scripts

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- blocked export。
- ready export。
- internal degraded export。
- P1 override。
- stale after approval。
- UI parity。

## 8. 成功标准

- 任何 client export 与 final readiness 不一致均为测试失败。
- 用户能看到明确修复动作。

## 9. 风险

避免在 UI 隐藏底层 refs；主标题用业务语言，详情可展示技术证据。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/B5-fixture-isolation-regression.md -->

# B5 — Fixture Isolation & Regression

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B5` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A3, B1-B4 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

彻底隔离 fixture/dev 与 production，防止测试能力进入正式交付。

## 3. In Scope

- fixture adapter relocation。
- runtime guards。
- test markers。
- CI scans。
- production E2E failure tests。

## 4. Out of Scope

不删除 fixture 能力。

## 5. 必须实现

1. Fake generator 移至 tests/fixtures。
2. Production import fixture source P0。
3. `--allow-fixture-*` 在 production 无效。
4. CI 扫描 production runtime 中 placeholder token。
5. 示例路径显式 run_mode=fixture。
6. Regression test 覆盖 legacy commands。

## 6. 允许 / 预期修改路径

- `tests/fixtures/`
- `examples/`
- `scripts/capabilities/`
- `.github/workflows/ci.yml`
- `tests/test_fixture_boundaries.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- source scan。
- production fake execution。
- fixture allowed。
- dev explicit allowed。
- benchmark real case forbidden。
- legacy regression。

## 8. 成功标准

- Production 路径 0 placeholder。
- CI 自动阻止回归。

## 9. 风险

字符串扫描可能误报文档，需要限定 runtime paths。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/C1-self-contained-release-tree.md -->

# C1 — Self-contained Release Tree

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C1` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | Stack B complete |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把 release 从源码仓软链接升级为真正自包含版本目录。

## 3. In Scope

- runtime copy/package。
- relative launcher。
- capability lock。
- release manifest。
- versioned releases。
- checksums。

## 4. Out of Scope

不发布到 PyPI；不实现在线 updater。

## 5. 必须实现

1. Release 包含完整 runtime。
2. launcher 不引用 repo root。
3. vendor/pin required capability runtime。
4. 生成 capability lock。
5. 生成 release manifest 和 SHA256SUMS。
6. current/previous symlink。
7. runtime doctor 检查 missing files。

## 6. 允许 / 预期修改路径

- `scripts/skills/installer.py`
- `scripts/release/`（新增）
- `product-capability-manifest.json`
- packaging scripts
- `tests/test_release_tree.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- build release outside repo。
- move/delete repo 后 CLI 仍可运行。
- checksum。
- missing file doctor。
- target skill links。

## 8. 成功标准

- Release 在临时目录独立运行。
- 无 repo-root dependency。
- 所有 required capability 有 lock。

## 9. 风险

Vendored 跨仓代码需处理 license 和同步流程。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/C2-install-upgrade-rollback.md -->

# C2 — Transactional Install / Upgrade / Rollback

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C2` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | C1 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

提供安全安装、升级和回滚。

## 3. In Scope

- stage/verify/activate。
- migration plan。
- backup。
- rollback。
- failure recovery。
- temp HOME smoke。

## 4. Out of Scope

不做自动联网更新。

## 5. 必须实现

1. 安装先 stage。
2. Verify 后原子切 current。
3. 保留 previous。
4. legacy real dir 不静默覆盖。
5. upgrade from 0.9.13。
6. rollback command。
7. 失败自动恢复。
8. install log。

## 6. 允许 / 预期修改路径

- `scripts/release/install.py`
- `scripts/skills/installer.py`
- CLI commands
- `tests/test_release_install.py`
- `tests/test_skill_installation.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- clean install。
- reinstall。
- upgrade。
- broken release。
- real dir conflict。
- rollback。
- symlink repair。
- multi-target。

## 8. 成功标准

- Temporary HOME 全部通过。
- 安装失败不破坏当前可用版本。

## 9. 风险

macOS symlink、权限和路径空格需要单独测试。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/C3-real-benchmark.md -->

# C3 — Real Case Benchmark

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C3` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | Stack B complete; A0 benchmark candidates |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

用真实客户项目证明生产闭环和业务效果。

## 3. In Scope

- real case schema。
- local-only inputs。
- baseline。
- metrics。
- manual review。
- aggregate report。

## 4. Out of Scope

不把客户原文提交到公开仓库；不以 fixture 代替 real case。

## 5. 必须实现

1. 建立 ≥3 个 real case。
2. 原始路径留本地。
3. Repo 保存脱敏 metadata。
4. 自动采集时间、接受率、修改次数、artifact validity。
5. 人工记录质量结论。
6. 生成 aggregate RC report。
7. 失败案例不得删除。

## 6. 允许 / 预期修改路径

- `benchmarks/cases/real_*` metadata
- `scripts/benchmark/`
- `docs/qa/real-benchmark/`
- `tests/test_real_benchmark_contract.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- local path absent。
- missing baseline。
- invalid artifact。
- acceptance calculation。
- aggregate median。
- privacy scan。

## 8. 成功标准

- 3 case 完整。
- 指标达到 Master Spec。
- 0 私有原文入库。
- 报告可复核。

## 9. 风险

真实项目差异大，必须同时保留定量指标和人工说明。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/C4-ci-rc-release.md -->

# C4 — CI, RC Gate & Release Artifact

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C4` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | C1-C3 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把本轮验收固化为 CI/RC gate，并生成发行物。

## 3. In Scope

- CI jobs。
- contract tests。
- fixture E2E。
- package smoke。
- browser smoke。
- RC report。
- archive/checksum。

## 4. Out of Scope

CI 不运行私有真实客户资料。

## 5. 必须实现

1. CI 增加 schema、artifact validator、release tree smoke。
2. Fixture E2E。
3. Browser smoke。
4. Release archive。
5. SHA256SUMS。
6. RC report command。
7. Real benchmark 结果以外部 evidence import。

## 6. 允许 / 预期修改路径

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `scripts/release/`
- `scripts/benchmark/report.py`
- `tests/`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- Linux CI。
- temp HOME。
- release archive unpack。
- moved repo test。
- browser smoke。
- RC blocked/pass fixtures。

## 8. 成功标准

- Main branch CI 稳定。
- Release artifact 可下载和验证。
- RC gate 缺任何证据都 blocked。

## 9. 风险

Playwright/LibreOffice 在 CI 的可用性可能不稳定，应分 required deterministic job 与 platform smoke。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: tasks/C5-docs-release-closure.md -->

# C5 — Documentation & Release Closure

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C5` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | C1-C4 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

让安装、使用、故障诊断、能力边界和发布说明与真实实现一致。

## 3. In Scope

- README。
- Quick start。
- Agent guide。
- Migration。
- Troubleshooting。
- Release notes。
- Architecture update。
- Known limitations。

## 4. Out of Scope

不写超出实现的市场承诺。

## 5. 必须实现

1. 一条最短 Production path。
2. 一条 Agent path。
3. Build profiles 和 editability。
4. Fixture boundary。
5. Install/upgrade/rollback。
6. Benchmark 结果。
7. Known limitations。
8. 删除旧 placeholder 叙述。

## 6. 允许 / 预期修改路径

- `README*`
- `docs/releases/`
- `docs/guides/`
- `skills/*/SKILL.md`
- `docs/specs/index`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- docs command smoke。
- link check。
- CLI help parity。
- forbidden stale command scan。

## 8. 成功标准

- 文档命令可执行。
- 对外口径与 RC 证据一致。
- 不再把 flat-image 说成 fully editable。

## 9. 风险

文档最容易滞后，必须从 CLI help 和 schema 自动生成部分内容。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。


---

<!-- SOURCE: acceptance/acceptance-matrix.md -->

# Acceptance Matrix

## 1. Stack A

| Case | 预期 |
|---|---|
| Production 无执行器 | `awaiting_agent_execution`，不产出假文件 |
| PPT Deck Pro Max bridge 3 页 | 3 个 v2 result，真实 artifact |
| run_id mismatch | reject + P0 event |
| Agent partial result | partial，不冒充全量完成 |
| Build HTML | 可打开、页数正确 |
| Build PDF | `%PDF-`，页数正确 |
| Build PNG | 每页真实 PNG |
| Build PPTX | 可被 python-pptx / LibreOffice 打开 |
| page order | 与 manifest 完全一致 |
| source change | old build stale |

## 2. Stack B

| Case | 预期 |
|---|---|
| 文本改名 `.pptx` | P0 blocked |
| 文本改名 `.png` | P0 blocked |
| 损坏 PDF | P0 blocked |
| 0 byte artifact | P0 blocked |
| checksum mismatch | P0 blocked |
| stale render | P0 blocked |
| missing required format | P0 blocked |
| flat-image + native required | P1 blocked，需修复或授权 |
| all ready | final readiness ready |
| Export 与 readiness 不一致 | 测试失败 |

## 3. Stack C

| Case | 预期 |
|---|---|
| Release build outside repo | 成功 |
| 删除原 repo 后运行 | 成功 |
| Clean temp HOME install | full_suite_ready=true |
| Upgrade 0.9.13 → 0.9.16 | 成功 |
| Broken staged release | current 不受影响 |
| Rollback | 恢复 previous |
| 3 real cases | 完整报告 |
| Private source scan | 无客户原文提交 |
| RC 缺 benchmark evidence | blocked |
| RC 全部达标 | candidate ready |

## 4. 不可豁免项

以下不允许 override：

- Production placeholder；
- run/session mismatch；
- invalid format；
- path traversal；
- checksum mismatch；
- stale final artifact；
- missing required final artifact；
- 客户可见 P0；
- final page count mismatch。

P1 可按既有 override governance 处理，但必须绑定 finding_id、approver、reason 和有效期。


---

<!-- SOURCE: acceptance/qa-test-plan.md -->

# QA Test Plan

## 1. 测试层级

1. Unit
2. JSON Schema / Contract
3. Adapter
4. Integration
5. Fixture E2E
6. Production failure E2E
7. Browser smoke
8. Clean install
9. Upgrade / rollback
10. Real benchmark

## 2. 必跑命令

最终命令以实际实现为准，但至少包括：

```bash
python3 -m compileall scripts tests
python3 -m unittest discover -s tests
git diff --check HEAD
```

新增：

```bash
deck-master contract-validate --all
deck-master release-build --output /tmp/deck-master-release
deck-master release-smoke --release /tmp/deck-master-release --temp-home
deck-master benchmark-rc-report --real-only
```

## 3. Failure Matrix

必须自动生成下列坏产物：

- fake.pptx（普通文本）
- corrupt.pptx（坏 ZIP）
- missing-content-types.pptx
- fake.png
- truncated.png
- fake.pdf
- empty.html
- page-count-mismatch.html
- stale artifact manifest
- checksum mismatch
- absolute path result
- traversal path result
- wrong run_id
- wrong session_id
- fixture source in production

每项都必须有明确 finding 和 next action。

## 4. Browser Smoke

桌面 1600 / 1440 / 1280：

- awaiting Agent；
- generation partial；
- build blocked；
- artifact invalid；
- artifact stale；
- needs quality；
- needs approval；
- ready for export；
- delivered。

动作：

- 查看 artifact 详情；
- 跳转 blocker；
- 批准页面；
- 提交审批；
- 重新计算 readiness；
- 确认交付。

## 5. 真实案例 QA

每个真实案例保存：

- command log；
- timestamps；
- run-state snapshots；
- artifact validation report；
- quality reports；
- review decisions；
- final readiness；
- delivery package hash；
- benchmark metrics；
- 人工结论。

## 6. QA 裁决

- P0：阻断合并或 RC。
- P1：默认阻断 Stack Exit；只有明确归属下一 Stack 且不影响本 Stack 业务目标时可延期。
- P2：可进入 backlog，但必须记录。


---

<!-- SOURCE: acceptance/rc-checklist.md -->

# v0.9.16 RC Checklist

## Code & Contract

- [ ] A0–A5 完成
- [ ] B1–B5 完成
- [ ] C1–C5 完成
- [ ] 所有 canonical schema 已提交
- [ ] spec deviation 已关闭或明确接受
- [ ] 全量测试通过
- [ ] git diff check clean

## Production Truth

- [ ] Production placeholder = 0
- [ ] Fake extension failure matrix 全部阻断
- [ ] Required artifact parse = 100%
- [ ] Source fingerprint stale test 通过
- [ ] run/session binding = 100%
- [ ] final page count = 100%

## Delivery

- [ ] HTML 可打开
- [ ] PDF 可打开
- [ ] 每页 PNG 可打开
- [ ] PPTX 可打开
- [ ] PPTX editability 已声明
- [ ] Artifact manifest 完整
- [ ] Lineage 完整
- [ ] Final readiness ready
- [ ] Export package hash 已记录

## Release

- [ ] Release tree 自包含
- [ ] 原仓移动后 CLI 可用
- [ ] Clean install
- [ ] Upgrade from 0.9.13
- [ ] Rollback
- [ ] Codex targets ready
- [ ] Claude Code targets ready
- [ ] Release archive
- [ ] SHA256SUMS
- [ ] Capability lock

## Real Benchmark

- [ ] ≥3 real cases
- [ ] median first-pass acceptance ≥65%
- [ ] each case acceptance ≥50%
- [ ] review-ready ratio ≤60%
- [ ] client-visible P0 = 0
- [ ] artifact validity = 100%
- [ ] private source scan clean
- [ ] human review evidence complete

## Documentation

- [ ] Quick Start 与 CLI 一致
- [ ] Agent playbook 与实际路径一致
- [ ] Migration guide
- [ ] Troubleshooting
- [ ] Known limitations
- [ ] Release notes
- [ ] 不宣称 flat-image fully editable

只有全部勾选后，才能写：`v0.9.16 is an RC candidate`。


---

<!-- SOURCE: agents/agent-execution-protocol.md -->

# Agent Execution Protocol

## 1. 评审基线原则

本包是规划基线，不是最终开发事实。

每个开发分支开始时，Agent 必须在仓库提交实际执行 Spec：

```text
docs/specs/real-production-closure/implementation/
  baseline-lock.json
  implementation-spec.md
  implementation-spec.json
  spec-deviation-log.md
  test-evidence.md
```

后续 PR 评审必须：

> 以该分支实际提交的 implementation spec 为 baseline，不能直接把本规划包中未被采用的设计当成缺陷。

## 2. Spec Drift

任何偏差必须记录：

| 字段 | 内容 |
|---|---|
| task_id | 原任务 |
| planned | 原设计 |
| actual | 实际设计 |
| reason | 原因 |
| impact | 影响 |
| compatibility | 兼容性 |
| tests | 证明 |
| reviewer_status | accepted / rejected / pending |

未记录的关键偏差视为缺陷。

## 3. 单任务执行规则

1. 只实现当前 task。
2. 先读依赖 task 的结果。
3. 不以“顺手优化”为由扩范围。
4. 新 artifact 必须有 schema version。
5. 坏输入不得覆盖好状态。
6. Production 不允许 fixture fallback。
7. 关键写操作必须原子化。
8. 所有外部结果必须做 run/session/path validation。
9. 不能声称运行了未实际运行的测试。
10. 完成后输出标准交付报告。

## 4. 并行规则

允许并行：

- A2 与 A4，在 A1 contract 冻结后；
- B1 与 B3 的框架；
- C1 与 C3。

不允许并行修改同一状态语义：

- Generation status；
- Final readiness；
- Release activation。

## 5. PR 规则

每个 PR 包含：

- Task ID；
- actual spec；
- changed files；
- migration；
- tests；
- evidence；
- known limits；
- deviation log；
- rollback。

## 6. Codex 核验标记

涉及以下事实必须写“需要 Codex 核验”直至实际执行：

- 当前 HEAD；
- 测试数；
- 命令可运行；
- dependency installed；
- clean install；
-真实 benchmark；
- 本机 suite status；
- release artifact。


---

<!-- SOURCE: agents/codex-prompts.md -->

# Codex Execution Prompts

## 1. Master Integrator

```text
你正在开发 MainQuestAI/Deck-Master。

Baseline:
- origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177
- 先核验，不要假定本地 HEAD 一致。

先阅读：
- README.md
- 00-master-spec.md
- 01-baseline-gap-register.md
- 02-cross-repo-contracts.md
- agents/agent-execution-protocol.md

第一步只执行 A0。
在仓库提交实际 implementation spec、baseline lock、capability lock 草案和 deviation log。
不要在 A0 实现业务功能。

完成后输出：
1. 核验事实；
2. 当前 Gap；
3. 实际 Stack 拆分；
4. 分支 implementation spec 路径；
5. 测试基线；
6. 需要用户决定的阻断项。
```

## 2. Stack A

```text
实现 Stack A：v0.9.14 Real Production Runtime。

必须先读取 A0 实际 implementation spec。
按 A1 → A2/A3/A4 → A5 顺序执行。
核心目标：Production 不再生成 placeholder；真实 Agent 结果可回写；PPT Master 产出真实 HTML/PDF/PNG/PPTX。

硬约束：
- Deck Master 零内置 LLM Provider。
- Run 是唯一状态源。
- completed 必须有有效 artifact。
- fixture 只允许 fixture/dev。
- 所有偏差写 spec-deviation-log.md。

每个 Task 独立提交。
完成后运行全量测试和一条真实非 fixture smoke。
```

## 3. Stack B

```text
实现 Stack B：v0.9.15 Artifact Truth & Final Readiness。

先确认 Stack A 已完成并合并。
按 B1 → B2/B3 → B4 → B5 执行。

硬目标：
- fake extension、corrupt package、checksum mismatch、stale artifact 全部阻断；
- parse failure 必须 P0；
- final_readiness.json 是唯一最终结论；
- Export、Review Workspace、Benchmark 不得复制 readiness 逻辑；
- Production placeholder 回归由 CI 阻断。
```

## 4. Stack C

```text
实现 Stack C：v0.9.16 Release, Benchmark & RC。

按 C1/C3 → C2/C4 → C5 执行。

硬目标：
- release tree 自包含；
- 删除或移动原 repo 后 CLI 仍可用；
- clean install、upgrade、rollback；
- ≥3 real cases；
- RC report 缺任一证据必须 blocked；
- 只提交脱敏 benchmark metadata 和 metrics。
```

## 5. 单任务模板

```text
你正在执行 {TASK_ID}。

请读取：
- 00-master-spec.md
- 对应 Stack Spec
- tasks/{TASK_FILE}
- 分支内实际 implementation spec
- spec-deviation-log.md

只实现本 Task。
不要扩展到后续 Task。
先写出：
1. 当前事实；
2. 计划修改文件；
3. 兼容策略；
4. 测试矩阵。

实现后：
- 运行 Task tests；
- 运行相关 regression；
- git diff --check；
- 更新 test-evidence.md；
- 更新 deviation log；
- 输出真实结果和未完成项。
```


---

<!-- SOURCE: agents/review-protocol.md -->

# Development Review Protocol

## 1. 评审顺序

1. 确认实际 implementation spec。
2. 确认 baseline SHA。
3. 确认 Task 范围。
4. 检查 P0 业务目标。
5. 检查 contract / migration。
6. 检查测试证据。
7. 检查 spec deviation。
8. 再检查代码质量和 P2 优化。

## 2. P0 定义

以下任一项为 P0：

- Production 可产生 placeholder；
- invalid artifact 可被标记 ready；
- parse failure 被吞；
- run/session mismatch 未阻断；
- stale artifact 可 export；
- required artifact 缺失可 export；
- release 依赖源码仓但文档声称独立安装；
- final readiness 和 export 结论不一致；
- real benchmark 使用 fixture 充数；
- 用户可见产物或状态存在误导。

## 3. 无法确认

以下不能直接判缺陷，必须要求证据：

- 本机是否安装 Playwright / LibreOffice；
- 当前测试是否通过；
- 真实案例是否达标；
- release 在 clean HOME 是否通过；
- 外部 Agent 是否真实生成高质量页面。

## 4. 评审输出

```text
结论
P0 阻断项
P1 必修项
待核实项
可优化项
Spec deviation 裁决
测试证据裁决
是否允许进入下一 Stack
```

## 5. Merge Gate

- Stack A：真实 non-fixture smoke。
- Stack B：完整 failure matrix。
- Stack C：clean install + real benchmark + RC checklist。
