# 方案依据与本次核对

日期：2026-10-29（Asia/Shanghai）。v0.1 整理公开理念与规划，v0.2 只修订开发套件；均未实施功能或真实内容生成。

## 来源与取舍

- [原始讨论：主线全量审查](https://chatgpt.com/c/6ae00b11-b864-83ea-82db-3c08f8ab3781)：本次读取完整五轮讨论，核心依据是用户对“服务讲述者”、会员系统首提/竞标、业务框架和迭代重心的明确纠正。
- [讨论与完整方案汇总](https://chatgpt.com/space/page_edfcb582fa8481918185226bc80ecf8e)：读取 sequence 2，含完整用户表述、修正后的框架与最终方案。Page 元数据为个人空间，无父 Page；本次未发现需另读的父级配置。
- [商业表达能力迭代方案](https://chatgpt.com/space/page_e5a0dd94684c8191ab0948bdd34d3ad0)：读取 sequence 0，提取 D00–D08、X01、协议建议与候选验收。以上链接可能需要原账户访问；公开仓库正文已自包含，不要求读者获取私有原对话。

原讨论中模板保真、原生图表和通用自动执行等早期提议，已按最终方向放入后续范围；“以听众理解为唯一出发点”的旧提议不作为当前产品定义。九卡和评测数值是方案建议，不被表述为已实施或已批准的费用承诺。

本套件保留原方案完整方法、兼容与验收设计，把每卡验收编号并补齐步骤、交付、验证入口。新增 D06a/D06b 是实施拆分，用来消除整卡依赖循环；不是新增产品能力。完整原始聊天和客户材料不复制进公开仓库。

## 固定源码核对

v0.1 从 [ce4ef8b2](https://github.com/MainQuestAI/Deck-Master/commit/ce4ef8b204dd5033019364ce44979adac7f4243b) 核对源码。v0.2 重新 fetch 后从最新 origin/main [03c06add](https://github.com/MainQuestAI/Deck-Master/commit/03c06add760eb20a9e457c6f8bda0b2a8b8036b7) 建立独立修订分支；两基线间只有文档变化，运行代码依据不变。原工作目录的其他改动未纳入。

| 核对点 | 实际观察 | 开发含义 |
| --- | --- | --- |
| [资源目录](../../../skills/deck-master/resource-catalog.json) | 67 条资源；M01–M10 的 id 为 content-m01 至 content-m10 | 复用已有目录，卡数不等于应用效果 |
| [方法选择/冻结](../../../src/deck_master/method_resources.py) | method_ids_for 依 kind/intent/phase/review_units；freeze_task_methods 接收显式资源，冻结 manifest/hash | 现函数没有商业策划能力参数；新默认包须按能力隔离，不全局替换 |
| [阶段指令](../../../src/deck_master/content_production.py) | framing 指令仍是受众变化目标；argument 产 Narrative 提案及可选 planned Plan | 任务导向须连同方法、阶段与成果约定修改 |
| [M07](../../../skills/deck-master/references/methods/M07-synthesis.md) | 当前要求去掉只有分类名称的节点 | 新增可展开业务主题语义，不能简单放宽空口号 |
| [依赖切片](../../../src/deck_master/dependency_slices.py) | TASK_FACT_IDENTITIES 含 scenario，不含 existing_decisions；framing 最小依赖仅 brief，argument 为 brief/audience，direction 为 audience/brief，均未强制 scenario | 补任务及决定的实际场景/共识绑定；tasks.py 整体摘要检查与 inputs_update 显式退役仍存在，不据此推断所有旧任务均可接受 |
| [影响分析](../../../src/deck_master/content_impact.py) | 记录 changed_task_fields；affected_pages 从变化来源引用计算，unaffected 为其补集 | 场景修改后的语义影响不能仅用现投影判定 |
| [大纲审查](../../../src/deck_master/outline_review.py) | 固定当前 Narrative/匹配 Plan；要求零页例外成立；派发无显式 selected_resource_ids | 复用审查链，补正式选卡传递 |
| [完整前审](../../../src/deck_master/content_review.py) | dispatch 读取 packet 并要求独立性，open_host_task 没传显式选卡 | 接入所需方法但保留真实独立审查 |
| [采用入口](../../../src/deck_master/content_production.py) | narrative.v1 严格分派和采用分支仍存在 | D01 必须适配所有消费处，不能只加 schema |
| Narrative 直接版本分派 | rg 搜索 src/deck_master 的 Python 文件，narrative.v1 涉及 models / content_production / content_insight / content_review / editing 共 5 个文件；editing.py:64 原未列入套件 | D01 补齐，且继续盘点无显式版本字符串的字段消费者 |
| [当前设计](../../../DESIGN.md) | 2026-10-24 UI 增量优先，浅色面与黑色主操作 | D06 沿现行入口接线，不重做视觉系统 |

链接从本文件回到仓库根；具体调用及所有受影响消费点由各卡开工再定位。历史合同与测试报告不反向覆盖活动 schema。

## 未执行的验证

原 Space 报告中的纯函数探针、零页面顺序采用合成路径是原讨论记录，本次未重跑。本次没有测试新框架效果，没有完成 D00 小样、D08 留出评估、浏览器交互、PPT 渲染或 PowerPoint/WPS 编辑。本套件对应的产品实现仍为 planned。

v0.1 的历史文档校验为 17 份 Markdown、160 个本地链接、68 项 AC、12 个工作单元；该记录不作为 v0.2 证据。

## v0.2 修订与验证

依据 2026-10-29 的修订说明及本轮 review，落实作者主审 + 三模型辅审、目标/最低评测档位和 D02a/D02b 拆分；补齐 Narrative 消费者、任务/决定依赖及四态投影冻结。将真实修正/采用前移至 D06a，补已关闭请求的有界后续改写，以 D00a 输入分诊解除 X01 的条件依赖循环。v0.2 只修改本套件文档，不实施产品代码。

文档检查结果见下方验证记录；它们不能替代 D00/D08 的模型生成、作者专业评审或产品运行验证。

| 检查命令/方式 | v0.2 结果 |
| --- | --- |
| `python3 -B` 执行一次性标准库校验脚本：解析卡片 AC、JSON、Markdown 链接与标题，深度遍历依赖图 | 13 份 Markdown、89 个本地链接/锚点、10 张卡、71 项 AC；索引与卡片逐项一致，每项恰归一个工作单元；15 个工作单元在 X01 未启用/启用两种图中均无环；README 数量与 I1 顺序一致 |
| `git show <固定 SHA>:<源码路径>`，并检查引用行号 | SPEC 的 29 条固定源码链接路径与行号存在 |
| `python3 -m json.tool docs/specs/deck-master-business-expression-20261029/execution-index.json` | 可解析；两档数值一致，实际档位未冻结，卡/单元保持 planned/inactive、71 项 AC 均为 not_run |
| `rg -n <旧评审措辞集合> docs/specs/deck-master-business-expression-20261029`（检查旧双人评审、额外裁决人与缺评审安排等表述） | 无匹配（退出码 1 为预期） |
| `git diff --exit-code -- src skills tests`；`git diff --name-only` | 产品代码、Skill、测试无变更；仅本套件 12 个文件改变，根 README 引用无冲突，无需修改 |
| `git diff --check` | 通过 |

本次没有运行产品测试、模型生成或三模型辅审，没有完成任何开发卡验收，也未执行合并、安装迁移或 Release 发布。
