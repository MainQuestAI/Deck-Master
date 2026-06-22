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
