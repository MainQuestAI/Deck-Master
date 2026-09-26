# 外部原始意见与主审取舍

输入为 30KB PLAN 及明确源码片段；不是完整仓库读取。原始回包的 modelUsage 保存在 outside-review-result.json。

```tool-output
# 独立复核结论

老板，结论：**方向成立，可以进入 W01 实施**。但动手前有 4 件事要先写进卡片：

1. F01 的防护方式要换，不能按原方案做"祖先链校验"。
2. F03 应先查一条更便宜的修复路径。
3. F02 需要写明"强观察做不到时怎么办"的出口。
4. W01 部分关闭后，状态要能被 gate 识别。

其余原生发现基本成立。下面只列补充、纠偏和误报。

---

## 一、对原生发现的挑战

**F01（成立，但修复方案有隐患）**
- **祖先链防护会误伤后续合法对象。** W07 的"并行候选不写当前指针"会产生不在 current 祖先链上的合法 revision。按祖先链拒读，W07 落地后就得回头改 W01，形成反向依赖。
- **建议改用"已提交 revision 登记"作为合法性来源**，由 `commit_change` 写入的日志或索引提供。配套做三件事：
  - revision_id 严格字符集校验，拒绝 `/`、`..` 以及空值。
  - `resolve()` 后必须位于 `revisions_dir` 内，且拒绝 symlink。
  - 快照内容与本项目身份绑定。
- **待核实：** 快照里是否已有 project_id。原生证据只显示校验了 `revision_id`。如果没有 project_id，"foreign 同名快照"只能靠登记表挡住，不能靠内容字段。
- **分类问题：** F01 里"损坏 review 导致 project_view 崩溃"与 revision 转发无关，应并入 F04。否则 P1 修复范围被放大，验收也会混在一起。

**F03（成立，但可能不需要新建"基础设施"）**
- `commit_change(..., operation_id=...)`（`tasks.py:1154-1158`）已经把 operation_id 交给提交层。如果 revision 或 task 已持久化 `result_digest`，只需在 `tasks.py:860` 读不到 journal 时，按 operation_id 反查已提交的 revision 并补写 journal，就能消除 `tasks.py:875` 的误冲突。
- 这比先建一层"recoverable commit infrastructure"更小、更可验证。W02 入口应先确认这条路径是否可行，不行再升级方案。
- **漏掉的边界：** 在 `tasks.py:862`，只要 journal 存在且 task 已被 superseded，同一操作带着相同 digest 重试时，会先抛 `StaleInputContext`，而不是返回 `already_applied`。响应丢失后的重放因此不幂等。需要确认已完成的 task 是否可能后续被标记为 superseded。
- **性质：** 这是 main 上已有的缺陷，影响现有 CLI 的 accept 流程。应作为 W02 第一个独立核心 PR，不要和 ContentPlan、Attempt 捆在一起。

**F02（成立，但缺少否定出口）**
- Host（Codex）是外部执行者，Deck Master 本身不调用模型。"工具已观察/供应商回执"的前提有两个：
  - Host 必须经由 Deck Master 提供的采集器发起调用。
  - 签名必须能用登记过的密钥验证。只检查字段存在，等于没有签名。
- 供应商很可能不回传可验证的回执。因此 spike 的结论必须允许"强级别不可达"。此时 W05 只展示"已冻结 / Host申报"，W05 的 AC 要按这一结果可以关闭，不能让 W05 卡死。
- 真实 Host gate 依然必需。要写明 Host 不可用时的停止条件，而不是用模拟数据放行。

**F04（成立，补充位置）**
- 同一循环里还有几处硬崩点：`view.py:83` 的 `e['page_id']` / `e['page']`，`view.py:84` 的 `document['outputs']`（旧项目可能没有这个字段），以及 `reviewer` 不是 dict 时的 `.get`。
- 失败要按层降级（fail-closed），但整页 view 不能因此返回 500。

**F05（成立，需要确认 AC 归属）**
- 方案表把"300页多候选/Attempt压力"写在 **W04** 行，原生审查说在 **W01-AC01**。需要核对 AC 矩阵，防止同一 AC 被两个卡片各自当成对方的责任。
- "slice 合入但 AC01 未关"必须有显式状态，例如 `slice-merged / AC-open`。W03、W04 的前置条件写"依赖 W01 slice"，而不是"依赖 W01 关闭"。否则"一次只推进一卡"的 gate 会自己锁死。
- 300 页数据应通过真实核心 API 批量生成 fixture，不要手写 JSON。

**F06（部分为误报风险）**
- 方案 W01 的触达文件是 `view.py/service.py/web.py`，**不含 `cli.py`**。
- 如果没有 AC 要求 CLI 按 revision/page 读取，最小修复是订正 DX-SPEC，说明 `view --json` 实际返回的是服务状态，而不是新增 3 个 flag。
- 如果 AC 确实要求，再加 flag。同时要定义清楚：`--revision` 与 `--open` 同时出现时是否互斥；不带 `--json` 时的行为。

## 二、新增发现

1. **代码基线过期。** 方案写的基线是 `cad56e0`，原生审查基于 `d1c7c46`，中间的 `3e1c706` 改了页数限制和旧 ppt 链接迁移。CODE-BASELINE 需要重新对齐，否则 W01 对旧项目的兼容判断会有偏差。
2. **W02 过大。** 按现在的描述，W02 要承载：恢复修复、观察 spike、ContentPlan/SourceLink、GenerationRequest/Attempt、公共 Skill 契约。在"一次一卡"的节奏下，它会成为单点堵塞。建议在卡内拆成串行 PR：
   - (a) journal 恢复
   - (b) 观察 spike 与决策
   - (c) Request/Attempt
   - (d) ContentPlan

   AC 归属不变。
3. **里程碑顺序已被新序列改变。** 方案定义 M1a = W01/W03/W04，但新序列让 W02 先于 W03 执行，M1a 实际要等到 W02 之后才可见。需要在方案里记下这一变化，避免有人按原 M1a 期望提前做前端演示。
4. **revision 参数要贯穿所有读路径。** `/api/pages/{id}`（`web.py:170`）和 `/api/tasks`（`web.py:184`）固定读当前 revision。如果 W01 只在 `/api/workbench` 支持 `?revision=`，用户在历史版本里点进单页会静默跳到当前版本，违反"固定版本对照不追随后台更新"。

## 三、证据边界

- 方案在 §7.1 之后被截断，完成条件和后续卡片细节我没有看到。
- AC 矩阵原文未提供，F05/F06 的归属判断基于转述。
- `commit_change` 的实现，以及快照是否包含 project_id 和 result_digest，都没有直接证据。以上相关结论均为待核实。

---

Recommendation: **启动 W01 核心 slice。开工前把 revision 防护改为"已提交登记 + 路径/symlink 校验"，并把 W02 首个 PR 定为基于已有 operation_id 的 journal 恢复**，因为祖先链方案会与 W07 的并行候选冲突，而 `commit_change` 已经接收 operation_id，大概率可以用更小的改动修复 `tasks.py:875` 的误冲突，不必先建一层新的基础设施。
```

## 主审取舍

采用：全读路由 revision 贯通、基线刷新、W02 包内串行 PR、分段 gate、CLI --open 互斥。

纠正：活动 Document 必含 project_id/outputs；Candidate 不是离线 Document revision，不新增提交注册表。由此补 F07，明确管理 revision 可前进但采用槽不变。当前已提交任务不因普通过期变成 superseded（相关分支只处理未终结任务）；该假设不另报 bug。operation_id 没有原 digest/稳定结果不能安全重建旧回执；继续原 Store 最小原语。工具实际观察不必须新增代理，供应商签名也不是唯一允许证据。不能放宽 W02-AC07 或真实 Host 闸门。CLI 新读选项在 DX§3 已明确承诺，纳入 W01。
