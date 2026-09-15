# 专业首稿与过度防御整改实施记录

日期：2026-09-15  
分支：`codex/professional-first-draft`  
实施起点：`4d44c7ee92632622a13d3770025ccac5ea49b982`

## 完成标准

本轮以正常任务能连续生成、修改、恢复和交付完整业务内容为工程完成标准。页面正文、职责、关系、数值、单位和脚注必须进入真实可编辑产物；页面集合及顺序由当前成稿决定。测试通过只证明工程行为，不代替用户对专业性、视觉效果和实际编辑体验的验收。

## 实施路线

首条生产路线继续使用 `high_density`。`import-plan --source agent` 接收完整叙事和 PagePackage，`ready_for_build` 保持为规范状态。新内容锁使用 `enrichment.framework=page_package`，旧 `mbb` 仅用于兼容读取。Scene canonical 文件是当前权威；已有蓝图、SVG、PPTX、渲染、读回和局部修改能力继续复用。

## 整改索引

| 审计项 | 实际改动 | 主要实现位置 |
| --- | --- | --- |
| IN-01、IN-09、QD-12 | 删除十模块、默认 12/15 页和最少页数等固定结构要求；自动页数由真实任务主题形成，明确页数仍受尊重 | `scripts/workflow/stage_checks.py`、`scripts/planning/narrative_planner.py`、`scripts/planning/page_budget.py`、`scripts/quality/draft_gate_v2.py` |
| IN-02、IN-03、IN-04、PR-03、PR-19、QD-11 | 历史页缺失不再等同证据缺失；删除关键词代理、机械前三来源、循环自证和无风险扣分；事实引用与设计判断分开处理 | `scripts/sourcing/plan.py`、`scripts/planning/claim_map.py`、`scripts/advisory/narrative.py`、`scripts/high_density/content.py`、`scripts/quality/draft_gate_v2.py` |
| IN-06、IN-07、IN-08、DOC-01 | 只问当前任务适用的问题；“没有额外约束”是有效回答；已授权的 brief、planning、sourcing 与可由当前 Agent 完成的 handoff 连续推进 | `scripts/workflow/questions.py`、`scripts/workflow/stage_checks.py`、`scripts/workflow/handoff.py`、`skills/stage-contracts.json`、`AGENTS.md` |
| PF-01、PF-02、PF-03、PF-04 | doctor、setup、workspace 和 suite 状态按当前宿主、路线与阶段判断；无关模板、Review Desk、其他宿主和软件 RC 不再成为单份 Deck 前置 | `scripts/deck_master.py`、`scripts/runtime/setup_status.py`、`scripts/workspace/foundation.py`、`scripts/skills/installer.py` |
| PR-01、PR-02、PR-04 | 完整 PagePackage 直接成为内容锁；不再强制 MBB/SCR/逐页管理结论；递归投影真实可见业务叶节点，排除结构元数据 | `scripts/high_density/content.py`、`scripts/high_density/engine.py`、`docs/contracts/content-lock.v2.schema.json` |
| PR-05、PR-11、PR-12、QD-01、QD-02、QD-03、QD-15 | 删除块数、字符数、数字数、图片面积和普通业务词代理门禁；内部审稿引用不再按原样子串误杀；保留真实溢出、泄漏、归属和编辑性检查 | `scripts/high_density/visibility.py`、`scripts/high_density/svg.py`、`scripts/production/page_package.py`、`scripts/quality/pptx_audit.py`、`scripts/quality/customer_visible_safety.py`、`scripts/quality/context_conflict_gate.py` |
| PR-06、PR-07、PR-08 | 旧格式按 schema/版本识别；run-local provider hash 支持跨目录恢复；canonical Scene 是唯一当前入口，旧镜像仅兼容读取 | `scripts/high_density/migration.py`、`scripts/high_density/blueprint.py`、`scripts/high_density/integrity.py`、`scripts/high_density/scene.py` |
| PR-09/QD-05、QD-07、QD-08 | 按页面内容、视觉和集合变化传播失效；纯重排只重新装配文件；产物新鲜度按当前文件身份判断，不由时间戳和无关记录触发全稿返工 | `scripts/runtime/orchestration.py`、`scripts/high_density/engine.py`、`scripts/quality/gate_freshness.py`、`scripts/workflow/state.py` |
| PR-10、QD-04、QD-16 | 自动测量不冒充主编或主审；未评估维度保持未评估；目录非空不再冒充品牌通过 | `scripts/high_density/self_review.py`、`scripts/high_density/main_review.py`、`scripts/high_density/svg.py`、`scripts/quality/rubric.py`、`scripts/quality/brand_gate.py` |
| PR-13 | 返修意见回到真实生产输入；删除任意三次失败即冻结，保留用户明确预算和停止指令 | `scripts/high_density/engine.py`、`skills/deck-builder-high-density/references/stage-protocol.md` |
| PR-15、QD-17、PF-05 | 同次状态查询复用后端检查；同一 PPTX 审计共享解包结果；final-readiness 复用当前 gate policy；CI 每个 Python 版本只运行一次完整测试 | `scripts/runtime/builder_backend.py`、`scripts/quality/pptx_audit.py`、`scripts/quality/gate_runner.py`、`scripts/runtime/final_readiness.py`、`.github/workflows/ci.yml` |
| QD-06、QD-09 | workflow client-export 批准写入既有最终批准事实，撤销同步失效；删除未被出口消费的公开平行 team approval 命令 | `scripts/workflow/approval.py`、`scripts/deck_master.py` |
| QD-10、QD-13、QD-14 | delivery、Review Desk、next-step 和出口统一读取当前产物及适用 gate；过期和非必需旧报告不再阻断，当前 P0/P1 仍被发现 | `scripts/delivery/validate.py`、`scripts/orchestrate/export_queue.py`、`scripts/review/readiness.py`、`scripts/quality/gate_policy.py`、`scripts/runtime/final_readiness.py` |

## 保留的有效保护

- 跨 run 路径和来源身份必须明确，真实缺失或损坏继续报错。
- 生产所需的真实权限、工具和依赖缺失继续阻断对应动作。
- 当前产物必须可打开、可读回、可编辑；真实溢出、结构损坏和关系错误继续进入修订。
- 导入回滚、历史备份、canonical 当前文件和旧版本恢复继续保留。
- 没有实际审阅时，不生成主审通过、品牌通过或业务批准。

## 验证与交付边界

定向回归覆盖短稿、不同任务结构、无库路径、嵌套正文、图示关系、合法业务词、局部修改、增删页、重排、旧 run、当前 gate 和批准状态。2026-09-15 的无库真实 production 验证通过已安装的 CLI 从完整 PagePackage 形成两页 PPTX；蓝图由真实 ImageGen 产生，Scene 和 SVG 由 Agent 根据正文、图示意图重建，生产没有借用 fixture。安装后仅修改第二页并重建：导入报告仅标记第二页变化，第一页 SVG 哈希不变，文件级 PPTX 与检查刷新。最终 PPTX 的 OpenXML 验证零错误，officecli 读到两页、43 个原生 shape、零张整页图片；render/delivery gate 均通过，final-readiness 为 ready。

真实运行还发现并修复 canonical 内容锁批准、安装包模块及契约定位、中文换行误判、旧蓝图 handoff 引用、像素相似度压倒实际视觉审阅、文本 run 的 OpenXML 顺序、无媒体图片误阻断和完整 PagePackage 出口仍索取独立 Brief 等连续生产缺陷。像素指标保留为观察结果，当前 producer/main review 的通过由实际工程阅图记录；两个 reviewer ID 不能代表两个独立的人类专业审稿人。合成两页证明工程链路及局部修改，不证明首次交流/已有客户评审在陌生企业和真实业务材料上普遍专业可用。

release smoke、无 Library 候选安装、真实 PPT 渲染和读回已完成；完整测试与静态检查以本分支最终 SHA 的实际结果为准。安装完成后由用户验收专业内容、视觉表达及办公软件中的实际编辑体验。

原始客户材料、失败现场和生成 run 保持在仓库外；本文件只记录可公开复现的工程行为与边界。
