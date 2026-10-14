# RC3-01-S01 独立核心复审：第二轮

结论：**REQUEST_CHANGES**。F-S01-01 已修复；另有合法整稿 finding 的 closure 出口缺失。

- 固定候选：`e1d42878093382254507448732ac0b1c6052a0ba`。
- 第一轮候选：`5deb222c77cadbdb835c695b17224d4e312d2395`。
- 原方法候选：`1fb3ddacbb75a2d891b5a14d955cf23db9460931`。
- 独立执行者：`/root/rc3_01_code_review`。
- 日期：2026-10-14 UTC；专用 env-01 模块来源为本卡 src。
- 范围：追加提交三文件，以及完整 S01 三 core/tests/report 链。没有改产品代码、实际模型运行、安装、merge、原 A/B 首轮或并行 METHODS/ledger/anchor 文档。

## F-S01-01 复核：已关闭

当前 pass freshness 与历史 finding 存续已分开。历史完整 preproduction records 用于中央 `finding_closed`，当前 pass 仍须绑定当前全稿；当前页面/required unit 内的开放 finding 不因同页、页外正文或 notes 变化失踪。当前合法退役页、P2 子范围以及不再要求的 speech unit 按适用范围过滤，历史原件仍保留。

独立运行同组回归：**130 passed in 7.61s**，涵盖原 118 项和新增 12 项正式 API 路径。审查了多步 stale replaces 链→当前同页 fixed 的正例，没有仅复制当前 pass 清旧 finding 的逻辑。

## F-S01-02（P1）：合法整稿 finding 没有可接纳的关闭出口

`review.v1.schema.json` 和 v2 的 finding `page_id` 明确允许 null。第二轮 gate 也专门保留非空当前范围内的 deck-level finding。然而中央 `finding_closed` 仍要求 `content:page:None` 依赖、current_page_subject(page_id=None) 及 same-page 变更，这些无法由合法当前 Page 满足。

独立正式 synthetic L1 重现：

1. `_deck` 创建两页训练稿，`_publish` 正式接纳一个 argument 单位的 `needs_review`。finding=`global-uncertainty`、impact=`needs_judgment`、page_id=null、element_refs=[]，对象为“全稿实测收益未知，需要确认该不确定性是否诚实保留”。初始结果 accepted。
2. 新正式 review 保留同一 review_id/kind=argument/stage=preproduction、显式 replaces 原 ref、相同 finding_id/page_id=null，并提交 `accepted_variance`、具体理由“全文明确未实测收益，条件性机制已限定；不补造数据”。当前完整 subjects/dependencies、observations、真实存储 evidence 和 synthetic 独立 receipt 均保留。
3. receiver 拒绝：`review/replaces: finding 'global-uncertainty' is not closed by a current same-page product, dependencies and evidence`。
4. 新普通 pass 没有替换不能关闭旧项，当前 status=blocked。这个“阻塞而没有合法解决动作”的结果不是通过。

中央 null 限制是既有行为；S01 新全历史存续要求使合法 null 项也必须有正式复核出口，不能靠删历史或恢复“改别页就忘掉”绕过。应限定在 preproduction 下处理合法整稿 finding：当前全稿/Narrative/Plan 绑定、完整依赖、observations/evidence 和显式同逻辑 replaces 均保留；variance 仍仅限 needs_judgment 并要具体理由，fixed 要能证明当前所审内容真实变化。final/page_visual 的当前输出/preview 条件不得放宽。增加 null variance/fixed 正例和无变更、缺当前绑定/证据、must_fix→variance 等反例。

第一轮报告及当时结果保持原版本。当前未签 merge PASS；等待主控归属并由 owner 修复后，再按新准确 SHA 复审。

上述仅为代码/L1 证据，不代替新安装实际生成、独立模型效果、Owner/受众、真实试讲或桌面文件验收。
