# Deck Master v0.9 Agentic Integration & Review Maturity Spec

日期：2026-06-12  
状态：PROPOSED / NEXT ITERATION SPEC  
适用范围：Deck Master 开源版 v0.9.x 到 v1.0.0 RC 前的核心开发方向  
上游依据：终局蓝图、Run OS MVP 确认版、P2-P5 runtime implementation、后续产品边界校准讨论

---

## 1. 结论

Deck Master v0.9 的核心目标不是继续扩展成一个完整商业 SaaS，也不是内置 LLM / Agent Runtime / 文档解析 / PPT 生成引擎。

Deck Master 开源版应被定义为：

> Agent-facing Solution Deck Run OS：面向 Codex-first 工作流，通过 CLI、Workspace、结构化 artifacts、Quality Gate、Review Cockpit 和 Skill / Tool contracts，把 Codex、Claude Code、Hermes、PPT Library、PPT Deck Pro Max、PPT Master 等外部 Agent / companion tools 串成一个专业 Solution Deck 生产链路。

本轮 v0.9 开发要把当前已经完成的 P2-P5 runtime 基线，进一步提升为：

1. 外部 Agent 可以发现、安装和调用 Deck Master Skill。
2. 外部 Agent 可以把已整理资料交给 Deck Master，而不是 Deck Master 自己解析所有资料。
3. 外部 Agent 可以执行叙事判断、语义审查、视觉审查，并以结构化 JSON 写回。
4. Deck Master 可以验证、应用和审查这些外部 Agent 结果。
5. PPT Library / PPT Deck Pro Max / PPT Master 通过 CLI contract 与 Deck Master 交接，不做强耦合。
6. Review Cockpit 从预览面板升级为 Run 审查与决策工具。
7. Workspace feedback 被整理成 Agent 可读的 learning pack，支撑下一次 run。
8. v1.0.0 benchmark 暂不在本轮重开发，但本轮要补最小 metrics hooks，为后续真实项目验证做准备。

---

## 2. 产品边界

### 2.1 Deck Master Open Source owns

Deck Master 开源版负责：

- Deck Workspace 文件系统结构。
- Run state / typed events / next-step resolver。
- 结构化 artifacts 的 schema、读写、验证和迁移。
- Context Pack import contract。
- Narrative advice task / result contract。
- External quality review task / result contract。
- Generation handoff / handback contract。
- PPT Library candidate normalization 与 sourcing decision。
- Review Cockpit。
- Quality Gate 与 export blocking。
- Workspace learning pack。
- Codex-first Skill / playbooks / schemas / prompts。
- Companion tool UAT contract。

### 2.2 External Agent owns

Codex / Claude Code / Hermes / Workbody 等外部 Agent 负责：

- LLM 推理。
- 多轮对话。
- 用户需求澄清。
- 复杂资料读取、摘要和整理。
- 叙事建议生成。
- 语义审查。
- 视觉审查。
- 调用 companion tools。
- 根据 Deck Master artifacts 做解释和下一步建议。

### 2.3 Companion tools own

PPT Library 负责：

- 历史 PPT indexing。
- slide-level search。
- candidate selection。
- screenshot extraction / reference。
- canonical slide id。
- historical slide metadata。

PPT Deck Pro Max 负责：

- 页面级内容生成。
- adapt / generate 页面生产。
- generation project skeleton。
- generated asset output。

PPT Master 负责：

- PPT/SVG/HTML 渲染。
- 可视化执行。
- rendering-specific QA。

### 2.4 Open-source v0.9 non-goals

本轮不做：

- 不内置 OpenAI / Claude / Gemini 等 LLM Provider。
- 不在 Deck Master CLI 中直接调用 LLM。
- 不自建 Agent Runtime。
- 不做 PDF / Excel / Screenshot / PPT 通用解析器。
- 不重做 PPT Library。
- 不重做 PPT Deck Pro Max。
- 不重做 PPT Master。
- 不做完整 benchmark 系统。
- 不做 SaaS / hosted service。
- 不做完整团队协作平台。
- 不做多用户权限和远程 workspace。
- 不做 CRM / 飞书 / Google Drive 实时连接器。
- 不做商业版 dashboard。

---

## 3. 当前基线

当前 main 已完成 P2-P5 runtime implementation，具备以下基础能力：

- `init-workspace` / `register-workspace` / `validate-workspace`。
- typed events。
- next-step resolver。
- review_status / action_intent migration。
- export quality blocking。
- context / brief / claim map。
- consulting judgments。
- claim-evidence graph。
- narrative_v2 planner。
- page task enrichment。
- sourcing scoring v2。
- evidence / context-conflict / confidentiality / brand gates。
- override governance。
- delivery validation / outcome。
- opportunity / approval / solution package experimental local modules。
- connector import contract。

当前代码已经支持：

```bash
python3 scripts/deck_master.py autoplan \
  --run-id <run_id> \
  --planning-mode narrative_v2 \
  --library-mode fixture
```

当前 v0.9 的工作不是重写上述能力，而是在此基础上补齐 Agent-facing contracts 与 Review Cockpit 成熟度。

---

## 4. v0.9 成功标准

v0.9 完成后，Deck Master 应达到以下状态：

1. 用户可以把本仓库内的 `skills/deck-master/` 软链接安装到 Codex skill 目录。
2. Codex 可以通过 skill 读取 Deck Master 工作流、schemas、playbooks 和 prompts。
3. Codex 可以生成 `context_pack.json`，Deck Master 可以 import 为 run context。
4. Codex 可以执行 narrative advisory task，并把 `narrative_advice.json` 写回。
5. Deck Master 可以 validate / import / apply narrative advice，并生成 diff。
6. Codex / Claude Code / Hermes 可以执行 external quality review，Deck Master 可以 import findings。
7. external quality findings 可以进入 Quality Governance，并参与 export blocking。
8. PPT Deck Pro Max / PPT Master 可以通过 generation result / render result handback 更新 preview。
9. Review Cockpit 能显示 Deck readiness、Claim coverage、Next 5 actions、page decision workbench。
10. Workspace learning pack 可以被 Codex 读取，并作为下一次 run 的上下文。
11. 所有新增 artifacts 都有 schema_version。
12. 所有 import / apply / review 操作都写 typed events。
13. 旧 P2-P5 主链路不破坏。
14. `python3 -m unittest discover -s tests` 通过。

---

## 5. Version path

| 版本 | 目标 | 核心能力 |
|---|---|---|
| v0.8.x | 已完成 | Run OS + Narrative v2 + Asset skeleton + Quality Governance + experimental P5 |
| v0.9.0 | Agentic Integration | Skill install、Context Pack、Narrative Advice、External Review、Generation Handback |
| v0.9.5 | Review Maturity | Review Cockpit 2.0、Workspace Learning Pack、Companion Tool UAT |
| v1.0.0 RC | Benchmark & Real Runs | 真实项目 benchmark、10x readiness report、3 个真实样本 |
| v1.0.0 | 正式收口 | Codex-first workflow 稳定、真实项目数据达到预期 |

---

## 6. Package A: Skill Packaging & Installation

### 6.1 Goal

让 Deck Master Skill 可以被 Codex-first 工作流发现、安装和调用；同时保持 Claude Code / Hermes 等外部 Agent 可通过同一套目录和 schema 适配。

### 6.2 File layout

新增：

```text
skills/
  deck-master/
    SKILL.md
    AGENTS.md
    README.md
    playbooks/
      codex-run-solution-deck.md
      review-cockpit-workflow.md
      ppt-library-handoff.md
      deck-pro-max-handoff.md
      external-quality-review.md
      workspace-learning.md
    schemas/
      context_pack.schema.json
      narrative_advice_task.schema.json
      narrative_advice_result.schema.json
      external_quality_review.schema.json
      generation_result.schema.json
      workspace_learning_pack.schema.json
    prompts/
      narrative_advisor.prompt.md
      quality_reviewer.prompt.md
      source_decision_reviewer.prompt.md
      review_cockpit_next_actions.prompt.md
```

### 6.3 CLI

新增：

```bash
python3 scripts/deck_master.py install-skill \
  --target codex \
  --agent-skill-dir ~/.codex/skills

python3 scripts/deck_master.py validate-skill \
  --target codex \
  --agent-skill-dir ~/.codex/skills
```

可选：

```bash
python3 scripts/deck_master.py install-skill \
  --target claude-code \
  --agent-skill-dir ~/.claude/skills

python3 scripts/deck_master.py install-skill \
  --target hermes \
  --agent-skill-dir ~/.hermes/skills
```

### 6.4 Behavior

- 默认创建软链接：`<agent-skill-dir>/deck-master -> <repo>/skills/deck-master`。
- 不复制文件。
- 重复安装必须幂等。
- 目标目录不存在时自动创建。
- 已存在非软链接目录时，默认报错。
- 支持 `--force` 删除旧链接后重建。
- 支持 `--dry-run` 打印将执行的操作。

### 6.5 Optional local config

新增可选配置：

```text
~/.deck-master/config.json
```

示例：

```json
{
  "agent_skill_dirs": {
    "codex": "~/.codex/skills",
    "claude-code": "~/.claude/skills",
    "hermes": "~/.hermes/skills"
  }
}
```

### 6.6 Acceptance criteria

- `install-skill --target codex` 成功创建软链接。
- `validate-skill` 能检查 `SKILL.md`、`AGENTS.md`、schemas、playbooks、prompts 是否存在。
- `install-skill --dry-run` 不修改文件系统。
- 软链接目标随仓库更新自动生效。
- Windows / macOS / Linux 路径错误时有清晰错误信息。

### 6.7 Tests

新增：

```text
tests/test_skill_install.py
```

覆盖：

- install codex symlink。
- validate installed skill。
- idempotent install。
- force reinstall。
- existing non-symlink path blocks。
- dry-run no write。
- missing required skill files returns invalid。

---

## 7. Package B: Agent Context Pack Contract

### 7.1 Goal

Deck Master 不负责解析所有真实资料；外部 Agent 负责读取 PDF / PPT / Excel / screenshot / web / meeting transcript，并输出标准 `context_pack.json`。Deck Master 负责 import、validate、normalize 和纳入 run artifacts。

### 7.2 New schema

新增：

```text
skills/deck-master/schemas/context_pack.schema.json
```

Schema version:

```text
deck_context_pack.v1
```

Minimum shape:

```json
{
  "schema_version": "deck_context_pack.v1",
  "run_id": "demo-run",
  "created_by": "codex",
  "sources": [
    {
      "source_id": "src_001",
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
          "quote_or_excerpt": "……",
          "location": "page 12",
          "publication_status": "safe_to_use",
          "sensitivity": "normal"
        }
      ],
      "sensitivity": "normal"
    }
  ]
}
```

### 7.3 Allowed source_type

- `meeting_transcript`
- `customer_material`
- `historical_solution`
- `product_material`
- `competitive_material`
- `market_research`
- `user_judgment`
- `knowledge_export`
- `other`

### 7.4 Allowed origin_type

- `txt`
- `md`
- `pdf`
- `pptx`
- `docx`
- `xlsx`
- `image`
- `screenshot`
- `web`
- `manual`
- `agent_summary`

### 7.5 Allowed publication_status

- `safe_to_use`
- `internal_only`
- `needs_redaction`
- `unknown`

### 7.6 CLI

新增：

```bash
python3 scripts/deck_master.py import-context-pack \
  --run-id <run_id> \
  --input context_pack.json
```

可选：

```bash
python3 scripts/deck_master.py create-run-from-context-pack \
  --workspace <workspace> \
  --input context_pack.json \
  --run-id <run_id>
```

### 7.7 Behavior

`import-context-pack`：

- 读取 JSON。
- 校验 schema_version。
- 校验 source_id / evidence_id 唯一性。
- 转换或更新 `context_manifest.json`。
- 保留 evidence_candidates。
- 写 typed event：`context_pack.imported`。
- 坏 JSON 不覆盖现有 `context_manifest.json`。

`create-run-from-context-pack`：

- 创建 request.json。
- 创建 context_manifest.json。
- 如果 workspace 存在，写入 request.workspace。
- 可以后续继续 `build-brief`、`build-claim-map`、`autoplan --planning-mode narrative_v2`。

### 7.8 Integration with Claim-Evidence Graph

`build_claim_evidence_graph()` 应优先读取 context_manifest 中的 evidence_candidates。

每个 evidence candidate 应转换为 graph evidence：

```json
{
  "evidence_id": "ev_001",
  "source_ref": "src_001",
  "evidence_type": "customer_material",
  "summary": "……",
  "confidence": 0.7,
  "publication_status": "safe_to_use",
  "sensitivity": "normal",
  "location": "page 12"
}
```

### 7.9 Codex playbook requirement

`skills/deck-master/playbooks/codex-run-solution-deck.md` 必须说明：

1. Codex 负责读取客户资料。
2. Codex 负责整理 context_pack。
3. Deck Master 只 import context_pack。
4. 不要求 Deck Master 解析原始 PDF / PPT / Excel。

### 7.10 Acceptance criteria

- Codex 生成的 context_pack 可被 Deck Master import。
- imported context_manifest 能被 build-brief / build-claim-map / claim graph 使用。
- evidence candidates 被 claim graph 保留。
- sensitivity / publication_status 不丢失。
- bad context_pack 不覆盖已有 artifact。

### 7.11 Tests

新增：

```text
tests/test_context_pack_contract.py
```

覆盖：

- valid context pack import。
- duplicated source_id blocks。
- duplicated evidence_id blocks。
- missing schema_version blocks。
- bad JSON no overwrite。
- context pack creates context_manifest。
- evidence_candidates enter claim_evidence_graph。

---

## 8. Package C: Narrative Advisory Task / Result Contract

### 8.1 Goal

Deck Master 不内置 LLM，但需要让 Codex / Claude Code / Hermes 能基于 run artifacts 做深度叙事判断，并把结构化建议写回。

### 8.2 New artifacts

```text
advisor_tasks/narrative_advice_task.json
advisor_results/narrative_advice.json
advisor_results/narrative_advice_diff.json
```

### 8.3 Task schema

Schema version:

```text
deck_narrative_advice_task.v1
```

Minimum shape:

```json
{
  "schema_version": "deck_narrative_advice_task.v1",
  "run_id": "demo-run",
  "task_id": "narrative_advice_demo-run",
  "created_for": "codex",
  "inputs": {
    "request": "request.json",
    "deck_brief": "deck_brief.json",
    "claim_map": "claim_map.json",
    "claim_evidence_graph": "claim_evidence_graph.json",
    "page_tasks": "page_tasks.json",
    "workspace_learning_pack": "workspace/learning/workspace_learning_pack.json"
  },
  "instructions": [
    "识别客户真实业务矛盾。",
    "判断当前 Deck 主线是否成立。",
    "补充 objection handling。",
    "指出哪些页面缺证据。",
    "建议哪些页面应该重写、转生成或放入 appendix。"
  ],
  "output_schema": "deck_narrative_advice.v1"
}
```

### 8.4 Result schema

Schema version:

```text
deck_narrative_advice.v1
```

Minimum shape:

```json
{
  "schema_version": "deck_narrative_advice.v1",
  "run_id": "demo-run",
  "advisor": "codex",
  "core_thesis_rewrite": "客户当前不是缺工具，而是缺跨渠道运营闭环。",
  "business_tension": "渠道增长和运营效率之间存在矛盾。",
  "objection_map": [
    {
      "objection": "客户可能认为现有系统已经够用。",
      "response_strategy": "用数据割裂、触达效率和复购提升证明统一运营中台的必要性。"
    }
  ],
  "page_recommendations": [
    {
      "beat_id": "beat_004",
      "action": "strengthen_claim",
      "reason": "页面只讲能力，没有证明业务价值。",
      "suggested_core_claim": "库存可视化的价值不是看板，而是提升履约效率。",
      "evidence_needed": ["履约时效", "缺货率", "库存准确率"]
    }
  ],
  "risk_flags": []
}
```

### 8.5 CLI

新增：

```bash
python3 scripts/deck_master.py prepare-narrative-advice \
  --run-id <run_id>

python3 scripts/deck_master.py import-narrative-advice \
  --run-id <run_id> \
  --input narrative_advice.json

python3 scripts/deck_master.py apply-narrative-advice \
  --run-id <run_id>
```

### 8.6 Behavior

`prepare-narrative-advice`：

- 收集 request / deck_brief / claim_map / claim_evidence_graph / page_tasks / workspace learning pack 引用。
- 不复制大文件内容，默认写 refs。
- 输出 task。
- 写 typed event：`narrative_advice.prepared`。

`import-narrative-advice`：

- 校验 result schema。
- 校验 beat_id 是否存在。
- 保存到 `advisor_results/narrative_advice.json`。
- 写 typed event：`narrative_advice.imported`。

`apply-narrative-advice`：

- 根据 page_recommendations 更新 page_tasks 中的 planning 字段。
- 不静默覆盖用户 locked 页面。
- 生成 `narrative_advice_diff.json`。
- 写 typed event：`narrative_advice.applied`。

### 8.7 Page action mapping

Allowed recommendation actions:

- `strengthen_claim`
- `weaken_claim`
- `add_evidence`
- `convert_to_generate`
- `replace_source`
- `move_to_appendix`
- `split_page`
- `merge_page`
- `manual_review_required`
- `no_change`

### 8.8 Acceptance criteria

- Task 可被 Codex 直接读取。
- Result 可校验。
- Apply 后 page_tasks 有可追踪修改。
- Diff 清楚说明修改前后。
- Review Cockpit 可显示 advice。
- 不内置 LLM。

### 8.9 Tests

新增：

```text
tests/test_narrative_advice_contract.py
```

覆盖：

- prepare task。
- import valid result。
- invalid beat_id blocks。
- invalid schema blocks。
- apply updates page_tasks。
- locked page not overwritten。
- diff generated。
- events written。

---

## 9. Package D: External Quality Review Contract

### 9.1 Goal

不内置语义 / 视觉审查 Agent；Deck Master 生成 review task，外部 Agent 执行审查并写回 findings。Deck Master import 后将 findings 纳入 Quality Governance 和 export blocking。

### 9.2 New artifacts

```text
quality_review_tasks/semantic_review_task.json
quality_review_tasks/visual_review_task.json
quality_review_tasks/client_readiness_review_task.json
quality_reports/external_semantic_gate.json
quality_reports/external_visual_gate.json
quality_reports/external_client_readiness_gate.json
```

### 9.3 CLI

新增：

```bash
python3 scripts/deck_master.py prepare-quality-review \
  --run-id <run_id> \
  --scope semantic,visual,evidence,client-readiness

python3 scripts/deck_master.py import-quality-review \
  --run-id <run_id> \
  --input external_quality_review.json
```

### 9.4 Review task schema

Schema version:

```text
deck_external_quality_review_task.v1
```

Minimum shape:

```json
{
  "schema_version": "deck_external_quality_review_task.v1",
  "run_id": "demo-run",
  "scope": "semantic",
  "reviewer_target": "codex",
  "inputs": {
    "preview_manifest": "preview_manifest.json",
    "page_tasks": "page_tasks.json",
    "claim_evidence_graph": "claim_evidence_graph.json",
    "quality_reports": "quality_reports/"
  },
  "review_dimensions": [
    "claim_evidence_alignment",
    "consulting_style_expression",
    "customer_specificity",
    "decision_readiness"
  ],
  "output_schema": "deck_external_quality_review.v1"
}
```

### 9.5 Review result schema

Schema version:

```text
deck_external_quality_review.v1
```

Minimum shape:

```json
{
  "schema_version": "deck_external_quality_review.v1",
  "run_id": "demo-run",
  "reviewer": "codex",
  "scope": "semantic",
  "findings": [
    {
      "finding_id": "ext_semantic_001",
      "severity": "P1",
      "page_id": "beat_004",
      "dimension": "claim_evidence_alignment",
      "message": "页面标题提出库存可视化价值，但正文没有给出履约效率证据。",
      "repair_instruction": "补充履约时效、缺货率、库存准确率等指标，或降低页面主张。"
    }
  ],
  "summary": {
    "status": "rework_required",
    "blocks_delivery": true
  }
}
```

### 9.6 Scope mapping

| scope | Output gate file |
|---|---|
| `semantic` | `quality_reports/external_semantic_gate.json` |
| `visual` | `quality_reports/external_visual_gate.json` |
| `evidence` | `quality_reports/external_evidence_gate.json` |
| `client-readiness` | `quality_reports/external_client_readiness_gate.json` |

### 9.7 Behavior

`prepare-quality-review`：

- 根据 scope 生成 review task。
- 任务引用现有 artifacts。
- 不调用 LLM。
- 写 event。

`import-quality-review`：

- 校验 schema。
- 校验 severity 只能是 P0/P1/P2/P3。
- 校验 page_id 如果存在，应能在 preview_manifest 或 page_tasks 找到。
- 写对应 gate report。
- P0/P1 参与 export blocking。
- 写 event。

### 9.8 Acceptance criteria

- Codex 可读取 task 并输出 review result。
- Review result 可导入。
- findings 在 Review Cockpit 可见。
- external P0/P1 findings 可阻断 client export。
- 多 reviewer 不互相覆盖。
- bad result 不覆盖旧 report。

### 9.9 Tests

新增：

```text
tests/test_external_quality_review_contract.py
```

覆盖：

- prepare semantic review task。
- import semantic review result。
- import visual review result。
- invalid severity blocks。
- invalid page_id warning or blocks by policy。
- imported P1 blocks export。
- imported P1 with override passes export。
- multiple reviewer files not overwritten。

---

## 10. Package E: Build Tool Handoff / Handback Contract

### 10.1 Goal

不在 Deck Master 中实现 PPT 页面生成，而是强化与 PPT Deck Pro Max / PPT Master 的任务交接和产物回收。

### 10.2 New artifacts

```text
generation_tasks/index.json
generation_tasks/<task_id>.json
generation_results/<beat_id>.json
generated_assets/<beat_id>/
render_results/<artifact_id>.json
```

### 10.3 CLI

新增：

```bash
python3 scripts/deck_master.py prepare-generation-handoff \
  --run-id <run_id>

python3 scripts/deck_master.py import-generation-result \
  --run-id <run_id> \
  --input generation_result.json

python3 scripts/deck_master.py refresh-preview-from-generation \
  --run-id <run_id>
```

可选：

```bash
python3 scripts/deck_master.py validate-generation-result \
  --input generation_result.json
```

### 10.4 Generation result schema

Schema version:

```text
deck_generation_result.v1
```

Minimum shape:

```json
{
  "schema_version": "deck_generation_result.v1",
  "run_id": "demo-run",
  "tool": "ppt-deck-pro-max",
  "task_id": "generation_004",
  "beat_id": "beat_004",
  "status": "completed",
  "artifact_type": "pptx_slide",
  "artifact_path": "generated_assets/beat_004/slide.pptx",
  "preview_path": "generated_assets/beat_004/preview.png",
  "notes": "Generated with reference slide structure.",
  "errors": []
}
```

Allowed status:

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

Allowed artifact_type:

- `pptx_slide`
- `svg`
- `html`
- `png_preview`
- `pptx_deck`
- `unknown`

### 10.5 Behavior

`prepare-generation-handoff`：

- 读取 sourcing_plan。
- 为 `adapt` / `generate` 页面准备 generation_tasks。
- 不执行生成工具。
- 输出 handoff summary。
- 写 event。

`import-generation-result`：

- 校验 result。
- 校验 beat_id / task_id。
- 保存 result。
- 对 completed result 检查 preview_path 是否存在。
- 对 failed result 保留 errors。
- 写 event。

`refresh-preview-from-generation`：

- 读取 generation_results。
- 对 completed result 更新 preview_manifest 对应页面 preview_path。
- 不覆盖 locked historical slide。
- failed result 在 page payload 中显示。
- 写 event。

### 10.6 Acceptance criteria

- PPT Deck Pro Max 可消费 generation_tasks。
- PPT Deck Pro Max 可写回 generation_result。
- Deck Master 可 import result 并刷新 preview。
- failed generation 可见且不阻断其他页面。
- locked page 不被覆盖。
- Review Cockpit 显示 generation status。

### 10.7 Tests

新增：

```text
tests/test_generation_handoff_contract.py
```

覆盖：

- prepare handoff。
- import completed result。
- import failed result。
- invalid beat_id blocks。
- missing preview_path warning。
- refresh preview updates manifest。
- locked page not overwritten。
- events written。

---

## 11. Package F: Review Cockpit 2.0

### 11.1 Goal

把 localhost Web UI 从“页面预览和基础审批”升级为“Run 审查与决策工具”。

### 11.2 Core panels

#### 11.2.1 Deck Readiness Panel

显示：

```text
Deck Readiness
- Narrative: pass / blocked
- Evidence: 7 gaps
- Sources: reuse 3 / adapt 4 / generate 5 / manual 2
- Quality: 2 P1 findings
- Export: blocked / ready
```

#### 11.2.2 Claim Coverage Matrix

显示：

| Claim | Pages | Evidence | Status |
|---|---|---:|---|
| claim_01 | P3 / P5 | 2 | ok |
| claim_02 | P6 | 0 | evidence_gap |
| claim_03 | none | 0 | uncovered |

#### 11.2.3 Next 5 Actions

自动生成下一步建议：

```text
1. P6 缺客户案例证据。
2. P8 ROI 页没有指标依据。
3. P4 复用历史页但客户行业冲突。
4. P10 generation task failed。
5. Draft Gate 有 2 个 P1，需要补证据或 override。
```

#### 11.2.4 Page Decision Workbench

页面操作：

- `approve`
- `reject`
- `request_evidence`
- `convert_to_generate`
- `replace_candidate`
- `move_to_appendix`
- `lock_source`
- `rerun_generation`
- `create_override`
- `add_review_note`

### 11.3 New APIs

新增或增强：

```text
GET  /api/readiness/<run_id>
GET  /api/claim-coverage/<run_id>
GET  /api/next-actions/<run_id>
POST /api/page/<page_id>/review-action?run_id=<run_id>
POST /api/page/<page_id>/lock-source?run_id=<run_id>
POST /api/page/<page_id>/move-to-appendix?run_id=<run_id>
POST /api/page/<page_id>/request-evidence?run_id=<run_id>
```

### 11.4 Review action schema

```json
{
  "action": "request_evidence",
  "notes": "ROI 页缺客户侧指标。",
  "target_status": "needs_review",
  "action_intent": "manual_placeholder",
  "evidence_request": {
    "evidence_type": "data_point",
    "description": "补充缺货率、库存准确率或履约时效指标。"
  }
}
```

### 11.5 Readiness calculation

Deck readiness 应综合：

- draft / draft_v2 gate。
- evidence gate。
- external review gates。
- approved page count。
- manual placeholder count。
- generation failed count。
- run-level blocking findings。
- export clearance。

输出：

```json
{
  "schema_version": "deck_readiness.v1",
  "run_id": "demo-run",
  "status": "blocked",
  "score": 62,
  "blocking_reasons": [
    "2 P1 quality findings without override",
    "3 evidence gaps",
    "1 generation task failed"
  ],
  "next_actions": []
}
```

### 11.6 Acceptance criteria

- 用户打开 Review Cockpit 能知道 deck 是否 ready。
- 用户能看到 claim coverage。
- 用户能看到 next 5 actions。
- 用户能对页面执行核心 review actions。
- 所有 actions 写 typed event。
- 所有 actions 不绕过 quality gate。
- external review findings 可见。
- generation status 可见。

### 11.7 Tests

新增：

```text
tests/test_review_cockpit_readiness.py
tests/test_review_cockpit_actions.py
```

覆盖：

- readiness blocked by quality。
- readiness blocked by evidence gaps。
- readiness ready when gates pass and pages approved。
- claim coverage matrix。
- next actions generation。
- request evidence action。
- move to appendix。
- lock source。
- action writes event。

---

## 12. Package G: Workspace Learning Pack

### 12.1 Goal

把 workspace feedback、asset health、delivery outcome、quality failures 聚合成 Agent 可读的 learning pack，支撑下一次 Codex run。

### 12.2 New artifacts

```text
workspace/learning/workspace_learning_pack.json
workspace/learning/agent_context_summary.md
```

### 12.3 CLI

新增：

```bash
python3 scripts/deck_master.py build-learning-pack \
  --workspace <workspace>
```

可选：

```bash
python3 scripts/deck_master.py show-learning-pack \
  --workspace <workspace>
```

### 12.4 Learning pack schema

Schema version:

```text
deck_workspace_learning_pack.v1
```

Minimum shape:

```json
{
  "schema_version": "deck_workspace_learning_pack.v1",
  "workspace": "/path/to/workspace",
  "generated_at": "2026-06-12T00:00:00Z",
  "high_value_patterns": [
    {
      "pattern": "问题诊断 + 目标架构 + 分阶段路线图",
      "approval_rate": 0.82,
      "used_in_runs": 8
    }
  ],
  "frequent_failure_modes": [
    {
      "failure": "ROI 页缺指标证据",
      "count": 12,
      "repair": "补业务指标或降级为价值假设"
    }
  ],
  "strong_assets": [
    {
      "canonical_slide_id": "slide_xxx",
      "title": "全渠道库存可视化目标架构",
      "approval_rate": 0.9,
      "best_for": ["retail", "omnichannel", "inventory"]
    }
  ],
  "agent_guidance": [
    "新 run 开始前优先检查 high_value_patterns。",
    "遇到 ROI 页时优先要求业务指标证据。"
  ]
}
```

### 12.5 Data sources

Learning pack 从以下来源聚合：

- `assets/asset_feedback.jsonl`
- `assets/asset_health_report.json`
- `runs/*/quality_reports/*.json`
- `runs/*/delivery/delivery_outcome.json`
- `runs/*/approved_queue.json`
- `structure-assets/page_archetypes.md/json`

### 12.6 Agent summary markdown

`agent_context_summary.md` 应面向 Codex 直接可读：

```md
# Deck Master Workspace Learning Summary

## Strong patterns
- 问题诊断 + 目标架构 + 分阶段路线图：approval_rate 82%。

## Frequent failure modes
- ROI 页经常缺指标证据。生成或审查 ROI 页时必须优先询问客户指标。

## Strong reusable assets
- slide_xxx：全渠道库存可视化目标架构。适合 retail / omnichannel / inventory。
```

### 12.7 Acceptance criteria

- learning pack 可生成。
- 空 workspace 不报错，返回 empty learning pack。
- Codex Skill 会提醒 Agent 读取 learning pack。
- narrative advice task 会引用 learning pack。
- sourcing 可读取部分 strong_assets。
- 不做复杂 BI dashboard。

### 12.8 Tests

新增：

```text
tests/test_workspace_learning_pack.py
```

覆盖：

- empty workspace。
- aggregate asset feedback。
- aggregate failure modes。
- aggregate strong assets。
- write markdown summary。
- narrative advice task references learning pack。

---

## 13. Package H: Companion Tool UAT Contracts

### 13.1 Goal

不重做 PPT Library / PPT Deck Pro Max / PPT Master，而是定义 contract validator 和 UAT 清单，确保 companion tools 可以稳定接入 Deck Master。

### 13.2 New docs

```text
docs/uat/ppt-library-contract-uat.md
docs/uat/ppt-deck-pro-max-contract-uat.md
docs/uat/ppt-master-contract-uat.md
```

### 13.3 New CLI

```bash
python3 scripts/deck_master.py validate-ppt-library-result \
  --input library_results/selection.json

python3 scripts/deck_master.py validate-generation-result \
  --input generation_result.json

python3 scripts/deck_master.py validate-render-result \
  --input render_result.json
```

### 13.4 PPT Library candidate contract

Minimum fields:

```json
{
  "slide_id": "...",
  "canonical_slide_id": "...",
  "title": "...",
  "text_summary": "...",
  "source_file": "...",
  "page_number": 12,
  "screenshot_path": "...",
  "confidence": 0.82,
  "narrative_role": "architecture",
  "page_archetype": "target_architecture",
  "source_project": "...",
  "industry": "retail",
  "win_rate": 0.67,
  "reuse_count": 3
}
```

Validator outputs:

```json
{
  "schema_version": "deck_companion_validation.v1",
  "valid": true,
  "errors": [],
  "warnings": ["candidate fixture_x missing screenshot_path"],
  "summary": {
    "candidates": 32,
    "with_screenshot": 29,
    "with_canonical_id": 32
  }
}
```

### 13.5 UAT checklist for PPT Library

- 600+ historical PPT indexed。
- 真实 brief 能返回候选。
- screenshot_path 可打开。
- canonical_slide_id 稳定。
- page_number 正确。
- source_file 可追踪。
- narrative_role / page_archetype 可用于 sourcing。
- empty result 不导致 Deck Master 中断。

### 13.6 UAT checklist for PPT Deck Pro Max

- 可读取 `generation_tasks/index.json`。
- 可读取单页 task。
- 可输出 `generation_result.json`。
- completed result 包含 preview_path。
- failed result 包含 errors。
- rerun 不覆盖 locked page。

### 13.7 UAT checklist for PPT Master

- 可读取 render task。
- 可输出 render result。
- 可提供 PPTX / SVG / HTML / PNG preview 路径。
- 页数可验证。
- render result 可进入 Render Gate。

### 13.8 Acceptance criteria

- validators 可运行。
- UAT docs 明确输入、输出、失败策略。
- companion tools 不需要被 import 到 Deck Master Python runtime。
- Codex Skill playbook 会引用 UAT contract。

### 13.9 Tests

新增：

```text
tests/test_companion_tool_contracts.py
```

覆盖：

- valid PPT Library result。
- missing screenshot warning。
- missing canonical id error。
- valid generation result。
- failed generation result。
- valid render result。

---

## 14. Lightweight Metrics Hooks for v1.0 Benchmark

### 14.1 Goal

本轮不做完整 benchmark 系统，但应补最小 run metrics hooks，为 v1.0.0 RC 的真实 benchmark 做准备。

### 14.2 New artifact

```text
run_metrics.json
```

Minimum shape:

```json
{
  "schema_version": "deck_run_metrics.v1",
  "run_id": "demo-run",
  "created_at": "...",
  "preview_ready_at": "...",
  "first_quality_gate_at": "...",
  "approved_queue_created_at": "...",
  "counts": {
    "pages": 12,
    "reuse": 3,
    "adapt": 4,
    "generate": 5,
    "manual_placeholder": 0,
    "quality_findings": 7,
    "approved_pages": 6,
    "rejected_pages": 1
  }
}
```

### 14.3 Behavior

- 不做 benchmark UI。
- 每个关键 step 完成时更新 metrics。
- metrics 只记录可观测时间和 count。
- 不记录用户隐私内容。
- 后续 benchmark 直接读取 metrics。

### 14.4 Acceptance criteria

- autoplan 后 metrics 有 preview_ready_at。
- quality-gate 后 metrics 有 first_quality_gate_at。
- export 后 metrics 有 approved_queue_created_at。
- counts 与 preview / sourcing / quality reports 一致。

---

## 15. Experimental modules policy

当前 `scripts/team/*`、opportunity、approval、team dashboard、solution package 作为 experimental local modules 保留。

v0.9 不继续强化人类团队协作产品。

要求：

- 文档中标记 experimental。
- 不作为 v1.0 critical path。
- 不要求商业化权限体系。
- 不删除现有测试。
- 若修改，必须保持现有 tests pass。

建议新增：

```text
docs/experimental/team-workspace-notes.md
```

说明：

```text
Team modules are local experimental extensions. They are not part of the open-source v1.0 critical path. A hosted/commercial edition may revisit permissions, team collaboration, and shared workspace later.
```

---

## 16. Agent task execution template

后续每个 Agent 任务应使用以下模板。

```text
你正在开发 MainQuestAI/Deck-Master。
请阅读：
- docs/specs/deck-master-v0.9-agentic-integration-review-maturity-spec.md
- skills/deck-master/AGENTS.md

本次只实现 Package <X>: <Name>。

必须遵守：
- 不内置 LLM provider。
- 不调用 OpenAI / Claude / Gemini API。
- 不重做 PPT Library / PPT Deck Pro Max / PPT Master。
- 不破坏 P2-P5 当前主链路。
- 新 artifact 必须有 schema_version。
- import/apply 操作必须写 typed events。
- bad JSON 不得覆盖旧 artifact。
- CLI 输出必须为 JSON。
- 保持 python3 -m unittest discover -s tests 通过。

完成后输出：
- 修改文件清单。
- 新增 CLI。
- 新增 schemas。
- 测试命令和结果。
- 已知限制。
```

---

## 17. Recommended implementation order

建议顺序：

1. Package A：Skill Packaging & Installation。
2. Package B：Agent Context Pack Contract。
3. Package C：Narrative Advisory Contract。
4. Package D：External Quality Review Contract。
5. Package E：Build Tool Handoff / Handback。
6. Package F：Review Cockpit 2.0。
7. Package G：Workspace Learning Pack。
8. Package H：Companion Tool UAT Contracts。
9. Lightweight Metrics Hooks。
10. Experimental module docs。

理由：

- 先让 Codex 能发现和调用 Deck Master。
- 再定义上下文、叙事、审查、生成的 agent/tool contract。
- 再升级 UI 审查体验。
- 最后沉淀 learning pack 和 UAT。

---

## 18. Definition of Done

v0.9 完成时必须满足：

- `skills/deck-master/` 存在且可安装到 Codex skill 目录。
- `install-skill` / `validate-skill` 可用。
- `import-context-pack` 可用。
- `prepare/import/apply-narrative-advice` 可用。
- `prepare/import-quality-review` 可用。
- `prepare/import/refresh-generation` handback 可用。
- Review Cockpit 2.0 核心 API 可用。
- Review Cockpit 展示 readiness / claim coverage / next actions。
- Workspace learning pack 可生成。
- Companion tool validators 可用。
- run_metrics 最小 hooks 可用。
- 所有新增 tests 通过。
- 旧 P2-P5 tests 通过。
- 无内置 LLM provider。
- 文档明确 Team modules experimental。

---

## 19. v1.0.0 RC benchmark gate

v0.9 完成后，v1.0.0 RC 才进入 benchmark。

Benchmark gate 应验证：

- 至少 3 个真实客户项目。
- 每个项目从 context pack 到 preview / quality gate / approved queue。
- 记录人工耗时。
- 记录页面通过率。
- 记录 reuse / adapt 有效率。
- 记录证据缺口发现情况。
- 和手工基线对比。
- 判断是否达到“约 12 小时到约 2 小时”的目标。

v1.0.0 不以功能数量收口，而以真实项目数据收口。

---

## 20. Final positioning

Deck Master v0.9 的核心不是“让 Deck Master 自己更像 Agent”，而是让它更适合被 Agent 使用。

最终形态：

```text
Codex / Claude Code / Hermes
  ↓ reads skill + run artifacts
Deck Master CLI / Runtime
  ↓ coordinates contracts
PPT Library / PPT Deck Pro Max / PPT Master
  ↓ returns candidates / generated pages / rendered assets
Deck Master Review Cockpit
  ↓ human review + quality governance
Workspace Learning Pack
  ↓ informs next Agent run
```

这条链路才是 Deck Master 开源版 1.0 前最重要的成熟度方向。
