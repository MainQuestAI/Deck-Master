# Deck Master v0.9 Agentic Integration & Review Maturity Spec

日期：2026-06-12  
状态：开发主控 Spec v0.1  
当前落库路径：`docs/deck-master-v0.9-agentic-integration-review-maturity-spec.md`  
配套任务包：`docs/deck_master_v09_spec_pack/`  
适用范围：Deck Master 开源版 v0.9.x 到 v1.0.0 RC 前的连续开发  
第一运行环境：Codex-first 本地 Agent 工作流  
低优先级兼容：Claude Code、Hermes、其他本地 / 桌面级通用 Agent  
核心定位：Agent-facing Solution Deck Run OS

---

## 0. Executive Summary

Deck Master v0.9 的目标是收敛开源版边界：避免继续横向扩展完整商业 SaaS，也避免内置 LLM、Agent Runtime、资料解析、PPT 生成和团队协作平台。

v0.9 的目标是把 Deck Master 从“功能齐全的本地 Run OS”提升为：

> **Codex-first、Skill-driven、外部 Agent 可协同、Companion Tools 可交接、Review Cockpit 可决策的专业 Solution Deck Run OS。**

Deck Master 开源版负责：

- 维护 Deck Workspace。
- 管理一次 Deck run 的状态、事件、恢复和 artifacts。
- 定义 Codex / Claude Code / Hermes 可执行的 Skill、Playbook、Task、Result Schema。
- 接收外部 Agent 生成的 Context Pack、Narrative Advice、External Quality Review。
- 与 PPT Library、PPT Deck Pro Max、PPT Master 通过 CLI contract 交接。
- 将所有外部产物纳入 Claim-Evidence Graph、Quality Gate、Review Cockpit、Export 和 Workspace Learning。
- 提供 localhost Review Cockpit，使用户完成页面审查、证据审查、来源审查、质量阻断处理和导出判断。

Deck Master 开源版不负责：

- 不内置任何 LLM Provider。
- 不配置 OpenAI / Claude / Gemini API Key。
- 不自建 Agent Runtime。
- 不直接解析所有 PDF / Excel / Screenshot / PPT / Web 等资料格式。
- 不重做 PPT Library 的历史页解析与检索。
- 不重做 PPT Deck Pro Max / PPT Master 的页面生成和渲染。
- 不在 v1.0 前做商业团队协作平台。
- 不在当前阶段做完整 benchmark 系统。

v1.0.0 的正式收口标志是：

> **Agentic integration 稳定 + Review Cockpit 可用 + PPT Library / PPT Deck Pro Max / PPT Master UAT 通过 + benchmark 跑出真实项目数据，验证从约 12 小时到约 2 小时可审查草案的目标。**

---

## 1. 背景与当前状态

### 1.1 已完成基线

当前 Deck Master 已完成 P2-P5 runtime implementation，主链路已具备：

- Workspace Foundation。
- Typed Events。
- Next Step Resolver。
- Review Status Migration。
- Export Quality Blocking。
- Schema Helper。
- Context Manifest / Conversation Session / Deck Brief / Claim Map。
- Consulting Judgments。
- Claim-Evidence Graph。
- Narrative Planner v2。
- Page Tasks 分层结构。
- PPT Library selection / fixture fallback。
- Sourcing Decision v1 / v2。
- Generation Task Package。
- Preview Manifest。
- Draft / Draft v2 / Evidence / Context Conflict / Confidentiality / Brand / Render / Delivery Gate。
- Override Governance。
- Delivery Validation / Delivery Outcome。
- Experimental Team / Opportunity / Approval / Dashboard / Solution Package。
- Localhost Preview / Review UI 的基础能力。

当前代码已经形成“专业 Deck Run OS Alpha+ / Early Beta”的结构，但仍需要把开源版的边界进一步收敛为 Agent-facing runtime。

### 1.2 这份 Spec 的作用

本 Spec 用于指导下一轮连续开发：

- 不再以 P2 / P3 / P4 / P5 横向阶段推进。
- 改为围绕 v0.9 的 Agentic Integration 和 Review Maturity 推进。
- 明确 Deck Master owns / External Agent owns / Companion Tool owns / Commercial Edition owns。
- 形成可交给 Codex / Claude Code / Hermes 等 Agent 执行的任务包。
- 为 v1.0.0 benchmark release gate 做轻量铺垫，但不提前做重型 benchmark。

---

## 2. 产品边界与责任分工

### 2.1 系统分层

| 层级 | 职责 | 开源版 Deck Master 是否负责 |
|---|---|---|
| 通用 Agent Runtime | 多轮推理、LLM 调用、资料理解、跨工具调度 | 不负责 |
| Agent Skill / Playbook | 告诉 Codex / Claude Code 如何调用 Deck Master 和伴随工具 | 负责 |
| Deck Master Runtime | Workspace、Run、Artifacts、Events、Next Step、Quality Gate、Export | 负责 |
| Review Cockpit | 用户完成页面、来源、证据、质量和导出判断 | 负责 |
| PPT Library | 历史 PPT 解析、截图、索引、检索、候选返回 | 不重复做，只定义 contract |
| PPT Deck Pro Max / PPT Master | 页面生成、PPT 组装、渲染 | 不重复做，只定义 handoff / handback |
| 商业团队版 | 多人协作、权限、远程 workspace、组织级 dashboard | v1.0 前不负责 |

### 2.2 Deck Master Owns

Deck Master 开源版必须负责：

1. **Workspace Contract**
   - `workspace_manifest.json`
   - `visual-system/`
   - `structure-assets/`
   - `quality/`
   - `assets/`
   - `learning/`
   - `skills/` 安装入口

2. **Run Contract**
   - `request.json`
   - `events.jsonl`
   - `context_manifest.json`
   - `deck_brief.json`
   - `claim_map.json`
   - `claim_evidence_graph.json`
   - `narrative_plan.json`
   - `page_tasks.json`
   - `sourcing_plan.json`
   - `generation_tasks/`
   - `preview_manifest.json`
   - `quality_reports/`
   - `approved_queue.json`

3. **Agent Handoff / Handback**
   - Context Pack import。
   - Narrative Advice task/result。
   - External Quality Review task/result。
   - Generation result import。
   - Workspace Learning Pack export。

4. **Quality & Review**
   - Quality report schema。
   - External findings import。
   - Export blocking。
   - Override governance。
   - Review Cockpit 2.0。

5. **Skill Packaging**
   - Codex-first skill。
   - 可软链接到 Codex / Claude Code / Hermes skill 目录。
   - Playbooks / schemas / prompt templates / task templates。

### 2.3 External Agent Owns

外部 Agent 负责：

- 读取复杂资料。
- 使用 LLM 进行业务推理。
- 生成 Context Pack。
- 生成 Narrative Advice。
- 生成 External Quality Review。
- 调用 PPT Library / PPT Deck Pro Max / PPT Master。
- 根据 Deck Master `next-step` 执行下一步。
- 按 Skill Playbook 修复 run。

### 2.4 Companion Tool Owns

| 工具 | 职责 |
|---|---|
| PPT Library | PPT 资产解析、截图、索引、语义检索、候选页返回 |
| PPT Deck Pro Max | 根据 generation task 生成页面或页面项目 |
| PPT Master | 渲染、组装、导出、PPTX 级产物处理 |
| Codex | 主 Agent runtime 和开发 / 调度 / 推理入口 |
| Claude Code / Hermes | 低优先级兼容的外部 review / generation / repair agent |

---

## 3. v0.9 总体目标与非目标

### 3.1 总体目标

Deck Master v0.9 要达成以下状态：

> 用户在 Codex 中通过 Deck Master Skill 发起一次客户 Solution Deck run。Codex 负责整理资料、生成 context pack、请求 narrative advice、调用 PPT Library 和 PPT Deck Pro Max；Deck Master 负责接收结构化产物、规划和审查 Deck run、展示 Review Cockpit、执行 Quality Gate 和 Export blocking，最终形成可审查、可追踪、可继续打磨的 Solution Deck 草案。

### 3.2 v0.9 必须实现

- Skill Packaging & Installation。
- Codex-first Playbook。
- Agent Context Pack Contract。
- Narrative Advisory Task / Result Contract。
- External Quality Review Contract。
- Build Tool Handoff / Handback Contract。
- Review Cockpit 2.0。
- Workspace Learning Pack。
- Companion Tool UAT Contracts。
- Lightweight Metrics Hooks。

### 3.3 v0.9 不做

- 不内置 LLM Provider。
- 不做资料格式解析器。
- 不做 PPT 生成引擎。
- 不做 PPT Library 替代品。
- 不做完整 benchmark system。
- 不做团队协作商业版。
- 不做 SaaS / remote workspace。
- 不做复杂 CI / release platform。
- 不做多 Agent 调度平台。

---

## 4. 开发包总览

| 包 | 名称 | 优先级 | 核心产物 |
|---|---|---:|---|
| A | Skill Packaging & Installation | P0 | `skills/deck-master/`, `install-skill`, symlink |
| B | Agent Context Pack Contract | P0 | `context_pack.schema.json`, `import-context-pack` |
| C | Narrative Advisory Contract | P0 | `prepare-narrative-advice`, `import/apply-narrative-advice` |
| D | External Quality Review Contract | P0 | `prepare-quality-review`, `import-quality-review` |
| E | Build Tool Handoff / Handback | P0 | `prepare-generation-handoff`, `import-generation-result` |
| F | Review Cockpit 2.0 | P0 | Deck readiness, claim matrix, next actions, decision workbench |
| G | Workspace Learning Pack | P1 | `workspace_learning_pack.json`, `agent_context_summary.md` |
| H | Companion Tool UAT Contracts | P1 | validators + UAT docs for PPT Library / Deck Pro Max / PPT Master |
| I | Lightweight Metrics Hooks | P2 | `run_metrics.json`, event-derived metrics |

---

# Package A：Skill Packaging & Installation

## A.1 目标

让 Deck Master 的能力能够被 Codex / Claude Code / Hermes 等外部 Agent 发现、读取和调用。

Skill 放在本仓库，安装时通过软链接挂到目标 Agent 的 skill 目录。此模式方便统一升级和本地管理，避免每个 Agent 维护一份复制内容。

## A.2 目录结构

新增：

```text
skills/
  deck-master/
    SKILL.md
    AGENTS.md
    README.md
    playbooks/
      codex-run-solution-deck.md
      codex-review-and-repair.md
      ppt-library-handoff.md
      ppt-deck-pro-max-handoff.md
      external-quality-review.md
      workspace-learning.md
    schemas/
      context_pack.schema.json
      narrative_advice_task.schema.json
      narrative_advice_result.schema.json
      external_quality_review_task.schema.json
      external_quality_review_result.schema.json
      generation_result.schema.json
      workspace_learning_pack.schema.json
    prompts/
      narrative_advisor.prompt.md
      quality_reviewer.prompt.md
      source_decision_reviewer.prompt.md
      deck_repair.prompt.md
```

## A.3 CLI

新增命令：

```bash
python3 scripts/deck_master.py install-skill \
  --target codex \
  --agent-skill-dir ~/.codex/skills
```

```bash
python3 scripts/deck_master.py validate-skill \
  --target codex \
  --agent-skill-dir ~/.codex/skills
```

```bash
python3 scripts/deck_master.py uninstall-skill \
  --target codex \
  --agent-skill-dir ~/.codex/skills
```

推荐支持 target：

```text
codex
claude-code
hermes
custom
```

默认不强写死真实目录，CLI 参数必须支持显式传入。

可选配置文件：

```text
~/.deck-master/config.json
```

```json
{
  "agent_skill_dirs": {
    "codex": "~/.codex/skills",
    "claude-code": "~/.claude/skills",
    "hermes": "~/.hermes/skills"
  }
}
```

## A.4 行为规则

- 默认使用 symlink，不复制文件。
- 目标目录不存在时创建。
- 已存在同名 symlink 且指向当前 repo 时视为 installed。
- 已存在同名真实目录时拒绝覆盖，除非 `--force`。
- `--force` 只允许替换 symlink，不默认删除真实目录。
- 所有 install / uninstall / validate 操作写 typed event 到 workspace 或全局 install log。
- 不依赖特定 Agent 的私有 API。

## A.5 验收标准

- `skills/deck-master/SKILL.md` 存在。
- `install-skill --target codex --agent-skill-dir <tmp>` 创建软链接。
- 重复安装幂等。
- `validate-skill` 能检测 symlink 是否有效。
- target 不支持时报错清晰。
- `uninstall-skill` 只删除由 Deck Master 创建的 symlink。
- 测试覆盖 symlink、force、invalid target、existing real dir。

---

# Package B：Agent Context Pack Contract

## B.1 目标

Deck Master 避免内置完整资料解析器，核心职责是定义外部 Agent 到 Deck Master 的上下文交付协议。

外部 Agent 负责读取 PDF、PPT、Excel、截图、网页、会议转写、客户材料、竞品资料等，并输出标准 Context Pack。Deck Master 负责 import、validate、merge、event logging，并让其进入 run artifacts 和 Claim-Evidence Graph。

## B.1.1 与现有 connector import 的关系

当前仓库已有 `deck_connector_import.v1`，用于把外部系统导出的 source manifest 转成 `deck_context_manifest.v1`。v0.9 的 `deck_context_pack.v1` 是新的 Agent handoff 主协议，重点覆盖 evidence candidates、publication status、sensitivity、run merge 和 Quality Gate / Review Cockpit 可见性。

实施规则：

- 保留现有 `connector import` 命令，不能破坏已有测试和调用方式。
- `deck_context_pack.v1` 新增独立 import 路径，不复用 `deck_connector_import.v1` 作为 schema。
- 可以复用 connector import 中的本地文件、敏感来源和校验经验。
- 如需互通，新增 adapter 测试，明确字段映射和丢失字段。
- `context_manifest.json` 最终必须保留 Context Pack 的 evidence candidates、sensitivity 和 publication status。

## B.2 新增 Schema

文件：

```text
skills/deck-master/schemas/context_pack.schema.json
```

推荐对象：

```json
{
  "schema_version": "deck_context_pack.v1",
  "run_id": "retail-demo",
  "created_by": "codex",
  "created_at": "2026-06-12T00:00:00Z",
  "sources": [
    {
      "source_id": "src_customer_pdf_001",
      "source_type": "customer_material",
      "origin_type": "pdf",
      "origin_path": "/path/to/customer.pdf",
      "title": "客户现状材料",
      "summary": "客户当前多渠道会员数据分散，缺少统一运营闭环。",
      "evidence_candidates": [
        {
          "evidence_id": "ev_001",
          "evidence_type": "customer_material",
          "claim_hint": "客户缺少统一会员运营闭环",
          "quote_or_excerpt": "会员数据分散在不同渠道。",
          "location": "page 12",
          "publication_status": "safe_to_use",
          "sensitivity": "normal"
        }
      ],
      "sensitivity": "normal"
    }
  ],
  "global_constraints": [
    "客户名称需脱敏后再用于 client export。"
  ]
}
```

## B.3 CLI

新增：

```bash
python3 scripts/deck_master.py import-context-pack \
  --run-id <run_id> \
  --runs-dir runs \
  --input context_pack.json
```

新增：

```bash
python3 scripts/deck_master.py create-run-from-context-pack \
  --workspace <workspace> \
  --input context_pack.json \
  --run-id <run_id> \
  --industry retail \
  --audience client
```

## B.4 Import 规则

- `schema_version` 必须为 `deck_context_pack.v1`。
- `sources[].source_id` 必须唯一。
- `evidence_candidates[].evidence_id` 在 source 内唯一。
- `publication_status` 只允许：
  - `safe_to_use`
  - `internal_only`
  - `needs_redaction`
  - `unknown`
- `sensitivity` 只允许：
  - `normal`
  - `sensitive`
  - `high`
- high sensitivity source 默认不能进入 client export。
- bad JSON 不覆盖已有 `context_manifest.json`。
- import 成功后写 typed event。
- import 后应触发或提示重建 `claim_evidence_graph.json`。

## B.5 输出

Deck Master 生成或更新：

```text
context_manifest.json
context_packs/<pack_id>.json
events.jsonl
```

`context_manifest.json` 中每个 source 应保留：

- source_id
- source_type
- origin_type
- origin_path
- title
- summary
- evidence_candidates
- sensitivity
- publication_status 聚合信号

## B.6 验收标准

- Codex 生成的 context pack 可被 import。
- import 后 `context_manifest.json` 中可见 evidence candidates。
- `build-claim-graph` 能读取 imported evidence。
- high sensitivity 输入会被标记，不能静默进入 client export。
- bad JSON / invalid schema 不覆盖旧 artifact。
- 重复 import 同一个 source_id 时可选择 merge 或 reject，行为必须确定。
- 测试覆盖 valid pack、invalid schema、duplicate source、high sensitivity、bad JSON。

---

# Package C：Narrative Advisory Task / Result Contract

## C.1 目标

当前 `consulting_judgments.json` 由规则驱动生成，适合 deterministic baseline，但不足以承担专家级叙事判断。v0.9 保持零 LLM Provider 依赖，由 Codex 或其他外部 Agent 基于 Deck run artifacts 生成 Narrative Advice，再由 Deck Master 导入并应用。

## C.2 新增命令

```bash
python3 scripts/deck_master.py prepare-narrative-advice \
  --run-id <run_id> \
  --runs-dir runs
```

```bash
python3 scripts/deck_master.py import-narrative-advice \
  --run-id <run_id> \
  --input narrative_advice.json
```

```bash
python3 scripts/deck_master.py apply-narrative-advice \
  --run-id <run_id> \
  --input advisor_results/narrative_advice.json
```

## C.3 生成任务 Artifact

```text
advisor_tasks/narrative_advice_task.json
```

结构：

```json
{
  "schema_version": "deck_narrative_advice_task.v1",
  "run_id": "retail-demo",
  "task_id": "narrative_advice_001",
  "created_at": "2026-06-12T00:00:00Z",
  "inputs": {
    "request": "request.json",
    "deck_brief": "deck_brief.json",
    "claim_map": "claim_map.json",
    "claim_evidence_graph": "claim_evidence_graph.json",
    "page_tasks": "page_tasks.json",
    "quality_reports": "quality_reports/"
  },
  "instructions": [
    "识别客户真实业务矛盾。",
    "判断当前 Deck 主线是否成立。",
    "补充或改写 core thesis。",
    "提出 objection handling。",
    "指出哪些页面缺证据。",
    "建议哪些页面应该改为 appendix、generate、reuse 或补证据。"
  ],
  "output_schema": "deck_narrative_advice.v1"
}
```

## C.4 Agent 输出 Artifact

```text
advisor_results/narrative_advice.json
```

结构：

```json
{
  "schema_version": "deck_narrative_advice.v1",
  "run_id": "retail-demo",
  "advisor": "codex",
  "created_at": "2026-06-12T00:00:00Z",
  "core_thesis_rewrite": "客户当前缺少跨渠道运营闭环，内容工具只能解决局部问题。",
  "business_tension": "业务增长依赖多渠道触达，但运营数据和内容生产流程仍然分散。",
  "audience_strategy": {
    "primary_audience": "client",
    "decision_goal": "认可建设统一运营中台的必要性，并进入方案细化阶段。",
    "tone": "正式、可信、方案导向"
  },
  "objection_map": [
    {
      "objection": "客户可能认为现有系统已经够用。",
      "response_strategy": "用数据割裂、触达效率和复购提升证明统一运营中台的必要性。",
      "evidence_needed": ["现有渠道数据割裂截图", "会员重复识别问题", "运营效率指标"]
    }
  ],
  "page_recommendations": [
    {
      "beat_id": "beat_004",
      "action": "strengthen_claim",
      "reason": "页面只讲能力，没有证明业务价值。",
      "suggested_core_claim": "库存可视化的关键价值在于提升履约效率，不能停留在看板展示。",
      "evidence_needed": ["履约时效", "缺货率", "库存准确率"]
    }
  ],
  "deck_level_risks": [
    {
      "risk_id": "risk_001",
      "severity": "P1",
      "message": "ROI 页面缺少客户指标，建议降级为价值假设或补证据。"
    }
  ]
}
```

## C.5 Apply 规则

`apply-narrative-advice` 不应直接不可逆覆盖旧 artifacts。推荐策略：

1. 生成 diff：
   ```text
   advisor_results/narrative_advice_diff.json
   ```
2. 可选参数：
   ```bash
   --apply core-thesis,page-recommendations,risks
   ```
3. 默认只更新：
   - `page_tasks[].planning.decision_intent`
   - `page_tasks[].planning.core_claim`（仅在 action 为 strengthen_claim 且有 suggested_core_claim）
   - `page_tasks[].planning.evidence_need`
   - `claim_evidence_graph.gaps`
   - `quality_reports/external_narrative_gate.json`
4. 所有应用写 typed events。
5. 旧值保存在 diff 中。
6. 支持 `--dry-run`。

## C.6 验收标准

- 能生成 `narrative_advice_task.json`。
- Codex 可直接根据 task 执行。
- 能 import valid `narrative_advice.json`。
- invalid result 被拒绝，不覆盖旧数据。
- `apply-narrative-advice --dry-run` 只生成 diff。
- 应用后 page task 有可见变化。
- Review Cockpit 能展示 narrative advice。
- Quality Gate 能读取 deck-level risks。
- 测试覆盖 valid import、invalid schema、dry-run、apply、event logging。

---

# Package D：External Quality Review Contract

## D.1 目标

语义、视觉、客户可读性等高阶审查不由 Deck Master 内置 LLM 执行。Deck Master 生成 review task，外部 Agent 执行审查，并把 findings 按标准 schema 写回。Deck Master 负责导入为 Quality Gate report，并参与 Review Cockpit 与 Export Blocking。

## D.2 新增命令

```bash
python3 scripts/deck_master.py prepare-quality-review \
  --run-id <run_id> \
  --scope semantic,visual,evidence,client-readiness
```

```bash
python3 scripts/deck_master.py import-quality-review \
  --run-id <run_id> \
  --input external_quality_review.json
```

## D.3 Review Task

```text
quality_review_tasks/semantic_review_task.json
quality_review_tasks/visual_review_task.json
quality_review_tasks/client_readiness_review_task.json
```

Task schema：

```json
{
  "schema_version": "deck_external_quality_review_task.v1",
  "run_id": "retail-demo",
  "task_id": "semantic_review_001",
  "scope": "semantic",
  "inputs": {
    "deck_brief": "deck_brief.json",
    "claim_evidence_graph": "claim_evidence_graph.json",
    "page_tasks": "page_tasks.json",
    "preview_manifest": "preview_manifest.json",
    "quality_reports": "quality_reports/"
  },
  "review_dimensions": [
    "claim_evidence_alignment",
    "consulting_style_expression",
    "client_readability",
    "page_job_clarity",
    "decision_readiness"
  ],
  "output_schema": "deck_external_quality_review.v1"
}
```

## D.4 Review Result

```json
{
  "schema_version": "deck_external_quality_review.v1",
  "run_id": "retail-demo",
  "reviewer": "codex",
  "scope": "semantic",
  "created_at": "2026-06-12T00:00:00Z",
  "summary": {
    "status": "rework_required",
    "blocks_delivery": true,
    "p0_count": 0,
    "p1_count": 2,
    "p2_count": 4
  },
  "findings": [
    {
      "finding_id": "ext_semantic_001",
      "severity": "P1",
      "page_id": "beat_004",
      "dimension": "claim_evidence_alignment",
      "message": "页面标题提出库存可视化价值，但正文没有给出履约效率证据。",
      "repair_instruction": "补充履约时效、缺货率、库存准确率等指标，或降低页面主张。",
      "refs": ["page_tasks.json#beat_004", "claim_evidence_graph.json#claim_02"]
    }
  ]
}
```

## D.5 Import 规则

导入后生成：

```text
quality_reports/external_semantic_gate.json
quality_reports/external_visual_gate.json
quality_reports/external_client_readiness_gate.json
```

规则：

- P0 / P1 finding 参与 export blocking。
- `scope` 决定 gate 文件名。
- reviewer 必须记录。
- 同一 reviewer 同一 scope 可覆盖上一版，但旧版备份到 `quality_reports/archive/`。
- 多 reviewer 可并存：
  - `external_semantic_codex_gate.json`
  - `external_semantic_claude_code_gate.json`
- 默认汇总到 Review Cockpit。
- bad result 不覆盖旧报告。

## D.6 验收标准

- 能生成 review task。
- 能 import external review result。
- P0/P1 finding 阻断 client export。
- Review Cockpit 显示 reviewer、scope、finding。
- override 仍需逐 finding target_id。
- 多 reviewer 不互相覆盖，除非明确指定 `--replace`.
- 测试覆盖 semantic、visual、invalid result、multi reviewer、export blocking。

---

# Package E：Build Tool Handoff / Handback Contract

## E.1 目标

Deck Master 不做页面生成引擎。v0.9 要强化与 PPT Deck Pro Max / PPT Master 的 task handoff 和 artifact handback，使 generate / adapt 页面可以由外部工具生产并回写到 Deck run。

## E.2 新增命令

```bash
python3 scripts/deck_master.py prepare-generation-handoff \
  --run-id <run_id>
```

```bash
python3 scripts/deck_master.py import-generation-result \
  --run-id <run_id> \
  --input generation_result.json
```

```bash
python3 scripts/deck_master.py refresh-preview-from-generation \
  --run-id <run_id>
```

可选：

```bash
python3 scripts/deck_master.py validate-generation-result \
  --input generation_result.json
```

## E.3 Generation Task Handoff

现有：

```text
generation_tasks/index.json
generation_tasks/<task_id>.json
```

需要增强字段：

```json
{
  "schema_version": "deck_generation_task.v1",
  "task_id": "generation_004_beat_004",
  "run_id": "retail-demo",
  "beat_id": "beat_004",
  "page_title": "库存可视化目标架构",
  "source_decision": "generate",
  "generation_brief": "...",
  "reference_slide": null,
  "claim_ids": ["claim_02"],
  "evidence_refs": ["evidence_003"],
  "style_constraints": "...",
  "workspace_refs": [
    "visual-system/spec_lock.md",
    "structure-assets/page_archetypes.md#architecture"
  ],
  "quality_requirements": [
    "页面必须有主观点",
    "必须说明证据如何支撑判断"
  ],
  "expected_outputs": [
    "preview_path",
    "artifact_path",
    "generation_notes"
  ],
  "status": "pending"
}
```

## E.4 Generation Result

```json
{
  "schema_version": "deck_generation_result.v1",
  "run_id": "retail-demo",
  "tool": "ppt-deck-pro-max",
  "task_id": "generation_004_beat_004",
  "beat_id": "beat_004",
  "status": "completed",
  "artifact_type": "pptx_slide",
  "artifact_path": "generated_assets/beat_004/slide.pptx",
  "preview_path": "generated_assets/beat_004/preview.png",
  "notes": "Generated using architecture archetype.",
  "errors": []
}
```

Failure result：

```json
{
  "schema_version": "deck_generation_result.v1",
  "run_id": "retail-demo",
  "tool": "ppt-deck-pro-max",
  "task_id": "generation_004_beat_004",
  "beat_id": "beat_004",
  "status": "failed",
  "artifact_type": "",
  "artifact_path": "",
  "preview_path": "",
  "notes": "",
  "errors": [
    {
      "code": "missing_reference_asset",
      "message": "Reference slide screenshot was not found."
    }
  ]
}
```

## E.5 Import 行为

- completed：
  - 写入 `generation_results/<task_id>.json`
  - 更新 generation task status
  - 将 preview_path 写入 `preview_manifest.json` 对应页面
  - source_type 设为 `generated`
  - 写 event
- failed：
  - 写入 result
  - 更新 generation task status = failed
  - Review Cockpit 显示失败原因
  - 不覆盖旧 preview
- partial：
  - 允许 artifact_path 有值但 preview_path 缺失
  - 标记 `preview_missing`
- locked page：
  - 如果页面 `locked == true`，默认不允许覆盖，除非 `--force`
- bad result：
  - 报错，不覆盖旧状态

## E.6 验收标准

- 可生成 handoff task。
- 可导入 completed result 并刷新 preview manifest。
- 可导入 failed result 并在 UI 显示。
- locked page 不被覆盖。
- bad result 不覆盖旧数据。
- Agent playbook 说明如何调用 PPT Deck Pro Max。
- 测试覆盖 completed、failed、partial、locked、bad JSON、preview refresh。

---

# Package F：Review Cockpit 2.0

## F.1 目标

Review Cockpit 是 Deck Master 开源版 1.0 前最核心的产品体验。v0.9 要把当前 preview UI 从“页面预览 + 基础审查”升级为“Run 级审查决策工具”。

核心问题：

> 用户打开 Cockpit 后，必须立刻知道这份 Deck 为什么还不能交付、哪些页面可以保留、哪些页面要重做、哪些证据要补、下一步最该做什么。

## F.1.1 执行分段

Review Cockpit 2.0 不能一次性作为单个大 PR 实现。v0.9 按三段推进：

- **F1 Read-only Review APIs**：新增 deck readiness、claim coverage、next actions 三类只读 API，并复用现有 quality governance / narrative / asset signals 数据。
- **F2 Page Workbench Actions**：新增 page review action API，覆盖 approve、reject、request evidence、convert to generate、lock source、add note，并保证 Quality Gate 不被绕过。
- **F3 External Result Visibility**：在 C/D/E 的结果导入稳定后，把 narrative advice、external review、generation result 显示到 Cockpit。

F1 可以和 B/C/D/E 并行设计，但 F2/F3 必须等对应协议和 import 行为落地后再实施。

## F.2 新增/增强 API

```text
GET /api/review-summary/<run_id>
GET /api/claim-coverage/<run_id>
GET /api/next-actions/<run_id>
GET /api/page/<page_id>/workbench?run_id=<run_id>
POST /api/page/<page_id>/review-action?run_id=<run_id>
POST /api/import-external-review?run_id=<run_id>
POST /api/import-generation-result?run_id=<run_id>
```

## F.3 Deck Readiness Panel

显示：

```json
{
  "run_id": "retail-demo",
  "deck_readiness": {
    "overall": "blocked",
    "narrative": "conditional_pass",
    "evidence": "blocked",
    "source": "needs_review",
    "generation": "partial",
    "quality": "blocked",
    "export": "blocked"
  },
  "counts": {
    "pages": 14,
    "approved": 5,
    "needs_review": 7,
    "rejected": 2,
    "reuse": 3,
    "adapt": 4,
    "generate": 5,
    "manual_placeholder": 2,
    "p0": 0,
    "p1": 3,
    "p2": 8
  }
}
```

## F.4 Claim Coverage Matrix

API 输出：

```json
{
  "claims": [
    {
      "claim_id": "claim_01",
      "statement": "客户需要统一会员运营闭环。",
      "pages": ["beat_003", "beat_005"],
      "evidence": ["evidence_001", "evidence_003"],
      "status": "covered"
    },
    {
      "claim_id": "claim_02",
      "statement": "ROI 能通过复购提升体现。",
      "pages": ["beat_009"],
      "evidence": [],
      "status": "evidence_gap"
    }
  ]
}
```

状态：

- `covered`
- `uncovered`
- `evidence_gap`
- `review_required`
- `blocked`

## F.5 Next 5 Actions

系统自动聚合：

- Missing Draft Gate。
- P0 / P1 findings。
- Evidence gaps。
- Manual placeholders。
- Generation failed。
- Approved pages blocked by quality。
- High context conflict candidates。
- Claim uncovered。
- No preview asset。
- External review P1 findings。

输出：

```json
{
  "actions": [
    {
      "priority": 1,
      "action_type": "fix_evidence_gap",
      "target": "beat_009",
      "message": "ROI 页面缺少客户指标证据。",
      "suggested_command": "python3 scripts/deck_master.py prepare-narrative-advice --run-id retail-demo",
      "refs": ["claim_evidence_graph.json#claim_02"]
    }
  ]
}
```

## F.6 Page Decision Workbench

支持操作：

| 操作 | 行为 |
|---|---|
| approve | 设置 review_status=approved |
| reject | 设置 review_status=rejected |
| request_evidence | 创建 evidence request finding |
| convert_to_generate | action_intent=generate，并刷新 generation task |
| replace_candidate | 从 alternatives 中选择新候选 |
| move_to_appendix | role/section 标记为 appendix |
| lock_source | locked=true，后续自动决策不可覆盖 |
| create_override | 针对 finding_id 创建 P1 override |
| rerun_generation | 生成/标记 generation rerun task |
| add_note | 写审查备注 |

所有操作必须写 typed event。

## F.7 UI 要求

- 桌面浏览器优先。
- 左侧：页面列表 + 状态筛选。
- 中央：页面预览。
- 右侧：Page Workbench。
- 顶部：Deck Readiness Panel。
- 下方或侧栏：Claim Coverage / Next Actions / Quality Findings。
- 支持中文界面为主，英文字段保留。
- 不需要做完整商业工作台。
- 不需要多人协作 UI。

## F.8 验收标准

- 用户能一眼看到 deck 是否 ready。
- 用户能看到 claim coverage。
- 用户能看到 next 5 actions。
- 用户能对页面执行主要 review actions。
- 所有动作写 events。
- Review 操作不绕过 Quality Gate。
- External Review findings 可见。
- Generation status 可见。
- 测试覆盖 API、summary、claim coverage、next actions、review action event。

---

# Package G：Workspace Learning Pack

## G.1 目标

Feedback 在 v0.9 只聚合为外部 Agent 下次 run 可以读取的 Workspace Learning Pack，暂不建设复杂商业 BI。

## G.2 新增命令

```bash
python3 scripts/deck_master.py build-learning-pack \
  --workspace <workspace>
```

```bash
python3 scripts/deck_master.py show-learning-pack \
  --workspace <workspace>
```

## G.3 输出

```text
workspace/learning/workspace_learning_pack.json
workspace/learning/agent_context_summary.md
```

`workspace_learning_pack.json`：

```json
{
  "schema_version": "deck_workspace_learning_pack.v1",
  "workspace": "MarketingForce PPT Workshop",
  "generated_at": "2026-06-12T00:00:00Z",
  "high_value_patterns": [
    {
      "pattern_id": "pattern_001",
      "description": "问题诊断 + 目标架构 + 分阶段路线图",
      "used_in_runs": 8,
      "approval_rate": 0.82,
      "best_for": ["client_solution_deck", "retail", "digital_transformation"]
    }
  ],
  "frequent_failure_modes": [
    {
      "failure_id": "failure_001",
      "description": "ROI 页缺指标证据",
      "count": 12,
      "repair_instruction": "补业务指标或降级为价值假设。"
    }
  ],
  "strong_assets": [
    {
      "canonical_slide_id": "slide_xxx",
      "title": "全渠道库存可视化目标架构",
      "approval_rate": 0.9,
      "delivered_count": 4,
      "best_for": ["retail", "omnichannel", "inventory"]
    }
  ],
  "agent_guidance": [
    "在生成 ROI 页前优先检查是否有客户指标证据。",
    "架构页优先使用分层架构 archetype。"
  ]
}
```

`agent_context_summary.md`：

```markdown
# Workspace Learning Summary

## High-value patterns
- 问题诊断 + 目标架构 + 分阶段路线图：适合零售数字化转型方案，历史 approval rate 82%。

## Frequent failure modes
- ROI 页缺指标证据：建议补客户指标或降级为价值假设。

## Strong assets
- slide_xxx：全渠道库存可视化目标架构，适合 retail / omnichannel / inventory。
```

## G.4 数据来源

- `assets/asset_feedback.jsonl`
- `assets/asset_health_report.json`
- `delivery/delivery_outcome.json`
- run-level `preview_manifest.json`
- `quality_reports/`
- `approved_queue.json`
- `solution_package`（experimental 可读取但不依赖）

## G.5 Skill 集成

`skills/deck-master/playbooks/codex-run-solution-deck.md` 必须提示 Codex：

1. 如果 workspace learning pack 存在，先读取。
2. 在生成 narrative advice 前使用 learning pack。
3. 在 source decision review 中参考 strong assets。
4. 遇到 frequent failure modes 时主动提醒用户。

## G.6 验收标准

- 生成 JSON 和 Markdown 两种 learning pack。
- 空 workspace 也能生成可读空报告。
- Feedback 能聚合 approval / rejection / delivered。
- Frequent failure modes 能从 quality findings 聚合。
- Strong assets 能从 asset feedback 聚合。
- Codex playbook 引用 learning pack。
- 测试覆盖 empty workspace、feedback aggregation、quality finding aggregation、markdown output。

---

# Package H：Companion Tool UAT Contracts

## H.1 目标

Deck Master 不重做 PPT Library / PPT Deck Pro Max / PPT Master。v0.9 需要定义 contract validator 和 UAT 文档，确保这些 companion tools 的输出可被 Deck Master 稳定消费。

## H.2 新增命令

```bash
python3 scripts/deck_master.py validate-ppt-library-result \
  --input library_results/selection.json
```

```bash
python3 scripts/deck_master.py validate-generation-result \
  --input generation_result.json
```

```bash
python3 scripts/deck_master.py validate-render-result \
  --input render_result.json
```

## H.3 PPT Library Candidate Contract

必需字段：

```json
{
  "slide_id": "lib_slide_001",
  "canonical_slide_id": "slide_xxx",
  "title": "目标架构",
  "text_summary": "本页说明全渠道库存可视化目标架构。",
  "source_file": "/path/to/history.pptx",
  "page_number": 12,
  "screenshot_path": "/path/to/screenshot.png",
  "confidence": 0.82,
  "narrative_role": "architecture",
  "page_archetype": "target_architecture"
}
```

建议字段：

- source_project
- industry
- win_rate
- reuse_count
- approval_history
- delivery_history
- tags
- customer_context
- visual_pattern

Validator 行为：

- 必需字段缺失：error。
- screenshot 缺失：warning，不阻断。
- canonical_slide_id 缺失：warning，可 fallback。
- page_number 非数字：error。
- confidence 超出 0-1：error。
- source_file 不存在：warning。

## H.4 Generation Result Contract

同 Package E 的 `deck_generation_result.v1`。

Validator 行为：

- completed 必须有 artifact_path 或 preview_path。
- failed 必须有 errors。
- beat_id 必须存在。
- status 必须在 allowed values。
- artifact_path 不存在时 warning 或 error，取决于 status。

## H.5 Render Result Contract

```json
{
  "schema_version": "deck_render_result.v1",
  "run_id": "retail-demo",
  "tool": "ppt-master",
  "status": "completed",
  "artifact_type": "pptx",
  "artifact_path": "exports/final.pptx",
  "preview_dir": "exports/previews/",
  "page_count": 14,
  "errors": []
}
```

## H.6 UAT 文档

新增：

```text
docs/uat/ppt-library-contract-uat.md
docs/uat/ppt-deck-pro-max-contract-uat.md
docs/uat/ppt-master-contract-uat.md
```

PPT Library UAT 应验证：

- 600+ 历史 PPT 库可检索。
- 候选字段完整。
- screenshot path 可用。
- canonical id 稳定。
- source file 可追踪。
- role/archetype 可用。
- 真实 run 中 candidate 可进入 Review Cockpit。

PPT Deck Pro Max UAT 应验证：

- 可读取 generation task。
- 可输出 generation result。
- 预览图能被 Deck Master 展示。
- 失败状态能被 Deck Master 展示。
- rerun 不破坏 locked page。

PPT Master UAT 应验证：

- 可读取 approved queue。
- 可输出 render result。
- render / delivery gate 可读取 final artifact。
- page count 一致。

## H.7 验收标准

- 三类 validator 可用。
- 三份 UAT 文档存在。
- validator 输出 errors / warnings。
- bad result 不进入 run。
- UAT 文档能被 Codex Skill 引用。
- 测试覆盖 valid / invalid / warning。

---

# Package I：Lightweight Metrics Hooks

## I.1 目标

Benchmark 作为 v1.0.0 release gate，不在 v0.9 做重型系统。当前只补轻量 metrics hooks，使后续 benchmark 可以从 events 和 artifacts 中计算。

## I.2 新增命令

```bash
python3 scripts/deck_master.py summarize-run-metrics \
  --run-id <run_id>
```

## I.3 输出

```text
run_metrics.json
```

结构：

```json
{
  "schema_version": "deck_run_metrics.v1",
  "run_id": "retail-demo",
  "created_at": "...",
  "preview_ready_at": "...",
  "first_quality_gate_at": "...",
  "approved_queue_created_at": "...",
  "durations": {
    "created_to_preview_minutes": 18,
    "preview_to_first_quality_gate_minutes": 4
  },
  "counts": {
    "pages": 14,
    "approved": 5,
    "rejected": 2,
    "needs_review": 7,
    "reuse": 3,
    "adapt": 4,
    "generate": 5,
    "manual_placeholder": 2,
    "quality_findings": 12,
    "p0": 0,
    "p1": 3,
    "p2": 9
  }
}
```

## I.4 验收标准

- 可从 events 和 artifacts 计算 run metrics。
- 缺 events 时降级读取 artifacts mtime。
- 不阻断主链路。
- 为 v1.0 benchmark 保留足够字段。
- 测试覆盖 missing events、complete events、quality counts。

---

## 5. 任务拆分与 Agent 执行顺序

推荐顺序：

1. Package A：Skill Packaging。
2. Package B：Context Pack。
3. Package C：Narrative Advice。
4. Package D：External Quality Review。
5. Package E：Generation Handoff。
6. Package F1：Review Cockpit 2.0 read-only APIs。
7. Package G：Learning Pack。
8. Package H：Companion Tool UAT。
9. Package I：Metrics Hooks。
10. Package F2/F3：Page Workbench actions 与 external result visibility。

原因：

- A 是所有 Agentic workflow 的入口。
- B/C/D/E 是四类外部 Agent / tool 协议。
- F1 先提供只读审查总览，F2/F3 再承接协议结果和页面操作，形成完整用户审查体验。
- G 把反馈变成下一次 Agent 可读上下文。
- H 验证 companion tools。
- I 为 v1.0 benchmark 准备数据，不提前重型化。

---

## 6. 统一工程约束

所有 package 必须遵守：

1. 不引入 LLM provider。
2. 不引入 Agent runtime。
3. 不破坏现有 CLI。
4. 新 artifact 必须有 `schema_version`。
5. bad JSON 不得覆盖旧 artifact。
6. import / apply 操作必须写 typed event。
7. 新 CLI 必须输出 JSON。
8. 新 schema 必须有测试。
9. Review Cockpit 操作不能绕过 Quality Gate。
10. 所有 external result 必须 validate 后才能进入 run。
11. 保持本地文件系统优先。
12. Team / P5 experimental 不进入 v0.9 critical path。

### 6.1 Event 兼容规则

当前 `events.jsonl` 同时存在 legacy `append_event` 和 canonical `append_typed_event` 两类记录。v0.9 新增命令和新增 UI action 必须统一写 `append_typed_event`，已有 legacy event 保持可读、可回放、可被 metrics 降级消费。

本轮不做全量 event 迁移。`summarize-run-metrics`、Review Cockpit 和 next-step 相关逻辑必须兼容两类事件；如同一个动作同时存在 legacy 和 typed event，优先使用 typed event。

---

## 7. Agent 执行模板

### 7.1 通用任务模板

```text
你正在开发 MainQuestAI/Deck-Master。

请阅读：
- docs/deck-master-v0.9-agentic-integration-review-maturity-spec.md
- skills/deck-master/SKILL.md（如果已存在）
- 当前任务文件：docs/deck_master_v09_spec_pack/tasks/<task>.md

本次只实现 <Package X>。
不要实现其他 package。

必须遵守：
- Deck Master 开源版不内置 LLM Provider。
- 不引入 OpenAI / Claude / Gemini SDK。
- 所有外部推理由 Agent 执行，Deck Master 只定义 task/result/import/apply。
- 新 artifact 必须带 schema_version。
- import/apply 必须 validate。
- bad JSON 不能覆盖旧数据。
- 关键步骤写 typed events。
- 新 CLI 输出 JSON。
- 补测试。
- 不破坏已有 start-conversation / autoplan / quality-gate / export。

完成后输出：
- 修改文件清单。
- 新增 CLI。
- 新增 artifacts。
- 测试命令和结果。
- 已知限制。
```

### 7.2 Code Review 模板

```text
请审查本 PR 是否符合 Deck Master v0.9 Spec。

重点检查：
1. 是否引入了内置 LLM provider。
2. 是否违反 Agent-facing runtime 边界。
3. 是否破坏现有 CLI。
4. 是否所有新 artifact 都有 schema_version。
5. import/apply 是否 validate。
6. bad JSON 是否会覆盖旧数据。
7. Review Cockpit 操作是否绕过 Quality Gate。
8. 测试是否覆盖 valid / invalid / migration / compatibility。
```

---

## 8. v1.0.0 收口条件

v0.9 完成后，进入 v1.0.0 RC。RC 阶段才做完整 Benchmark。

v1.0.0 RC 需要：

1. 选择至少 3 个真实客户项目样本。
2. 用 Codex-first workflow 跑完整链路。
3. 记录从 context 到 preview 的耗时。
4. 记录从 preview 到 approved queue 的耗时。
5. 记录人工修稿时间。
6. 记录页面通过率。
7. 记录 reuse/adapt 有效率。
8. 记录证据缺口发现率。
9. 输出 `10x_readiness_report.md`。
10. 若结果接近或达到 12h → 2h 目标，再发布 v1.0.0。

v1.0.0 不要求：

- 商业团队协作。
- 企业 SaaS。
- 完整远程连接器。
- 多人权限模型。
- 内置 LLM。

---

## 9. Definition of Done

v0.9 完成标准：

- Codex 能发现 Deck Master Skill。
- Codex 能按 playbook 创建 / 续跑 Deck run。
- 外部 Agent 能生成 Context Pack 并被 Deck Master import。
- 外部 Agent 能生成 Narrative Advice 并被 Deck Master apply。
- 外部 Agent 能生成 External Quality Review 并被 Deck Master import。
- PPT Deck Pro Max / PPT Master 能通过 handoff / handback 与 Deck Master 交接。
- Review Cockpit 2.0 能展示 Deck readiness、Claim coverage、Next actions、Page workbench。
- Workspace Learning Pack 能为下一次 Agent run 提供上下文。
- Companion Tool UAT validator 可运行。
- 所有新增 CLI 有测试。
- 所有新增 schema 有测试。
- `python3 -m unittest discover -s tests` 通过。
- 零内置 LLM provider。
- Team / P5 仍保持 experimental，不影响开源 1.0 主路径。

---

## 10. 推荐落库文件

```text
docs/deck-master-v0.9-agentic-integration-review-maturity-spec.md
docs/deck_master_v09_spec_pack/README.md
docs/deck_master_v09_spec_pack/deck-master-v0.9-agentic-integration-review-maturity-spec.md
docs/deck_master_v09_spec_pack/tasks/v0.9-a-skill-packaging.md
docs/deck_master_v09_spec_pack/tasks/v0.9-b-context-pack-contract.md
docs/deck_master_v09_spec_pack/tasks/v0.9-c-narrative-advisory-contract.md
docs/deck_master_v09_spec_pack/tasks/v0.9-d-external-quality-review-contract.md
docs/deck_master_v09_spec_pack/tasks/v0.9-e-build-tool-handoff-handback.md
docs/deck_master_v09_spec_pack/tasks/v0.9-f-review-cockpit-2.md
docs/deck_master_v09_spec_pack/tasks/v0.9-g-workspace-learning-pack.md
docs/deck_master_v09_spec_pack/tasks/v0.9-h-companion-tool-uat-contracts.md
docs/deck_master_v09_spec_pack/tasks/v0.9-i-lightweight-metrics-hooks.md
```

---

## 11. 结束语

Deck Master v0.9 的关键是收敛系统边界，把开源版打磨成足够清晰、足够稳定、足够 Agent-native 的专业 Deck Run OS。

正确方向是：

```text
Deck Master 不做推理。
Deck Master 不做解析。
Deck Master 不做生成。
Deck Master 负责协议、状态、审查、验收和资产复利。
```

这会让 Deck Master 开源版保持轻量、专业、可组合，同时又能和 Codex、Claude Code、Hermes、PPT Library、PPT Deck Pro Max、PPT Master 形成一个完整的 Solution Deck 生产链路。
