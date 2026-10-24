# Unified issue acceptance index

Baseline: 51 recorded issues plus #186 = 52. This is an evidence map, not blanket acceptance. The second reported new issue remains unidentified; API access was Forbidden.

| Issue | Owner | Historical report | Final status |
| --- | --- | --- | --- |
| #132 [WebUI 整改] 内容工作面瀑布堆叠、操作入口过载及完成/空状态误导 | RP-22 | [report](../../..//docs/reports/issue-repair-20261023/RP-22.md), [report](../../..//docs/reports/issue-repair-20261023/RP-22-deep-quality-browser-followup.md) | Pending final integrated verification / unmet real evidence |
| #133 [WebUI Bug] 内容计划缺少可视化编辑，表单直接显示 [object HTMLElement] | RP-10 | [report](../../..//docs/reports/issue-repair-20261023/RP-10.md) | Pending final integrated verification / unmet real evidence |
| #134 [Skill UX] deck-master 退出时未明确当前状态，缺少 deck-content 下一步交接与决策引导 | RP-24 | [report](../../..//docs/reports/issue-repair-20261023/RP-24-cross-execution-evidence.md), [report](../../..//docs/reports/issue-repair-20261023/RP-24-settled-reuse.md), [report](../../..//docs/reports/issue-repair-20261023/RP-24.md) | Pending final integrated verification / unmet real evidence |
| #135 [Content UX] 规划交付缺少决策协作：方法应用说明、方案取舍、审阅问题与可选追问未闭环 | RP-24 | [report](../../..//docs/reports/issue-repair-20261023/RP-24-cross-execution-evidence.md), [report](../../..//docs/reports/issue-repair-20261023/RP-24-settled-reuse.md), [report](../../..//docs/reports/issue-repair-20261023/RP-24.md) | Pending final integrated verification / unmet real evidence |
| #136 [WebUI UX] 正文完成后缺少可发现的制作推进入口，提示词/原图/SVG 工作链停留在结果查看 | RP-21 | [report](../../..//docs/reports/issue-repair-20261023/RP-21.md) | Pending final integrated verification / unmet real evidence |
| #137 [Agent UX] 独立审查能力发现不清，Host 将回执能力未配置误判为没有审查通道 | RP-01 | [report](../../..//docs/reports/issue-repair-20261023/RP-01.md), [report](../../..//docs/reports/issue-repair-20261023/RP-01-startup-diagnostics.md) | Pending final integrated verification / unmet real evidence |
| #138 [Bug] 原生独立复审结果接纳失败：无 finding 的通过记录无法替换，重试重复执行审查 | RP-11 | [report](../../..//docs/reports/issue-repair-20261023/RP-11.md) | Pending final integrated verification / unmet real evidence |
| #139 [Bug] V3 样页候选已生成，但详情读取错误使用参考预览，导致比较入口拒绝显示 | RP-00 | [report](../../..//docs/reports/issue-repair-20261023/RP-00.md) | Pending final integrated verification / unmet real evidence |
| #140 [P1][WebUI] 项目读取耗时约19秒，切换工作面长期保留旧页且缺少就近恢复 | RP-25 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #141 [P1][Design UX] 首次原图试作入口未呈现视觉方向依据与确认状态，和风格规划流程脱节 | RP-21 | [report](../../..//docs/reports/issue-repair-20261023/RP-21.md) | Pending final integrated verification / unmet real evidence |
| #142 [P1][Performance] 控制状态轮询重复读取项目且请求重叠，巡检空闲期两个服务持续占用约2个CPU核心 | RP-25 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #143 [P2][WebUI] 无主线导入稿的证据区将主线绑定缺失写成原子映射缺失，与逐项“已记录映射”冲突 | RP-10 | [report](../../..//docs/reports/issue-repair-20261023/RP-10.md) | Pending final integrated verification / unmet real evidence |
| #144 [P2][Review] 仅口播审查失效仍强制重做全部前审单元，已有有效结论不能复用 | RP-12 | [report](../../..//docs/reports/issue-repair-20261023/RP-12.md) | Pending final integrated verification / unmet real evidence |
| #145 [P2][Performance] 图标候选列表逐项重跑全体候选验证，单次读取形成二次增长 | RP-26 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #146 [P2][Performance] 待协调输入说明循环重新验证历史可达性，热读仍为二次遍历 | RP-29 | [report](../../..//docs/reports/issue-repair-20261023/RP-29.md) | Pending final integrated verification / unmet real evidence |
| #148 [P2][Eligibility] 零调用正文候选被制作前审门禁阻断，待纠正稿必须先通过旧稿前审 | RP-02 | [report](../../..//docs/reports/issue-repair-20261023/RP-02.md) | Pending final integrated verification / unmet real evidence |
| #149 [P2][Delivery] 未采用的零调用试作使当前成稿审查失效并阻断交接 | RP-03 | [report](../../..//docs/reports/issue-repair-20261023/RP-03.md) | Pending final integrated verification / unmet real evidence |
| #150 [P2][Recovery] 已提交操作的精确恢复先被当前暂停门禁拒绝，要求无意义地恢复写权限 | RP-04 | [report](../../..//docs/reports/issue-repair-20261023/RP-04.md) | Pending final integrated verification / unmet real evidence |
| #151 [P2][Performance] 逐页组装门禁为同一快照重复构建全稿依赖与历史摘要 | RP-27 | [report](../../..//docs/reports/issue-repair-20261023/RP-27.md) | Pending final integrated verification / unmet real evidence |
| #152 [P2][Pipeline] 已有有效SVG预览仍逐页重渲染并丢弃输出，无用渲染失败可阻断组装 | RP-05 | [report](../../..//docs/reports/issue-repair-20261023/RP-05.md), [report](../../..//docs/reports/issue-repair-20261023/RP-05-RP-25-followup.md) | Pending final integrated verification / unmet real evidence |
| #153 [P2][Performance] 冻结单个候选检查经四次公共文件读取重建上下文与整包哈希五轮 | RP-28 | [report](../../..//docs/reports/issue-repair-20261023/RP-28.md) | Pending final integrated verification / unmet real evidence |
| #154 [P3][Recovery] 个人备份列表逐项重读同一清理日志并重复遍历项目祖先 | RP-29 | [report](../../..//docs/reports/issue-repair-20261023/RP-29.md) | Pending final integrated verification / unmet real evidence |
| #155 [P3][Review] 同一页同一finding闭合判断重复两遍，每次重建相同历史替换索引 | RP-27 | [report](../../..//docs/reports/issue-repair-20261023/RP-27.md) | Pending final integrated verification / unmet real evidence |
| #156 [P2][Performance] 变更列表逐项生成完整交接并重新扫描同一变更/任务集合 | RP-26 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #157 [P2][Performance] 严格专业策略的交付资格读取重复构建同一快照依赖图三次 | RP-27 | [report](../../..//docs/reports/issue-repair-20261023/RP-27.md) | Pending final integrated verification / unmet real evidence |
| #158 [P3][Recovery] 已存在正确索引的操作查询仍每次原子重写并fsync同一回执索引 | RP-29 | [report](../../..//docs/reports/issue-repair-20261023/RP-29.md) | Pending final integrated verification / unmet real evidence |
| #159 [P2][Performance] 轮询读取未共享快照与任务事实：轻量控制四次加载、个人摘要三次加载 | RP-26 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #160 [P2][Performance] 历史分页每页完整解析 head 到 cursor 的前缀，遍历全史形成二次工作 | RP-29 | [report](../../..//docs/reports/issue-repair-20261023/RP-29.md) | Pending final integrated verification / unmet real evidence |
| #161 [P3][Performance] 单页 lineage 的三个子投影重复扫描同一任务集合 | RP-26 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #162 [P1][Design] 内容表格被固化为成品版式，设计交接未区分约定排版与模型自主设计 | RP-17 | [report](../../..//docs/reports/issue-repair-20261023/RP-17.md) | Pending final integrated verification / unmet real evidence |
| #163 [P2][Skill] 设计方法派发三套口径不一致：blueprint 3 项、design 角色 7 项、design phase 缺 content-to-visual | RP-18 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #164 [P2][Review] 视觉审查缺表达质量维度：visual_expression 已入合同但不可选/未实现，page_visual 仍只复用三维 | RP-20 | [report](../../..//docs/reports/issue-repair-20261023/RP-20.md) | Pending final integrated verification / unmet real evidence |
| #165 [P2][Design] 项目级 layout_notes 与逐页设计指令冲突无检测：新样页 prompt 同时要求“不用表格”和“完整保留表格归属” | RP-17 | [report](../../..//docs/reports/issue-repair-20261023/RP-17.md) | Pending final integrated verification / unmet real evidence |
| #166 [P2][Contract] new_design 允许零视觉结构：visual_spec/layout_hint 无最小完整性校验，表格正文仍可派发生图 | RP-17 | [report](../../..//docs/reports/issue-repair-20261023/RP-17.md) | Pending final integrated verification / unmet real evidence |
| #167 [P2][Skill] 合法 Page 正文候选任务被 Content reader 错拒，Design 却接受 | RP-02 | [report](../../..//docs/reports/issue-repair-20261023/RP-02.md) | Pending final integrated verification / unmet real evidence |
| #168 [P2][Skill] 自然复合请求误选单一职责后，拒绝正确的 Master 协调入口 | RP-06 | [report](../../..//docs/reports/issue-repair-20261023/RP-06-X2.md), [report](../../..//docs/reports/issue-repair-20261023/RP-06.md) | Pending final integrated verification / unmet real evidence |
| #169 [P2][Workflow] 纯设计方案已完成仍无职责终态，continue 误索要正文或蓝图生产权限 | RP-06 | [report](../../..//docs/reports/issue-repair-20261023/RP-06-X2.md), [report](../../..//docs/reports/issue-repair-20261023/RP-06.md) | Pending final integrated verification / unmet real evidence |
| #170 [P2][WebUI] 方法准备选择口播审阅，实际发送不含 speech 的三项正文审查范围 | RP-18 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #171 [P2][Skill UX] 方法准备交接只复制显式ID和不可恢复摘要，丢失角色阶段与范围 | RP-18 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #172 [P3][WebUI] 项目模式无新阶段时隐藏31项只读方法，混用浏览与派发条件 | RP-18 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #173 [P1][Pipeline] 上传、设计资产与生产消费未贯通，Logo和模板缺少可用的制作链路 | RP-19 | [report](../../..//docs/reports/issue-repair-20261023/RP-19.md) | Pending final integrated verification / unmet real evidence |
| #174 [P1][Content] 内部来源误作上屏默认，客户表达与证据追溯未分层 | RP-16 | [report](../../..//docs/reports/issue-repair-20261023/RP-16.md) | Pending final integrated verification / unmet real evidence |
| #175 [P2][Skill] 改进后完整稿保留作者自证和坏稿错误数字，正例污染客户表达 | RP-13 | [report](../../..//docs/reports/issue-repair-20261023/RP-13.md) | Pending final integrated verification / unmet real evidence |
| #176 [P2][Skill] 无收益数据规则未按主张和用途限定，泛化要求假设与测量办法 | RP-13 | [report](../../..//docs/reports/issue-repair-20261023/RP-13.md) | Pending final integrated verification / unmet real evidence |
| #177 [P3][Skill] “删字不是修复”与M10删冗方法矛盾，完整性指导缺少语义边界 | RP-13 | [report](../../..//docs/reports/issue-repair-20261023/RP-13.md) | Pending final integrated verification / unmet real evidence |
| #178 [P2][Review] 独立内容前审包未展开当前请求与适用协作决定 | RP-14 | [report](../../..//docs/reports/issue-repair-20261023/RP-14.md) | Pending final integrated verification / unmet real evidence |
| #179 [P2][Review] 内容前审缺客户可见语域维度，失败项只罚藏限定不罚内部证据上屏 | RP-16 | [report](../../..//docs/reports/issue-repair-20261023/RP-16.md) | Pending final integrated verification / unmet real evidence |
| #180 [P2][Contract] content_profile / required_qualifications 无定义语义却被投影为设计上屏要求 | RP-15 | [report](../../..//docs/reports/issue-repair-20261023/RP-15.md) | Pending final integrated verification / unmet real evidence |
| #181 [P2][WebUI] 已记录的 v3 初始设计规范被风格工作面静默过滤 | RP-09 | No separate owner report found | Pending final integrated verification / unmet real evidence |
| #182 [P2][WebUI] 总览把历史失败与被接续任务作为当前优先待办，目标列表缺少辨识信息 | RP-08 | [report](../../..//docs/reports/issue-repair-20261023/RP-08.md) | Pending final integrated verification / unmet real evidence |
| #183 [P2] 单任务领取/接纳回执展开全部待办工作正文，重复携带完整材料 | RP-07 | [report](../../..//docs/reports/issue-repair-20261023/RP-07.md) | Pending final integrated verification / unmet real evidence |
| #186 外部报告 finding 接续返修 | PR187-186 | [report](../../..//docs/reports/pr187-followups/issue-186.md) | Pending final integrated verification / unmet real evidence |
