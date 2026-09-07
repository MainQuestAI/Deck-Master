# SC-1 Q0｜复用映射（reuse-map）

规格 `specs/01-baseline-and-reuse.md` §1.2 的每一条映射已对照本地源码核验。本文件记录"确认/修正/接入点"，供各 PR 直接引用，避免重新读码。

## 1. 逐条核验

| 规格条目 | 核验结论 | 实际接入点（file:line） |
|---|---|---|
| `scripts/skills/installer.py`（安装/兼容/绑定） | 确认。SUPPORTED_TARGETS=codex/claude-code/hermes/custom；project scope 仅 codex；release 树中心化 | A1：`installer.py:70-76,602-625`；release 树 1790-1915；SUITE_SKILLS 102-529 |
| `product-capability-manifest.json` | 确认。required_capabilities 17 项、public_skills 15 项、backend_deps deck-builder→ppt-master、skill_routes 存在 | A1/A4：manifest 根字段；`installer.py` `library_status._contract_state`（`runtime/library_status.py:276-336`）三方一致性已存在，A1 扩展复用 |
| `scripts/runtime/builder_backend.py` | 确认。仅做外部 PPT Master 绑定/校验，不读页面内容；`DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE` 第三方分支钉 SHA 绑定存在（修订五点名对象） | A2：绑定状态结构与 `backend_identity`（`runtime/render_handoff.py:47-54`）已有，可承接托管化改造 |
| `scripts/tools/ppt_library_client.py` | 确认。strict 模式真实存在且 fail-closed；`shutil.which` 探测可执行 | A3/A4：`ppt_library_client.py:1106-1155` 扩展托管解析；`runtime/library_status.py` 为只读检查器 |
| `scripts/context_intake/local_sources.py` | 确认。头部 900 字符摘要（F05）；全文存储缺失 | B1：`local_sources.py:31,58` 新增完整读取层，保留导航摘要 |
| `scripts/context_intake/context_pack.py` | 确认。v1 导入→manifest 证据候选 | B1/B2：v2 接入点即此；manifest 仍是统一承接 |
| `scripts/conversation/brief_compiler.py` | 确认存在 | B3：生产分支改为消费 Agent 结构化提炼（fixture 降级保留） |
| `scripts/narrative/judgment_builder.py` | 确认 F02。证据充分性=无 risk_flags 计数比 | B3：`judgment_builder.py:120-135` 重写判定，保留 judgment 对象/入口 |
| `scripts/planning/narrative_planner.py` | 确认 F06。生产 beat 标题硬编码 + 零售词过滤 | B4：`narrative_planner.py:144-209,346`；`page_budget.py:51-66` |
| `scripts/advisory/narrative.py` | 确认存在外部任务/导入/应用/diff 机制 | B4：扩展为主规划任务协议（复用回写） |
| `scripts/high_density/content.py`、`engine.py` | 确认。MBB 生成代码在 builder 内、fixture/dev 自动执行、production 等外部 Agent（详见 baseline-audit §5.2） | B4/B6：提取纯内容方法为公共模块；HD 经适配消费公共 narrative |
| `scripts/production/page_package.py` | 确认。Page Package 契约/索引已存在，但**生产链路无写入方、标准构建不消费**（本轮最重要缺口） | B5：新增生产写入方 + 标准构建适配消费；`scripts/build/manifest.py:204-213` 已有 v2 投影可复用 |
| `scripts/workflow/{questions,handoff}.py` | 确认。QuestionResolver 存在；handoff 有幂等/失效/投影 | A5/C2：扩展 answer 来源与 action envelope；不绕过运行时 |
| `scripts/quality/{external_review,gate_policy,gate_freshness}.py` | 确认。gate 绑定 fail-closed 机制真实有效 | C1—C3：升级载荷与必需策略，不动工程门 |
| `scripts/runtime/final_readiness.py` | 确认存在 | C3：公共内容就绪条件常态化 |
| `scripts/learning/pack.py` | 确认 F01。approval_rate 口径错误、rejection 未参与 | C4：`pack.py:64-148` 重算 |
| `benchmarks/` | 确认。real_* 仅元数据模板；fixture 与 real 分离 | C5：扩展 harness，登记真实样本前置条件 |

## 2. 规格未列明、但本轮可复用的既有资产

| 资产 | 说明 | 相关任务 |
|---|---|---|
| `scripts/build/manifest.py`（v2 build manifest + legacy_preview_adapter + page_package 投影） | 标准/HD 双侧共同的 v2 投影基础，B5 优先复用而非新写 | B5 |
| `scripts/runtime/render_handoff.py` 的 backend_identity 结构 | A2 托管后端版本绑定可直接沿用字段 | A2 |
| `scripts/assets/feedback.py` `append_feedback` | C4/F11 采集补齐的现成写入函数（server 端只需调用） | C4 |
| `runtime/library_status.py` `_contract_state` 三方一致性校验 | A1 lock 化后的一致性检查复用 | A1 |
| HD `provider_smoke.py:152-157` 的 package sha 复核模式 | B5 标准 build 适配消费 Page Package 时复用同一校验方式 | B5 |

## 3. 不复用/不改动的边界

- `scripts/preview/`（Review Desk）：本轮仅最小展示新增状态/结果，不重设计（规格 §0.4）。
- PPT Library 检索算法：只托管可执行程序与环境，不重写（规格 §1.2 A3 行）。
- 既有 `deck-*` 公开 skill 入口集合：不新增公开入口（D03）。
