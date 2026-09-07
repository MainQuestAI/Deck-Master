# 源码来源与证据边界

固定读取提交：`4199a6a8cc17ac522e074fee95bc114d4e274849`；读取日期：2026-09-07。

以下链接是本规格的源代码依据，不是本包新增能力已实现的证明。部分文件读取为相关函数/行段；本包不是整仓逐行审计。所有本地安装、路径、运行结果与真实客户产物需要 Codex 核验。

表中 R01—R23 为已读取源码/仓库文档依据；规格中的 MUST、目标阈值和新契约属于本轮设计决策，不由源码证明。上游可分发版本、许可证和实际可运行范围留给 Q0/A1 核验，不用历史猜测填充。

| ID | 来源 | 支持的判断 |
|---|---|---|
| R01 | [GitHub main 分支](https://api.github.com/repos/MainQuestAI/Deck-Master/branches/main) | 本次复核 main 与 PR #29 合并提交；运行结果不在此证据内 |
| R02 | [product-capability-manifest.json](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/product-capability-manifest.json) | 运行形态、零 Provider、公开/兼容能力和套件依赖 |
| R03 | [skills/manifest.json；skills/stage-contracts.json](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/skills/stage-contracts.json) | 现有阶段、必答问题、交接与契约版本；不要只改提示词 |
| R04 | [scripts/skills/installer.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/skills/installer.py) | 集中安装、release、lock、兼容目录和运行环境要求 |
| R05 | [scripts/runtime/builder_backend.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/runtime/builder_backend.py) | PPT Master 生产依赖、manifest 与 runtime status；默认后端不能绕过 |
| R06 | [PPT Library 真实集成](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/docs/integration/ppt-library-v2.md) | 真实 ppt-lib 命令、selection v2、授权与 Python 条件 |
| R07 | [scripts/context_intake/local_sources.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/context_intake/local_sources.py) | 文本类入口与前缀摘要/摘录，不能视为深度理解 |
| R08 | [scripts/context_intake/context_pack.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/context_intake/context_pack.py) | Context Pack v1 验证与统一转入 context_manifest |
| R09 | [scripts/conversation/brief_compiler.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/conversation/brief_compiler.py) | 主题/摘要切句形成核心要点的默认路径 |
| R10 | [scripts/narrative/judgment_builder.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/narrative/judgment_builder.py) | 业务判断/证据充分性规则的实际实现 |
| R11 | [scripts/planning/narrative_planner.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/planning/narrative_planner.py) | 模板先行、角色/标题推导覆盖和针对性 |
| R12 | [scripts/advisory/narrative.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/advisory/narrative.py) | 已有 narrative advice 的准备、导入与应用 |
| R13 | [高密度 Stage Protocol](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/skills/deck-builder-high-density/references/stage-protocol.md) | MBB/内容锁、provider、SVG、回读和既有保护，须保留 |
| R14 | [scripts/high_density/content.py；engine.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/high_density/content.py) | 内容与证据逻辑所在位置；提取复用而非复制 |
| R15 | [scripts/production/page_package.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/production/page_package.py) | Producer/Builder 边界、内部字段允许清单、构建输入 |
| R16 | [scripts/workflow/questions.py；handoff.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/workflow/questions.py) | 必答问题、新鲜度/含糊判断；阶段交接另见 handoff.py |
| R17 | [scripts/quality/gate_policy.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/quality/gate_policy.py) | 当前必需工程门和 gate 汇总机制 |
| R18 | [scripts/quality/external_review.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/quality/external_review.py) | 现有语义/视觉/证据/客户就绪任务与导入契约 |
| R19 | [scripts/runtime/final_readiness.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/runtime/final_readiness.py) | 当前版本质量、lineage、产物与高密度兼容汇总 |
| R20 | [scripts/learning/pack.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/learning/pack.py) | 反馈统计、错误通过率口径、高价值模式字段 |
| R21 | [benchmarks/README.md](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/benchmarks/README.md) | 真实元数据/Fixture 分离；原始资料与结果不入公开仓库 |
| R22 | [AGENTS 与新 Skill](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/skills/deck-master/SKILL.md) | 已确认授权/局部修改复用与 Agent 可继续；与 AGENTS 对照 |
| R23 | [docs/known-limitations.md](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/docs/known-limitations.md) | Technical Preview 与高密度未宣称完整生产就绪 |

补充已读取来源：
- [workflow/handoff.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/workflow/handoff.py)
- [high_density/engine.py](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/scripts/high_density/engine.py)
- [PPT Master 集成](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/docs/integration/ppt-master.md)
- [AGENTS.md](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/AGENTS.md)
- [新建 Deck Playbook](https://github.com/MainQuestAI/Deck-Master/blob/4199a6a8cc17ac522e074fee95bc114d4e274849/skills/deck-master/playbooks/codex-run-solution-deck.md)

本对话所附的历史 P2—P5 说明仅作背景：本轮保留其 Run OS/叙事/资产/质量的概念，不把历史阶段状态、旧路径或旧测试结论当作当前事实，也不重开其中的团队化扩展范围。
