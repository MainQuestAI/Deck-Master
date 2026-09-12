# Deck Master SC-1.1 · Native Deck Core
## 基于 PR #30 的独立生产内核纠偏与收口 Spec Pack

**规格版本：SC-1.1-NDC v1.0｜日期：2026-09-07｜实现基线：PR #30 @ `4977f89573d18a282c605360dc55f751443a2b21`。**

这是对 SC-1 的增量纠偏，不是重新开发完整 Deck Master，也不是产品软件版本号或完成报告。本包正式替换 SC-1 D04 的“PPT Master 必须作为标准默认后端”约束，以及所有以该后端身份为前提的衍生要求。其他内容质量、真实研究、用户负担、审批和数据保护目标继续有效。

**目标：新用户只安装 Deck Master 与其声明的基础依赖；在授权宿主工具支持下，以“确认内容→图片蓝图→视觉模型重建 SVG→内置原生 PPTX 编译→回读与修订”为默认生产链路。不存在外部 PPT Master 仓库、Skill、绑定、托管整包时，仍能完成真实交付。**

优先复用 `scripts/high_density/` 已有编译、解析、视觉检查与回读代码，提取为公共内核。仅缺项允许按许可证和最小依赖闭包吸收上游组件；不得换名复制完整 PPT Master 后再称为独立。

### 阅读顺序

先读 [产品裁决与旧规格替换](specs/00-decisions-and-supersession.md)，再读 [基线与修改地图](specs/01-baseline-and-change-map.md)、[目标架构](specs/02-architecture-and-truth.md)、[开发顺序](tasks/DELIVERY_PLAN.md)。执行型 Agent 从 [START_HERE](agent/START_HERE.md) 开始。完整合并说明书为 [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)。

### 交付边界

本包包括目标接口、迁移规则、专业生产方法和计划验收。新增接口及文件均明确为目标设计。远端源码读取仅用于固定设计基线；本地文件、安装、代码能力、测试、宿主真实工具可用性和成片效果，**需要 Codex 核验**。不得把 Schema 样例、自检或 PR 描述中的测试数字视为本轮产品测试结果。

### 范围锁定

保留 SC-1 材料、研究、方案、公共叙事、Page Package、图文一致性、质量修订和反馈体系。此次不重写 PPT Library 索引算法，不新增模型 Provider、Agent Runtime、企业权限或聊天 UI。无历史库路径必须可用；历史资产路径按用户选择保持可用或如实报告缺项。

### 交付组织

一个增量目标、三个工作包、五个建议 PR。最终状态必须区分 `in_progress`、`engineering_complete / outcome_pending`、`accepted`。默认真实内置生产、必要接线或故障恢复未通过，不能进入 engineering_complete。SC-1 原有三类真实方案对照未完成，不能对外宣布整轮内容效果通过。
