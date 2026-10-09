# PR104 补充意见修复与验收（v1.0）

本轮从 `560c580460654e69378194a4e2180cbce0cce83e` 继续现有
`codex/pr103-complete-repair` 分支。五条意见此前作为只读发现保留；用户在本轮
授权修复、验证、提交、推送和更新 PR104。原八项修复的历史记录仍见
[2026-10-08 验收](pr104-review-repair-20261008.md)。不合并、部署、强推、切换
日常安装入口或调用付费真实 Host。

## 逐项修复与待复审证据

| ID | 意见 | 最小修复与实际验收边界 |
|---|---|---|
| S1 | [压力脚本点击隐藏版本区](https://github.com/MainQuestAI/Deck-Master/pull/104#discussion_r4221261962) | 先进入“版本”，再等可见的历史控件；真实读取分页及全部记录切换。实际完整压力运行还发现基础候选阶段也直接点隐藏区，因此同样先进入“待决定”；新增真实候选路径回归，不使用 force click。 |
| S2 | [旧拆解图按钮名](https://github.com/MainQuestAI/Deck-Master/pull/104#discussion_r4221261975) | 按正式 button 角色和“查看完整拆解图”名称打开；等大图 ready 后关闭，等真实关闭及焦点恢复，再计入阅读次数。完整运行补证正式输入冻结误禁只读/历史稿阅读按钮：只给此阅读动作豁免，配色、字体和正式确认门控保留。 |
| S3 | [同页比较缺少直接前快照](https://github.com/MainQuestAI/Deck-Master/pull/104#discussion_r4221261946) | 相关修改即使就是固定侧，也提供其父快照“修改前”；页范围变更不推断不存在的前页。固定侧不加入选择，同批和跨分页去重。覆盖 p02 先变、p01 后变，默认相关历史里比较 p01 修改前后，无需显示全部。 |
| S4 | [有效同页跨层意见被禁选](https://github.com/MainQuestAI/Deck-Master/pull/104#discussion_r4221261955) | 先核验页身份，再按意见自身层的当前引用核验；PPT 映射到 ppt_preview。原图、SVG、PPT、正文意见可跨层进入真实核心计划，保存并恢复选择；自身层已变/缺失、页已变和其它页仍禁用。不移动原意见或其几何范围。 |
| S5 | [失效截图分析仍能认领](https://github.com/MainQuestAI/Deck-Master/pull/104#discussion_r4221261989) | task_start 在状态写入前复用核心 task_inputs_current，拒绝失效 style_analyze。覆盖引用移除、字体变化、等待/运行中再次认领、历史恢复及正常幂等认领；拒绝后版本、任务、结果和零调用事实保持不变，接受结果的原时效/取消门控继续验证。 |

新增浏览器反例集中在
[test_pr104_supplemental_browser.py](../../tests/rebuild/test_pr104_supplemental_browser.py)，
认领回归在 [test_visual_styles.py](../../tests/rebuild/test_visual_styles.py)。安装回归入口
也包含新增浏览器文件，仍审计实际加载模块的 site-packages 来源。

复审定位：S1/S2 对应 `test_pressure_history_and_full_breakdown_use_visible_production_controls`
的当前/历史/只读三个分支及 `test_pressure_candidate_phase_opens_the_decisions_subarea`；
S3 对应 `test_page_history_offers_the_direct_before_snapshot_and_deduplicates_paging`；
S4 对应 `test_same_page_other_layer_opinion_is_selectable_and_reaches_core_plan` 的四层
载荷和恢复断言，以及 `test_other_layer_opinion_keeps_its_own_staleness_and_page_gates`
的四种负例；S5 对应新增的四种失效认领、字体恢复、正常幂等认领六例。
原确认竞态、草稿串选、重复业务提交、取消及迟到结果继续由原套件覆盖。

## 反例与失败区分

- 修复前真实核心：移除引用/改变字体后，等待中和运行中的四种失效认领都未被拒绝。
  正常认领幂等性通过。历史恢复已经 supersede 原任务；它原先拒绝为 TaskConflict，
  本轮增加明确的输入失效错误，不能把这个错误类型差异声称为旧版允许执行。
- 修复前真实浏览器：直接前快照缺失，四种同页跨层意见禁选，五项按预期失败。
  历史与只读稿的完整拆解图阅读各有一个正式模块反例。压力脚本的隐藏版本入口和
  旧按钮名在真实控件中核对，后续由实际脚本循环验证。
- 首次完整 W10 因基础候选仍在隐藏“待决定”区失败；二次运行进入截图阅读后，因
  只读完整拆解图按钮被正式输入门控禁用失败。两次都不具备完整窗口，不能算通过。
  保留原失败日志、采样和 HAR，不扩大超时、不强制点击、不清缓存或强制 GC。
- 一次针对性核心运行因沙箱不允许本地 HTTP 服务失败，其余 37 项通过；允许本地
  socket 后完整针对性 48 项通过。早期新增测试对折叠意见组使用可访问角色查询、
  对任务子区误认 heading、使用低于工厂下限的页数，均修正测试后复跑；没有修改
  产品门控来迎合这些测试错误。
- 完整单元/浏览器的首次启动出现自动权限审核超时；按返回规则重试一次成功。
  这是启动未执行，不能记录为测试通过或产品失败。

## 固定证据与完成条件

本轮状态为**待复审**。修复提交、开发自测和 CI 成功均不表示评审通过或最终
闭环；父对话将继续由原审查对话及用户指定的审查模型复审，不在本轮替换模型
或自行给出评审通过结论。

冻结后的本机结果、文件摘要和证据名称由
[证据索引](pr104-supplemental-evidence-20261009.json)固定。原始日志、截图、合成运行
及 HAR 保留在本机，不提交原材料或生成运行。提交后的精确 SHA、PR/push CI 与
wheel/离线/安装阶段以 PR104 正文和对应 Actions 记录固定，避免证据文档再改变
已核验 SHA。

本机最后冻结代码的实际结果：

| 验证 | 结果 |
|---|---|
| 针对性核心、补充浏览器与原 PR104 竞态套件 | 82 通过 |
| 完整单元 / 真实渲染 / 源码浏览器 | 1253 / 52 / 317 通过；浏览器 0 失败、0 跳过；渲染 22 条 Pillow 弃用警告 |
| 隔离 wheel 离线 / 安装回归 | 7 项 verified / 157 通过；52 个运行模块均来自 site-packages，零页面错误及外部请求 |
| wheel 文件字节 | 209 文件与源码、隔离安装一致；含 55 静态资源、24 目录图标 |
| W10 usability 完整门禁 | 实跑 1200 秒；中段/后段各 30 样本；内存中位数增长 0.97%（≤20%）；四条路径各 10 次，图片边界通过，零页面错误 |
| W10 热读 summary | 100 样本，p95 96.02ms（≤250ms） |

W10 与部分回归同时运行；无强制 GC、清缓存、重载或放宽阈值。日志中保留了导航
取消后的服务端 BrokenPipe 轨迹，与浏览器错误及脚本退出门禁分开记录。本机测试
在提交前冻结工作树上执行，原 HEAD 字段为上述基线；索引固定八个代码/测试文件
摘要，提交后再核验同一摘要，不能把该字段改写成未来提交。精确新 SHA 的远端
门禁由后续 PR/push CI 独立执行。

测试为正式模块、真实 Python 核心服务与 Chromium，材料是显式合成夹具；模型和
付费真实 Host 调用均为零。W10 的内存/DOM 窗口属于同一合成性能门禁，不代表
专业视觉验收。F09 沿用旧真实 Host 证据，本轮未重跑。
