# Deck Master 主流程重建｜完整实施与开发 Spec Pack v1.1

开发任务卡已按本清单拆分：见[25张任务卡与执行顺序](task-cards/README.md)及[126个子任务CSV](task-cards/subtasks.csv)。任务卡及正式Spec已同步修正验收归属和工程试行依赖；当前均未实施。

> 仓库基线说明：本目录由 v1.1 交付包导入。`sources/` 中指向仓库内代码的链接已改为相对路径；会话日志、事故运行目录和其他仓库外证据只保留说明，不提交本机绝对路径或原始运行材料。原始 ZIP 保存在仓库外的项目诊断归档中。

**用途：直接供 Codex 进行仓库核验、任务拆分、实施、测试、切换与退役。交付类型：文档和规范，不是已经实现的代码。**

本包将“新建什么、从哪里提取、调整什么、何时删除、用什么验收”落到模块、路径、接口、数据对象和工作包。不另建产品仓库，不再增加一套长期并行的运行模式，不引入内置模型供应商。

## 文件阅读顺序

先读 `MASTER_IMPLEMENTATION_SPEC.md`（合并总手册）或顺序阅读：

| 文档 | 负责的问题 |
| --- | --- |
| specs/00-execution-baseline.md | 授权、基线、范围、来源层级与产品裁决 |
| specs/01-target-architecture.md | 新核心如何建、依赖方向、目录、命名 |
| specs/02-file-change-and-retirement.md | 旧文件逐项处置、删除前提、跨分支提取 |
| specs/03-data-and-state-contracts.md | 唯一当前清单、页面、产物、任务、检查与版本 |
| specs/04-host-content-method.md | 默认内容生产、材料阅读、观点与完整正文 |
| specs/05-blueprint-and-svg.md | 生图输入、原图预期、正文往返、忠实 SVG 重构 |
| specs/06-native-compiler.md | 独立 SVG→PPTX 内核、支持范围、具体缺陷修复 |
| specs/07-review-and-quality.md | 检查什么、如何判、如何改、如何防止自证 |
| specs/08-edits-recovery-and-budget.md | 局部修改、事务、取消、晚到结果、费用边界 |
| specs/09-cli-and-host-protocol.md | 可实施 CLI、Host 交接、返回值和错误行为 |
| specs/10-review-workbench.md | 真实页面工作台、接口、编辑闭环与 UI 状态 |
| specs/11-package-install-and-cutover.md | 包结构、安装、PPT Master 解绑、唯一入口切换 |
| specs/12-legacy-and-document-retirement.md | 旧 run、旧 Skill、旧合同、历史文档与源码退役 |
| specs/13-verification-and-release.md | 正反例、内容迁移、公平对照、交付判断 |
| specs/14-agent-execution.md | 五工作包、依赖、并行规则、Codex 启动指令 |

`work-packages/` 是可逐包交给执行 Agent 的工作单；`inventory/` 是施工台账；`contracts/` 和 `examples/` 是拟实施契约及合成示例；`tools/materialize_inventory.py` 仅生成只读仓库清单，不改仓库、不执行删除；`sources/` 是原始依据副本。

## 三项不可误读的边界

1. 现状以固定 SHA 的核查和附件为依据；新路径、接口、状态、对象和目录均是**本包设计**，不代表它们已经存在。
2. 文档起草不等于代码实施、激活安装、发布或合并授权。开始实施须已有用户明确授权；本轮没有执行这些动作。
3. **需要 Codex 核验**：本地 HEAD、工作树、安装来源、未提交修改、精确函数现状、跨分支提取结果、测试、运行、UI 和产物。不得把本包的预期结果写成已运行结果。

原有 SC-1、Skill OS、P2–P5 与旧 RC 规格只作历史资料；与本包冲突的目标不再自动继承。本包不复活用户时间下降、固定数量样例成功、所有 Skill 齐备或外部 PPT Master 认证作为首稿质量标准。

## 实施规模与入口

本包包含15章Spec、5个工作包、25个开发任务；177个旧scripts逐文件处置、75项拟建目标（含35个核心文件与构建/方法/测试等附属目标）、58个旧合同、122个旧顶层测试文件的迁移分类，以及90条拟验收行为。数量仅描述文档覆盖，不是新增平台规模或质量指标。

直接交Codex：先读[START_HERE_FOR_CODEX.md](START_HERE_FOR_CODEX.md)，再按[IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md)推进。逐文件操作见[inventory/FILE_LEVEL_IMPLEMENTATION_CHECKLIST.md](inventory/FILE_LEVEL_IMPLEMENTATION_CHECKLIST.md)。

`PACK_VALIDATION.json`只记录文档结构、Schema与合成例、任务依赖、文件引用及清单一致性；不代表Deck Master产品测试或真实稿件通过。

## v1.1增量与复核

先读[CHANGELOG-v1.1.md](CHANGELOG-v1.1.md)。本包直接更新15章、五合同、25任务、工作包、施工表与示例，不是只附一页补丁。R1–R6与其他接口意见见变更表；完整往返例在[examples/roundtrips/README.md](examples/roundtrips/README.md)。

本次只复核并修改现有文档包，B0/K0为已有固定依据；用户转交的Codex本地核查不是本次新运行。新代码仍未实施。
