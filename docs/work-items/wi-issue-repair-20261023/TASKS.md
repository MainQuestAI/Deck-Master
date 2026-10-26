# 可执行任务清单

所有卡为 planned，顺序是建议交付顺序；依赖是完整验收前置，静态分析与可独立实现的片段可先开展。RP-23 是诊断前置，可从第一批开始。RP 编号不复用历史 T1–T9、T01–T25 或 W01–W12。

|任务|范围 / 唯一负责 Issue|依赖|批次|
|---|---|---|---|
|[RP-00](task-cards/RP-00.md) 回收已有窄修复并建立可复验安装基线|[#139](https://github.com/MainQuestAI/Deck-Master/issues/139)|无|0 已有修复正规化|
|[RP-01](task-cards/RP-01.md) 按阶段发现独立审查通道|[#137](https://github.com/MainQuestAI/Deck-Master/issues/137)|无|1 主链恢复|
|[RP-02](task-cards/RP-02.md) 修复零调用正文候选的完整职责链|[#148](https://github.com/MainQuestAI/Deck-Master/issues/148)、[#167](https://github.com/MainQuestAI/Deck-Master/issues/167)|无|1 主链恢复|
|[RP-03](task-cards/RP-03.md) 隔离未采用旁支对当前稿的阻塞|[#149](https://github.com/MainQuestAI/Deck-Master/issues/149)|[RP-02](task-cards/RP-02.md)|1 主链恢复|
|[RP-04](task-cards/RP-04.md) 统一精确操作重放与暂停门禁顺序|[#150](https://github.com/MainQuestAI/Deck-Master/issues/150)|[RP-00](task-cards/RP-00.md)|1 主链恢复|
|[RP-05](task-cards/RP-05.md) 去掉组装前弃用的重复 SVG 渲染|[#152](https://github.com/MainQuestAI/Deck-Master/issues/152)|无|1 主链恢复|
|[RP-06](task-cards/RP-06.md) 复合意图路由与纯设计完成语义|[#168](https://github.com/MainQuestAI/Deck-Master/issues/168)、[#169](https://github.com/MainQuestAI/Deck-Master/issues/169)|无|1 主链恢复|
|[RP-07](task-cards/RP-07.md) 将单任务变更响应收敛为紧凑回执|[#183](https://github.com/MainQuestAI/Deck-Master/issues/183)|无|1 主链恢复（新增前移）|
|[RP-08](task-cards/RP-08.md) 按当前请求与依赖生成真正可行动的待办|[#182](https://github.com/MainQuestAI/Deck-Master/issues/182)|[RP-03](task-cards/RP-03.md)、[RP-06](task-cards/RP-06.md)|1 主链恢复（新增前移）|
|[RP-09](task-cards/RP-09.md) 展示和沿用 v1/v2/v3 设计规范|[#181](https://github.com/MainQuestAI/Deck-Master/issues/181)|无|1 主链恢复（新增前移）|
|[RP-10](task-cards/RP-10.md) 修复内容计划编辑及来源状态表达|[#133](https://github.com/MainQuestAI/Deck-Master/issues/133)、[#143](https://github.com/MainQuestAI/Deck-Master/issues/143)|无|随模块交付：明确 UI 修复|
|[RP-11](task-cards/RP-11.md) 按失败阶段恢复可信独立审查结果|[#138](https://github.com/MainQuestAI/Deck-Master/issues/138)|[RP-00](task-cards/RP-00.md)、[RP-01](task-cards/RP-01.md)|2 客户表达闭环的审查支持|
|[RP-12](task-cards/RP-12.md) 只重审失效单元并保留其他有效结论|[#144](https://github.com/MainQuestAI/Deck-Master/issues/144)|[RP-11](task-cards/RP-11.md)|2 客户表达闭环的审查支持|
|[RP-13](task-cards/RP-13.md) 纠正写作规则与正例中的客户表达|[#175](https://github.com/MainQuestAI/Deck-Master/issues/175)、[#176](https://github.com/MainQuestAI/Deck-Master/issues/176)、[#177](https://github.com/MainQuestAI/Deck-Master/issues/177)|无|2 客户表达闭环|
|[RP-14](task-cards/RP-14.md) 把当前有效请求和决定送入审查|[#178](https://github.com/MainQuestAI/Deck-Master/issues/178)|无|2 客户表达闭环|
|[RP-15](task-cards/RP-15.md) 定义内容字段语义及客户可见消费边界|[#180](https://github.com/MainQuestAI/Deck-Master/issues/180)|无|2 客户表达闭环|
|[RP-16](task-cards/RP-16.md) 以受众语义审查完成客户表达闭环|[#174](https://github.com/MainQuestAI/Deck-Master/issues/174)、[#179](https://github.com/MainQuestAI/Deck-Master/issues/179)|[RP-11](task-cards/RP-11.md)、[RP-12](task-cards/RP-12.md)、[RP-13](task-cards/RP-13.md)、[RP-14](task-cards/RP-14.md)、[RP-15](task-cards/RP-15.md)|2 客户表达闭环|
|[RP-17](task-cards/RP-17.md) 统一两种设计策略与修订后的有效依据|[#162](https://github.com/MainQuestAI/Deck-Master/issues/162)、[#165](https://github.com/MainQuestAI/Deck-Master/issues/165)、[#166](https://github.com/MainQuestAI/Deck-Master/issues/166)|[RP-15](task-cards/RP-15.md)|3 设计与资产|
|[RP-18](task-cards/RP-18.md) 统一职责方法与可接手的方法准备|[#163](https://github.com/MainQuestAI/Deck-Master/issues/163)、[#170](https://github.com/MainQuestAI/Deck-Master/issues/170)、[#171](https://github.com/MainQuestAI/Deck-Master/issues/171)、[#172](https://github.com/MainQuestAI/Deck-Master/issues/172)|[RP-02](task-cards/RP-02.md)、[RP-06](task-cards/RP-06.md)|随模块交付：方法与交接|
|[RP-19](task-cards/RP-19.md) 贯通已支持品牌资产的真实生产消费|[#173](https://github.com/MainQuestAI/Deck-Master/issues/173)|[RP-17](task-cards/RP-17.md)|3 设计与资产|
|[RP-20](task-cards/RP-20.md) 在原图阶段检查表达质量与固定有向关系|[#164](https://github.com/MainQuestAI/Deck-Master/issues/164)|[RP-01](task-cards/RP-01.md)、[RP-11](task-cards/RP-11.md)、[RP-17](task-cards/RP-17.md)|3 设计与资产|
|[RP-21](task-cards/RP-21.md) 把真实设计依据接入样页和扩页入口|[#141](https://github.com/MainQuestAI/Deck-Master/issues/141)、[#136](https://github.com/MainQuestAI/Deck-Master/issues/136)|[RP-09](task-cards/RP-09.md)、[RP-17](task-cards/RP-17.md)、[RP-19](task-cards/RP-19.md)、[RP-20](task-cards/RP-20.md)|3 设计与资产|
|[RP-22](task-cards/RP-22.md) 按当前动作重排阅读和操作界面|[#132](https://github.com/MainQuestAI/Deck-Master/issues/132)|[RP-08](task-cards/RP-08.md)、[RP-10](task-cards/RP-10.md)、[RP-18](task-cards/RP-18.md)|4 整体体验验收|
|[RP-23](task-cards/RP-23.md) 核实跨用户轮次的受支持恢复路径|协同验收，不单独关闭 Issue|无|1 可提前独立诊断；支持 #134|
|[RP-24](task-cards/RP-24.md) 验证阶段退出、决策协作和实际职责交接|[#134](https://github.com/MainQuestAI/Deck-Master/issues/134)、[#135](https://github.com/MainQuestAI/Deck-Master/issues/135)|[RP-06](task-cards/RP-06.md)、[RP-18](task-cards/RP-18.md)、[RP-21](task-cards/RP-21.md)、[RP-23](task-cards/RP-23.md)|4 整体体验验收|
|[RP-25](task-cards/RP-25.md) 复测正式读取体验并收口轮询残项|[#140](https://github.com/MainQuestAI/Deck-Master/issues/140)、[#142](https://github.com/MainQuestAI/Deck-Master/issues/142)|[RP-00](task-cards/RP-00.md)|随基线交付：现场性能|
|[RP-26](task-cards/RP-26.md) 共享高频读取中的候选与任务事实|[#159](https://github.com/MainQuestAI/Deck-Master/issues/159)、[#145](https://github.com/MainQuestAI/Deck-Master/issues/145)、[#156](https://github.com/MainQuestAI/Deck-Master/issues/156)、[#161](https://github.com/MainQuestAI/Deck-Master/issues/161)|[RP-07](task-cards/RP-07.md)、[RP-08](task-cards/RP-08.md)|5 后续性能批次 A|
|[RP-27](task-cards/RP-27.md) 复用组装与交付依赖图及 finding 索引|[#151](https://github.com/MainQuestAI/Deck-Master/issues/151)、[#157](https://github.com/MainQuestAI/Deck-Master/issues/157)、[#155](https://github.com/MainQuestAI/Deck-Master/issues/155)|[RP-11](task-cards/RP-11.md)|5 后续性能批次 B|
|[RP-28](task-cards/RP-28.md) 冻结检查时复用同批已验证字节|[#153](https://github.com/MainQuestAI/Deck-Master/issues/153)|[RP-17](task-cards/RP-17.md)|5 后续性能批次 C|
|[RP-29](task-cards/RP-29.md) 收敛历史读取和恢复的重复工作|[#146](https://github.com/MainQuestAI/Deck-Master/issues/146)、[#160](https://github.com/MainQuestAI/Deck-Master/issues/160)、[#158](https://github.com/MainQuestAI/Deck-Master/issues/158)、[#154](https://github.com/MainQuestAI/Deck-Master/issues/154)|无|5 后续性能批次 D|
|[RP-30](task-cards/RP-30.md) 执行跨合同兼容和代表流程联合验收|协同验收，不单独关闭 Issue|[RP-04](task-cards/RP-04.md)、[RP-05](task-cards/RP-05.md)、[RP-16](task-cards/RP-16.md)、[RP-20](task-cards/RP-20.md)、[RP-21](task-cards/RP-21.md)、[RP-22](task-cards/RP-22.md)、[RP-24](task-cards/RP-24.md)、[RP-25](task-cards/RP-25.md)、[RP-26](task-cards/RP-26.md)、[RP-27](task-cards/RP-27.md)、[RP-28](task-cards/RP-28.md)、[RP-29](task-cards/RP-29.md)|6 联合验收|

## 51 项归属

|Issue|题目|唯一负责卡|本轮正文同步|
|---|---|---|---|
|[#132](https://github.com/MainQuestAI/Deck-Master/issues/132)|[WebUI 整改] 内容工作面瀑布堆叠、操作入口过载及完成/空状态误导|[RP-22](task-cards/RP-22.md)|更新本轮修订及验收|
|[#133](https://github.com/MainQuestAI/Deck-Master/issues/133)|[WebUI Bug] 内容计划缺少可视化编辑，表单直接显示 [object HTMLElement]|[RP-10](task-cards/RP-10.md)|保留原案；本基准汇总任务归属|
|[#134](https://github.com/MainQuestAI/Deck-Master/issues/134)|[Skill UX] deck-master 退出时未明确当前状态，缺少 deck-content 下一步交接与决策引导|[RP-24](task-cards/RP-24.md)|更新本轮修订及验收|
|[#135](https://github.com/MainQuestAI/Deck-Master/issues/135)|[Content UX] 规划交付缺少决策协作：方法应用说明、方案取舍、审阅问题与可选追问未闭环|[RP-24](task-cards/RP-24.md)|保留原案；本基准汇总任务归属|
|[#136](https://github.com/MainQuestAI/Deck-Master/issues/136)|[WebUI UX] 正文完成后缺少可发现的制作推进入口，提示词/原图/SVG 工作链停留在结果查看|[RP-21](task-cards/RP-21.md)|更新本轮修订及验收|
|[#137](https://github.com/MainQuestAI/Deck-Master/issues/137)|[Agent UX] 独立审查能力发现不清，Host 将回执能力未配置误判为没有审查通道|[RP-01](task-cards/RP-01.md)|更新本轮修订及验收|
|[#138](https://github.com/MainQuestAI/Deck-Master/issues/138)|[Bug] 原生独立复审结果接纳失败：无 finding 的通过记录无法替换，重试重复执行审查|[RP-11](task-cards/RP-11.md)|更新本轮修订及验收|
|[#139](https://github.com/MainQuestAI/Deck-Master/issues/139)|[Bug] V3 样页候选已生成，但详情读取错误使用参考预览，导致比较入口拒绝显示|[RP-00](task-cards/RP-00.md)|保留原案；本基准汇总任务归属|
|[#140](https://github.com/MainQuestAI/Deck-Master/issues/140)|[P1][WebUI] 项目读取耗时约19秒，切换工作面长期保留旧页且缺少就近恢复|[RP-25](task-cards/RP-25.md)|保留原案；本基准汇总任务归属|
|[#141](https://github.com/MainQuestAI/Deck-Master/issues/141)|[P1][Design UX] 首次原图试作入口未呈现视觉方向依据与确认状态，和风格规划流程脱节|[RP-21](task-cards/RP-21.md)|更新本轮修订及验收|
|[#142](https://github.com/MainQuestAI/Deck-Master/issues/142)|[P1][Performance] 控制状态轮询重复读取项目且请求重叠，巡检空闲期两个服务持续占用约2个CPU核心|[RP-25](task-cards/RP-25.md)|保留原案；本基准汇总任务归属|
|[#143](https://github.com/MainQuestAI/Deck-Master/issues/143)|[P2][WebUI] 无主线导入稿的证据区将主线绑定缺失写成原子映射缺失，与逐项“已记录映射”冲突|[RP-10](task-cards/RP-10.md)|保留原案；本基准汇总任务归属|
|[#144](https://github.com/MainQuestAI/Deck-Master/issues/144)|[P2][Review] 仅口播审查失效仍强制重做全部前审单元，已有有效结论不能复用|[RP-12](task-cards/RP-12.md)|更新本轮修订及验收|
|[#145](https://github.com/MainQuestAI/Deck-Master/issues/145)|[P2][Performance] 图标候选列表逐项重跑全体候选验证，单次读取形成二次增长|[RP-26](task-cards/RP-26.md)|保留原案；本基准汇总任务归属|
|[#146](https://github.com/MainQuestAI/Deck-Master/issues/146)|[P2][Performance] 待协调输入说明循环重新验证历史可达性，热读仍为二次遍历|[RP-29](task-cards/RP-29.md)|保留原案；本基准汇总任务归属|
|[#148](https://github.com/MainQuestAI/Deck-Master/issues/148)|[P2][Eligibility] 零调用正文候选被制作前审门禁阻断，待纠正稿必须先通过旧稿前审|[RP-02](task-cards/RP-02.md)|更新本轮修订及验收|
|[#149](https://github.com/MainQuestAI/Deck-Master/issues/149)|[P2][Delivery] 未采用的零调用试作使当前成稿审查失效并阻断交接|[RP-03](task-cards/RP-03.md)|保留原案；本基准汇总任务归属|
|[#150](https://github.com/MainQuestAI/Deck-Master/issues/150)|[P2][Recovery] 已提交操作的精确恢复先被当前暂停门禁拒绝，要求无意义地恢复写权限|[RP-04](task-cards/RP-04.md)|更新本轮修订及验收|
|[#151](https://github.com/MainQuestAI/Deck-Master/issues/151)|[P2][Performance] 逐页组装门禁为同一快照重复构建全稿依赖与历史摘要|[RP-27](task-cards/RP-27.md)|保留原案；本基准汇总任务归属|
|[#152](https://github.com/MainQuestAI/Deck-Master/issues/152)|[P2][Pipeline] 已有有效SVG预览仍逐页重渲染并丢弃输出，无用渲染失败可阻断组装|[RP-05](task-cards/RP-05.md)|保留原案；本基准汇总任务归属|
|[#153](https://github.com/MainQuestAI/Deck-Master/issues/153)|[P2][Performance] 冻结单个候选检查经四次公共文件读取重建上下文与整包哈希五轮|[RP-28](task-cards/RP-28.md)|保留原案；本基准汇总任务归属|
|[#154](https://github.com/MainQuestAI/Deck-Master/issues/154)|[P3][Recovery] 个人备份列表逐项重读同一清理日志并重复遍历项目祖先|[RP-29](task-cards/RP-29.md)|保留原案；本基准汇总任务归属|
|[#155](https://github.com/MainQuestAI/Deck-Master/issues/155)|[P3][Review] 同一页同一finding闭合判断重复两遍，每次重建相同历史替换索引|[RP-27](task-cards/RP-27.md)|保留原案；本基准汇总任务归属|
|[#156](https://github.com/MainQuestAI/Deck-Master/issues/156)|[P2][Performance] 变更列表逐项生成完整交接并重新扫描同一变更/任务集合|[RP-26](task-cards/RP-26.md)|保留原案；本基准汇总任务归属|
|[#157](https://github.com/MainQuestAI/Deck-Master/issues/157)|[P2][Performance] 严格专业策略的交付资格读取重复构建同一快照依赖图三次|[RP-27](task-cards/RP-27.md)|保留原案；本基准汇总任务归属|
|[#158](https://github.com/MainQuestAI/Deck-Master/issues/158)|[P3][Recovery] 已存在正确索引的操作查询仍每次原子重写并fsync同一回执索引|[RP-29](task-cards/RP-29.md)|保留原案；本基准汇总任务归属|
|[#159](https://github.com/MainQuestAI/Deck-Master/issues/159)|[P2][Performance] 轮询读取未共享快照与任务事实：轻量控制四次加载、个人摘要三次加载|[RP-26](task-cards/RP-26.md)|保留原案；本基准汇总任务归属|
|[#160](https://github.com/MainQuestAI/Deck-Master/issues/160)|[P2][Performance] 历史分页每页完整解析 head 到 cursor 的前缀，遍历全史形成二次工作|[RP-29](task-cards/RP-29.md)|保留原案；本基准汇总任务归属|
|[#161](https://github.com/MainQuestAI/Deck-Master/issues/161)|[P3][Performance] 单页 lineage 的三个子投影重复扫描同一任务集合|[RP-26](task-cards/RP-26.md)|保留原案；本基准汇总任务归属|
|[#162](https://github.com/MainQuestAI/Deck-Master/issues/162)|[P1][Design] 内容表格被固化为成品版式，设计交接未区分约定排版与模型自主设计|[RP-17](task-cards/RP-17.md)|更新本轮修订及验收|
|[#163](https://github.com/MainQuestAI/Deck-Master/issues/163)|[P2][Skill] 设计方法派发三套口径不一致：blueprint 3 项、design 角色 7 项、design phase 缺 content-to-visual|[RP-18](task-cards/RP-18.md)|更新本轮修订及验收|
|[#164](https://github.com/MainQuestAI/Deck-Master/issues/164)|[P2][Review] 视觉审查缺表达质量维度：visual_expression 已入合同但不可选/未实现，page_visual 仍只复用三维|[RP-20](task-cards/RP-20.md)|更新本轮修订及验收|
|[#165](https://github.com/MainQuestAI/Deck-Master/issues/165)|[P2][Design] 项目级 layout_notes 与逐页设计指令冲突无检测：新样页 prompt 同时要求“不用表格”和“完整保留表格归属”|[RP-17](task-cards/RP-17.md)|更新本轮修订及验收|
|[#166](https://github.com/MainQuestAI/Deck-Master/issues/166)|[P2][Contract] new_design 允许零视觉结构：visual_spec/layout_hint 无最小完整性校验，表格正文仍可派发生图|[RP-17](task-cards/RP-17.md)|更新本轮修订及验收|
|[#167](https://github.com/MainQuestAI/Deck-Master/issues/167)|[P2][Skill] 合法 Page 正文候选任务被 Content reader 错拒，Design 却接受|[RP-02](task-cards/RP-02.md)|更新本轮修订及验收|
|[#168](https://github.com/MainQuestAI/Deck-Master/issues/168)|[P2][Skill] 自然复合请求误选单一职责后，拒绝正确的 Master 协调入口|[RP-06](task-cards/RP-06.md)|保留原案；本基准汇总任务归属|
|[#169](https://github.com/MainQuestAI/Deck-Master/issues/169)|[P2][Workflow] 纯设计方案已完成仍无职责终态，continue 误索要正文或蓝图生产权限|[RP-06](task-cards/RP-06.md)|更新本轮修订及验收|
|[#170](https://github.com/MainQuestAI/Deck-Master/issues/170)|[P2][WebUI] 方法准备选择口播审阅，实际发送不含 speech 的三项正文审查范围|[RP-18](task-cards/RP-18.md)|保留原案；本基准汇总任务归属|
|[#171](https://github.com/MainQuestAI/Deck-Master/issues/171)|[P2][Skill UX] 方法准备交接只复制显式ID和不可恢复摘要，丢失角色阶段与范围|[RP-18](task-cards/RP-18.md)|保留原案；本基准汇总任务归属|
|[#172](https://github.com/MainQuestAI/Deck-Master/issues/172)|[P3][WebUI] 项目模式无新阶段时隐藏31项只读方法，混用浏览与派发条件|[RP-18](task-cards/RP-18.md)|保留原案；本基准汇总任务归属|
|[#173](https://github.com/MainQuestAI/Deck-Master/issues/173)|[P1][Pipeline] 上传、设计资产与生产消费未贯通，Logo和模板缺少可用的制作链路|[RP-19](task-cards/RP-19.md)|更新本轮修订及验收|
|[#174](https://github.com/MainQuestAI/Deck-Master/issues/174)|[P1][Content] 内部来源误作上屏默认，客户表达与证据追溯未分层|[RP-16](task-cards/RP-16.md)|更新本轮修订及验收|
|[#175](https://github.com/MainQuestAI/Deck-Master/issues/175)|[P2][Skill] 改进后完整稿保留作者自证和坏稿错误数字，正例污染客户表达|[RP-13](task-cards/RP-13.md)|更新本轮修订及验收|
|[#176](https://github.com/MainQuestAI/Deck-Master/issues/176)|[P2][Skill] 无收益数据规则未按主张和用途限定，泛化要求假设与测量办法|[RP-13](task-cards/RP-13.md)|更新本轮修订及验收|
|[#177](https://github.com/MainQuestAI/Deck-Master/issues/177)|[P3][Skill] “删字不是修复”与M10删冗方法矛盾，完整性指导缺少语义边界|[RP-13](task-cards/RP-13.md)|更新本轮修订及验收|
|[#178](https://github.com/MainQuestAI/Deck-Master/issues/178)|[P2][Review] 独立内容前审包未展开当前请求与适用协作决定|[RP-14](task-cards/RP-14.md)|更新本轮修订及验收|
|[#179](https://github.com/MainQuestAI/Deck-Master/issues/179)|[P2][Review] 内容前审缺客户可见语域维度，失败项只罚藏限定不罚内部证据上屏|[RP-16](task-cards/RP-16.md)|更新本轮修订及验收|
|[#180](https://github.com/MainQuestAI/Deck-Master/issues/180)|[P2][Contract] content_profile / required_qualifications 无定义语义却被投影为设计上屏要求|[RP-15](task-cards/RP-15.md)|更新本轮修订及验收|
|[#181](https://github.com/MainQuestAI/Deck-Master/issues/181)|[P2][WebUI] 已记录的 v3 初始设计规范被风格工作面静默过滤|[RP-09](task-cards/RP-09.md)|更新本轮修订及验收|
|[#182](https://github.com/MainQuestAI/Deck-Master/issues/182)|[P2][WebUI] 总览把历史失败与被接续任务作为当前优先待办，目标列表缺少辨识信息|[RP-08](task-cards/RP-08.md)|更新本轮修订及验收|
|[#183](https://github.com/MainQuestAI/Deck-Master/issues/183)|[P2] 单任务领取/接纳回执展开全部待办工作正文，重复携带完整材料|[RP-07](task-cards/RP-07.md)|更新本轮修订及验收|

## 执行与回报格式

后续每张卡按“实现范围 → 验收条目 → 证据 → 残项”报告，并记录基准 commit 与本次修复 commit。验收状态只使用 PASS / FAIL / BLOCKED / NOT_RUN；证据明确属于静态、合成、浏览器、真实原生调用、匹配安装或交付。不得把 planned 改为 complete 仅因为 Issue 已关联 PR。
