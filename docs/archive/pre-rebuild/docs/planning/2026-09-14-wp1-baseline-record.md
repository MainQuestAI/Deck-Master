# WP1 基线记录｜成对任务与兼容边界

日期：2026-09-14\\
对应方案：[下一轮迭代执行方案](2026-09-13-deck-master-execution-plan.md)（WP1）\\
代码基线：方案基线 main@bcb5b37；实施分支 codex/professional-first-draft（f4c8380 起，已确认无代码漂移）。

本文记录 2026-09-14 工程实施会话能够确定的基线决策与状态；WP1 中依赖
维护者输入的部分保持开放，见文末"待维护者输入"。

## 已确定的基线决策

| 项 | 决策 | 依据 |
| --- | --- | --- |
| 首批生产路径 | 高密度路线（page_packages 原生输入：fail-closed 加载、内容锁、build manifest v2） | 用户 2026-09-14 确认；整稿接入改动最小、验收最直接 |
| 标准路线 | 保持现状不破坏，首轮不适配 package 输入；package-only run 走标准构建会得到明确失败原因 | 执行方案 §4"先选一条实际可用生产路径" |
| 无库路径 | 无库为默认正常新建路径；显式 `--library-mode real` 保留真实依赖失败；fixture 仅限 demo/dev 显式使用 | 执行方案 §5 WP3、6.4.3 |
| 整稿入口 | `import-plan --source agent` JSON（narrative_plan + page_tasks + page_packages），复用既有 Page Package 契约 | 执行方案 WP3 成稿接入规则、工程评审 F1 |
| 宿主 | Codex CLI（当前实施环境）；其他宿主不在此轮承诺范围 | 执行方案 WP1 输出项，本会话可确定的部分 |

## 实施状态（截至本记录）

- 整稿接入、无库路径、门禁减法、pytest 统一已实施并合入本分支
  （提交 1028059、746f074、bbb175b、61d840b、d5d61f5、902fc1d 及后续）。
- fixture 级验证：正常入口（start-conversation → build-brief →
  build-claim-map → import-plan）整稿导入后 next-step 直达
  `build prepare --profile high-density`；高密度内容锁密度/证据/引用
  核对全部通过后进入 blueprint 阶段（awaiting_agent_build，宿主执行
  蓝图生成）。
- 真实 PPT 生产读回（执行方案 6.4.5）、办公软件编辑、安装包无库交付
  （WP5）尚未执行，等真实材料与冻结候选。

## D1 / D2 任务说明骨架（待维护者材料）

- **D1（首次能力交流）**：需要同一家企业的能力/案例资料。成稿目标：
  企业是谁、擅长哪些任务、能力如何发挥、何种案例支持适配判断；结尾
  可总结适用任务，不默认推进 POC。
- **D2（已有客户方案评审）**：与 D1 同源企业事实 + 具体客户任务资料。
  成稿目标：当前目标与条件、推荐方案、关键机制、真实取舍、实施依赖；
  压缩公司介绍，结尾呈现本次需要判断的事项。
- 场景确需不同资料时明确记录差异，不得给一个任务偷偷增加有利事实。

可复用的仓库内合成材料起点（仅用于方法演示，不冒充真实任务）：
`docs/specs/sc1-solution-core-independence/examples/`（合成材料包，含
`materials/late_constraint.txt` 末尾约束检验材料）、
`examples/briefs/`、`examples/context/`、执行方案 §7 示例。

## 旧 run 兼容基线

- 代表性旧 run 样本：`runs/local-mac-v098-smoke/`（含 narrative_plan、
  page_tasks、sourcing_plan、preview_manifest、quality_reports；库结果
  为 v1 形态）。WP5 恢复复验按此样本的原有能力执行。
- 恢复能力现状：导入/运行备份写入 `overrides/`（plan、sourcing、
  workspace binding 三处），恢复为人工拷贝或重新导入；无独立恢复命令。
  整稿导入中断时自动回滚到备份状态并有 stage 完整性守卫兜底。

## 待维护者输入

1. D1/D2 同源企业材料（能力/案例 + 客户任务）——WP2 成稿的前置。
2. 业务阅稿人安排（WP5）。
3. 首轮公开样例的可公开范围确认。
