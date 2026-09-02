# Deck Master 过度防御治理迭代 Spec v1

日期：2026-09-01
状态：Ready for implementation planning
适用范围：Deck Master PPT 生产生命周期中的过度防御问题，包括内容锁定、MBB 选择、蓝图生成、SVG/PPTX 构建、质量门禁、审阅、导出、最终放行和恢复重试。

## 1. 结论

本轮治理目标是把保护逻辑放回正确边界：只在真实边界和真实风险上阻断，不在内部已验证链路、正常业务文本、页面角色差异和不存在的 Host/UI 能力上制造闭锁。

当前审查结论：19 个活跃过度防御问题，1 个历史残留。其中 P0 4 个，P1 12 个，P2 3 个。

本 Spec 不要求删除真实安全控制。路径穿越、密钥泄漏、外部 Provider 结果来源、生产素材、防 unsupported fact、占位符和客户不可见内部执行文本仍然必须保留。

## 2. 为什么现在要做

当前问题已经从单点 bug 变成生产链路风险。用户在选择 `storyline.business` 后，本应继续生成 64 页 PPT，却被要求提供不存在的 Host/UI 密钥和签名证明。继续堆门禁会让每一轮修复都可能进入新的假阻断。

这会直接影响三个角色：

1. 用户：做 PPT 时被要求理解内部状态机、密钥、收据、Host/UI，而不是看到成片。
2. Agent 执行者：每一步都可能卡在不可完成的“证明动作”上，无法判断下一步该做什么。
3. Deck Master 产品：质量门禁从保障交付变成阻碍交付，可信度下降。

## 3. 已验证当前状态

验证日期：2026-09-01
当前仓：`main`，HEAD 与 `origin/main` 对齐。
当前已有未提交相关修复文件：`scripts/high_density/content.py`、`scripts/high_density/engine.py`、`skills/deck-builder-high-density/SKILL.md`、`tests/test_high_density_builder_v2.py`。

当前 LVMH run 的 `next-step` 返回 `awaiting_agent_build`，下一步是继续执行高密度构建并生成 `high_density_build/mbb/mbb_plan.json`。这说明此前故事线密钥闭锁已局部止血，但后续质量、审阅、导出和最终放行仍存在同类过度防御风险。

## 4. 根因

1. 测试集中证明“坏输入会被拦”，缺少“干净生产 happy path 必须通过”的端到端测试。
2. 高密度构建、标准 runtime、质量门禁、导出队列、最终 readiness 各自加保护，组合后没有统一用户结果验收。
3. 人工审阅被设计成 cryptographic attestation，但实际产品没有对应 Host/UI 注入器。
4. 质量报告缺少当前 artifact 绑定、过期判定和 supersession 规则，历史失败容易变成永久 veto。
5. 页面质量规则没有页面角色，导致封面、目录、章节页、方法页、图像型页面被同一套高密度正文页规则误杀。

## 5. 治理原则

1. 阻断只发生在真实风险边界：用户输入、外部 API、网络、文件、权限、密钥、客户可见交付物、事实证据和生产素材。
2. 内部已验证链路优先快速失败并给出可执行下一步，不能要求不存在的外部证明。
3. 所有人工动作必须有公开 CLI 或 UI 入口；没有入口的人工动作不能成为 required gate。
4. 质量规则必须识别 `builder_profile`、`output_profile`、`run_mode` 和页面角色。
5. 最终放行只读取当前 artifact 对应的当前 gate report。
6. 正常业务词默认允许，内部执行词和模板占位词默认拦截。
7. 64 页生产必须支持批量动作，不能把每页人工点击当作生产默认路径。

## 6. 全量问题清单

| ID | 严重度 | 问题 | 当前证据 | 治理要求 |
|---|---|---|---|---|
| ODG-01 | P0 | 标准链和高密度链的最终放行互相误判 | `scripts/runtime/next_step.py:111`、`scripts/runtime/final_readiness.py:162` | `final-readiness`、`next-step`、delivery validation 必须识别 `builder_profile=high_density` 和 `output_profile`，不能用标准 preview review 阻断高密度成片 |
| ODG-02 | P0 | 正常业务词被默认列入 P0 黑名单 | `scripts/quality/customer_visible_safety.py:13` | 从默认 forbidden terms 删除正常业务词，只保留占位符、内部执行标签和可客户误读的制作痕迹；项目可用 `quality/forbidden_terms.md` 加严 |
| ODG-03 | P0 | 客户可见扫描读取不可见 OOXML 内部元数据 | `scripts/quality/pptx_audit.py:49`、`scripts/quality/pptx_audit.py:133` | 默认只扫描真实 slide 文本、必要 notes/comments 和客户可见 doc props；排除 slide layout/master/presentation 内置占位文本和 shape `name` 默认属性 |
| ODG-04 | P0 | 高密度完成后 `next-step` 可能永久重复 render gate | `scripts/runtime/next_step.py:126` | 已存在当前 render result 和已通过 gate 时返回 final readiness 或 export 下一步；只在缺 gate 或 gate 过期时要求运行质量门禁 |
| ODG-05 | P1 | 主审视觉证明要求 `DECK_MASTER_REVIEW_ATTESTATION_KEY`，但无 Host/UI 注入器 | `scripts/high_density/integrity.py:71`、`scripts/high_density/svg.py:1018`、`scripts/high_density/engine.py:1079` | 默认生产链使用本地可追溯 review receipt；只有显式配置外部独立审查时才要求签名密钥 |
| ODG-06 | P1 | 蓝图批准是硬前置，但没有公开操作面 | `scripts/high_density/blueprint.py:569`、`scripts/high_density/engine.py:947` | 增加可操作命令或将 Provider receipt + content review pass 作为默认批准条件；不能只返回“找 Agent 写文件” |
| ODG-07 | P1 | 风格批准是硬前置，但公开 CLI 没有 select/approve style 命令 | `scripts/high_density/style.py:137`、`scripts/deck_master.py:3417` | 增加 `build select-style` 或在 `build prepare` 支持 `--style-id --approver`；状态提示必须给出真实可执行命令 |
| ODG-08 | P1 | Provider 结果强绑本机缓存根目录 | `scripts/high_density/blueprint.py:118` | Provider receipt 应记录来源类型和 hash，不应默认要求图片必须来自 `~/.codex/generated_images`；外部导入路径应可显式登记 |
| ODG-09 | P1 | 视觉审阅要求 producer self review 和 independent main review 双门禁 | `scripts/high_density/svg.py:1000`、`scripts/high_density/svg.py:1018` | 默认生产链允许“机器指标 pass + producer review pass”继续；main review 作为可配置增强门禁 |
| ODG-10 | P1 | 64 页生产被拆成页面级 Agent handoff，理论上 384 次交接 | `scripts/high_density/engine.py:947`、`scripts/high_density/engine.py:1040`、`scripts/high_density/engine.py:1077`、`scripts/high_density/engine.py:1079` | 按阶段批量返回 handoff：MBB、蓝图、SVG、视觉审阅、PPTX、readback；每页失败进入局部 rework 队列 |
| ODG-11 | P1 | sparse/full-slide image 检查没有页面角色 | `scripts/quality/pptx_audit.py:129`、`scripts/quality/pptx_audit.py:130` | 封面、章节页、视觉分隔页、图片页允许低文本或单主图；正文页继续防空页和整页截图偷懒 |
| ODG-12 | P1 | 历史 gate report 永久阻断最终交付 | `scripts/runtime/final_readiness.py:107`、`scripts/runtime/final_readiness.py:220` | gate report 必须绑定 artifact path、artifact hash、source fingerprint 或 manifest hash；过期报告只能 warning，不能 blocks_delivery |
| ODG-13 | P1 | P1 override 在导出和最终 readiness 中语义不一致 | `scripts/orchestrate/export_queue.py:150`、`scripts/runtime/final_readiness.py:220` | `has_active_override` 应被 delivery validation、export queue、final readiness 共用；P0 永远不可 override，P1 可显式 override |
| ODG-14 | P1 | 图片面积 caps 全局固定，误杀角色化页面 | `scripts/high_density/svg.py:223`、`scripts/high_density/svg.py:232`、`scripts/high_density/svg.py:694`、`scripts/high_density/svg.py:711` | 图片策略按页面角色配置：封面/视觉页可高图像占比，正文页保持文本不被图片覆盖 |
| ODG-15 | P1 | 每页都要求 evidence 和至少 3 个信息区域 | `docs/contracts/content-lock.v2.schema.json:17`、`docs/contracts/content-lock.v2.schema.json:21`、`scripts/high_density/content.py:826` | 证据和密度要求按页面角色执行；封面、目录、章节页、纯过渡页可使用结构性来源，不要求 3 个正文信息区域 |
| ODG-16 | P1 | 页码、来源、日期、方法标签等结构标签被当作事实证据要求 | `docs/contracts/content-lock.v2.schema.json:49`、`scripts/high_density/content.py:840` | `structural_label` 不得要求业务 evidence；有事实含义的数字和判断仍需 evidence |
| ODG-17 | P2 | `--watch` 在已可行动状态仍默认等 30 秒 | `scripts/high_density/engine.py:1182`、`scripts/deck_master.py:3432` | `awaiting_agent_build`、`awaiting_user_decision`、`needs_quality_review` 等可行动状态立即返回 |
| ODG-18 | P2 | 标准 builder 忽略 requested output profile，强制 HTML/PDF/PNG/PPTX 全套 | `scripts/runtime/build.py:219`、`scripts/runtime/build.py:375` | `production_pptx` 只要求 PPTX 和必要 readback；`client_delivery` 再要求完整客户包 |
| ODG-19 | P2 | Review Workbench 只有单页 approve，64 页成本过高 | `scripts/review/workbench.py:119`、`scripts/review/readiness.py:243` | 增加批量 approve/reject/needs-work，对无阻断页支持一次批准；有阻断页保留逐页原因 |
| ODG-R1 | Residue | 旧 `DECK_MASTER_USER_ATTESTATION_KEY` / `user_decision_receipt` 残留仍在 schema、文档和测试中 | `scripts/high_density/contracts.py:25`、`docs/contracts/mbb-user-decision-receipt.v1.schema.json`、`tests/test_high_density_builder_v2.py:515` | 已不应阻断故事线选择；后续清理旧 schema/docs/测试表述，避免再次被 Agent 误用 |

## 7. 目标行为

治理完成后的主链路：

```text
用户确认故事线/风格
  -> 高密度内容锁和 MBB 计划生成
  -> 蓝图/场景/SVG/PPTX 批量推进
  -> 当前 artifact 质量门禁
  -> 批量审阅非阻断页
  -> final readiness 读取当前报告
  -> 生成可编辑 PPTX 或客户交付包
```

任何阻断都必须回答三件事：

1. 真实风险是什么。
2. 用户或 Agent 可以执行哪条命令修复。
3. 修复后如何判定该阻断已经解除。

## 8. 分阶段治理方案

### ODG-A：P0 闭锁和误杀

目标：先保证干净生产链能继续走，不再被默认词表、不可见 OOXML 和重复 next-step 卡死。

交付：

1. 修正客户可见安全词表。
2. 修正 PPTX audit 默认扫描范围。
3. 修正高密度完成后的 `next-step`。
4. 修正 final readiness 的高密度 profile 识别。

退出标准：

1. 最小 clean PPTX 不因内置 `Placeholder`、layout/master 或 shape name 被 P0 拦截。
2. 当前 LVMH 64 页 page package 中正常业务词不触发默认 P0。
3. 高密度完成态不会返回同一条 render gate 死循环。
4. 相关单元测试和 targeted regression 全部通过。

### ODG-B：人工证明链和审批入口

目标：所有 required 人工动作都有真实入口；没有产品入口的密钥和签名不能卡 production。

交付：

1. 主审视觉证明改为本地可追溯 receipt，外部签名变成可配置增强门禁。
2. 风格选择提供公开命令。
3. 蓝图批准提供公开命令或明确自动批准条件。
4. Provider receipt 支持显式导入来源，不强绑本机缓存根。

退出标准：

1. 没有配置 `DECK_MASTER_REVIEW_ATTESTATION_KEY` 时，默认生产链仍可在指标和 review pass 后继续。
2. `next-step` 返回的每条人工动作都对应真实 CLI 命令。
3. Provider 蓝图可从用户指定本地路径登记并记录 hash。

### ODG-C：角色化页面规则和批量审阅

目标：把页面类型纳入质量判断，避免封面、章节页、目录页、图片页被正文页规则误杀，同时降低 64 页人工成本。

交付：

1. 定义页面角色到密度、证据、图片、文本、审阅策略的映射。
2. 修改 content lock / density / image caps / sparse page 检查。
3. 增加批量 review action。
4. 将 64 页交接改为阶段批量 handoff 和失败页 rework 队列。

退出标准：

1. 封面/章节/目录/视觉页能通过角色化规则。
2. 正文页仍会阻断 unsupported numeric facts、空页、整页截图偷懒、图片覆盖 P0/P1 文本。
3. 64 页可一次 approve 所有无阻断页，阻断页保留单页原因。

### ODG-D：最终放行一致性和残留清理

目标：最终 readiness、delivery validation、export queue、quality override 使用同一套当前 artifact 规则。

交付：

1. gate report freshness / supersession 规则。
2. P1 override 语义统一。
3. output profile respected。
4. `--watch` 可行动状态立即返回。
5. 清理旧 user attestation 残留表述，保留向后兼容读取但不作为 required gate。

退出标准：

1. 过期 gate report 不阻断当前 artifact。
2. P1 override 在三处表现一致。
3. `production_pptx` 不强制生成 HTML/PDF/PNG。
4. 旧 `DECK_MASTER_USER_ATTESTATION_KEY` 不出现在用户可执行指引中。

## 9. 不要动的内容

以下控制属于真实安全或交付质量边界，不纳入删除范围：

1. 路径穿越和 run 目录 containment。
2. 外部 Provider 结果 hash、prompt hash、content lock hash 和 artifact lineage。
3. 生产模式禁止 fixture fallback。
4. 密钥、token、原始客户材料、本机绝对路径进入客户可见 artifact 的检查。
5. unsupported factual values 和无证据业务判断的阻断。
6. 图片覆盖 P0/P1 正文文本的阻断。
7. PPTX 可编辑性 readback。
8. P0 finding 不允许 override。

## 10. 验收要求

每个 PR 必须至少包含：

1. 对应 ODG ID 的测试。
2. 一条干净 happy path 测试。
3. 一条仍然保留真实安全阻断的 negative test。
4. `python3 -m pytest` 的 targeted 命令和结果。
5. `git diff --check`。

整包完成时必须跑：

```bash
python3 -m pytest tests/test_customer_visible_safety.py tests/test_high_density_builder_v2.py
python3 -m pytest tests/test_final_readiness.py tests/test_delivery_validation.py tests/test_export_queue.py
git diff --check
```

如果受本机 LibreOffice 或外部 renderer 影响，必须记录为环境依赖，不得把环境失败写成业务通过。

## 11. 出界范围

本治理包不负责：

1. 重新设计 PPT 视觉风格。
2. 重新生成 LVMH 64 页正式内容。
3. 接入新的外部 PPT 后端或新 Provider。
4. 修复与过度防御无关的 UI、发布、安装或 benchmark 问题。
5. 提交、推送、合并分支。
