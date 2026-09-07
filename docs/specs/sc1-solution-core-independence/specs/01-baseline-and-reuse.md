# 01｜基线复核、代码复用与差距

## 1.1 基线使用方法

远端读取基线为 `4199a6a8cc17ac522e074fee95bc114d4e274849`，main，2026-09-07，含 PR #29。[R01]
Codex 开工先核对本地 HEAD、origin/main、未提交变更及最近实际 Spec。主分支前移时提交差异表，不回退或覆盖用户变更。不把历史 P2—P5 的阶段名称当作当前缺失清单。

以下“已读取”仅表示远端代码事实；能否在用户环境运行、是否已在后续提交修复、函数调用是否完整，均需要 Codex 核验。

## 1.2 复用映射

| 已读取路径/对象 | 当前可观察事实 | 本轮处理 | 对应任务 |
|---|---|---|---|
| `scripts/skills/installer.py`、release/lock/bind | 已有集中安装、兼容入口和后端绑定机制 | 扩展为托管固定运行时、真实能力验收；不另建安装系统 | A1—A3 |
| `product-capability-manifest.json`、`skills/manifest.json` | 已有公开入口/兼容能力/依赖声明 | 区分安装完整性与本次任务必需能力；保持旧字段兼容 | A1、A4 |
| `scripts/runtime/builder_backend.py` | 标准生产依赖 PPT Master，存在 runtime 检查与绑定 | 托管来源、固定版本、真实 smoke；保留标准默认后端 | A2 |
| `scripts/tools/ppt_library_client.py` | 真实检索调用外部 `ppt-lib`，统一 selection v2 | 把可执行程序纳入托管；允许明确 none；不重写检索算法 | A3、A4 |
| `scripts/context_intake/local_sources.py` | 文本类直接读取、前缀摘要/摘录 | 保留导航用途，新增完整读取/解析覆盖和宿主抽取 | B1 |
| `scripts/context_intake/context_pack.py` | v1 导入转化为 context_manifest 的证据候选 | 新版接入来源定位、版本、冲突、研究记录；仍由 manifest 统一承接 | B1、B2 |
| `scripts/conversation/brief_compiler.py` | 主题和摘要切句形成核心要点 | 生产模式改为消费 Agent 结构化提炼；规则仅 Fixture/迁移降级 | B3 |
| `scripts/narrative/judgment_builder.py` | 部分判断为计数与无 risk flag 推导证据 | 保留对象和入口，改为真实判断内容+依据；修复证据充分性算法 | B3 |
| `scripts/planning/narrative_planner.py` | 默认模板先行并补业务背景 | 生产按方案与证据规划；模板改作结构建议/测试适配 | B4 |
| `scripts/advisory/narrative.py` | 有外部任务、导入、应用和 diff | 扩展成主规划 Agent 任务协议，复用回写与定向修改机制 | B4 |
| `scripts/high_density/content.py`、`engine.py` | 存在内容锁、MBB、来源绑定、视觉与编译阶段 | 提取公共内容逻辑；旧路径通过适配继续；不复制另写 | B4、B6 |
| `scripts/production/page_package.py` | 页面边界已分 customer_visible/internal_only | 继续作为 Builder 唯一页面内容输入；增加关系与视图引用 | B5 |
| `scripts/workflow/{questions,handoff}.py` | 必答问题阻断；handoff 有幂等、失效、投影 | 扩展答案来源和任务内子动作；不绕过运行时直接写日志 | A5、C2 |
| `scripts/quality/{external_review,gate_policy,gate_freshness}.py` | 有外部语义审查、产物门和新鲜度判断 | 升级审查载荷与必需策略、修订再审；不得替换现有工程门 | C1—C3 |
| `scripts/runtime/final_readiness.py` | 汇总当前质量、产物、lineage；高密度有兼容判断 | 正常化公共内容就绪条件，消除只靠 profile 特例完成业务验收 | C3 |
| `scripts/learning/pack.py` | 有反馈汇总；approval_rate 口径错误，高价值模式为空 | 修正指标、有限经验卡，不做新学习平台 | C4 |
| `benchmarks/` | Fixture 与 real_metadata 分离，真实素材不入库 | 扩展对照和人工投入统计，不把 metadata 当完成结果 | C5 |

来源索引详见 `sources/README.md`。

## 1.3 必须先做的本地核验产物

Q0 交付 `baseline-audit.md`：包含源码 HEAD、运行基线、受影响命令/契约实际调用图、标准/高密度调用入口、安装与依赖所有权清单、现有测试命令与结果、真实 UAT 可用条件、同名 Spec 与本包差异。

Q0 还须验证：Page Package 在标准后端是否被真实消费；高密度 MBB 当前是否在 Builder 内被再次编写；旧 schema/readback/gate 的来源绑定范围；生产模式是否强制真实 Library；Project/global 安装对各宿主的实际覆盖。不能根据函数存在断言链路已经完整。

## 1.4 既有问题的处理位置

| ID | 静态发现 | 本轮要求 |
|---|---|---|
| F01 | `_aggregate_strong_assets` 通过数/(通过数+交付数)，未计拒绝 | C4 修复为按最终审阅决定去重后的接受率；旧值不参与新排序 |
| F02 | 没有 risk_flags 被视作有证据 | B3 使用明确证据关系；未审证据是未审，不是充分 |
| F03 | AGENTS 停在外部等待与新 Skill 可继续存在冲突 | A5 统一 docs/registry/QuestionResolver/next-step 实际行为 |
| F04 | 主新建 Playbook 没有显式完整展开生成/构建/交付 | C6 改为真正可执行的全链路指导 |
| F05 | 资料头部截取可能遗漏后置约束 | B1 完整覆盖率与后置约束回归；不得只扩展字符上限 |

以上需要 Codex 编写最小复现并核验；本包不声称已复现或修复。
