# 功能与界面差距矩阵

共54项功能核对，包含已有能力、UI适配、真实缺口和验收遗留，不能把53项全部计为缺失功能。

核验基准：main `66da345c84de48933a76de577114f08dcebf4f0e`。这里的“已有能力”不代表最终安装/真实项目验收通过。源码路径相对仓库；设计路径相对收讫目录。每行只有一个剩余项最终责任卡，消费方见任务依赖。

| ID | 能力 | 现状 | 责任卡 | 剩余项 | 设计 / 当前代码 |
|---|---|---|---|---|---|
| G01 | 视觉token/字体/图标 | 部分符合（W03） | [A01](task-cards/A01.md) | 接最新product覆盖；黑色主按钮、sans、控件与字体来源统一 | `design-system.html; style.css` / `src/deck_master/resources/static/v2/tokens.css; src/deck_master/resources/static/v2/workbench.css` |
| G02 | 数据表可读性/键盘/排序/选择 | 设计差距（W04） | [A03](task-cards/A03.md) | 从roving grid改普通Tab；章节、筛选、下一步和批量范围可见 | `design-system.html#table` / `src/deck_master/resources/static/v2/views.js` |
| G03 | 状态文案/错误/焦点 | 部分符合（W03 W10） | [A01](task-cards/A01.md) | 统一正式文案及真实状态；禁止模拟执行控件 | `product-ui-language.md; states.js` / `src/deck_master/resources/static/v2/dom.js; src/deck_master/resources/static/v2/drafts.js` |
| G04 | 项目新建/打开/示例/目录选择 | 已有能力，重做呈现（W03） | [A02](task-cards/A02.md) | 搜索卡片与空项目指导，补真实macOS选择/取消证据 | `app.js:projects` / `src/deck_master/launcher.py; src/deck_master/registry.py; src/deck_master/resources/static/v2/launcher-ui.js` |
| G05 | 主CLI与Skill打开新UI | 主流程入口补齐（W03） | [B02](task-cards/B02.md) | view增加显式ui选择，同项目连贯进入；不改默认发布 | `app.js:projects` / `src/deck_master/cli.py; src/deck_master/web.py; skills/deck-master/SKILL.md` |
| G06 | 当前项目可执行能力 | 功能差距，P05实测（W02 W03） | [B02](task-cards/B02.md) | health静态能力与项目可用动作分开，旧格式/只读/历史给原因 | `app.js:connection-info` / `src/deck_master/web.py; src/deck_master/ui_journal.py; src/deck_master/resources/static/v2/project.js` |
| G07 | 五工作面和共享单页 | 已有能力，重做呈现（W03–W11） | [A02](task-cards/A02.md) | 保持路由/跨项目隔离，改最新外壳及层级 | `app.js:navigate` / `src/deck_master/resources/static/v2/routes.js; src/deck_master/resources/static/v2/project.js` |
| G08 | 候选计数活动schema | 契约缺陷，P03实测（W01 W07） | [B01](task-cards/B01.md) | recorded/count响应必须有兼容schema分支 | `app.js:overview` / `src/deck_master/workbench.py; src/deck_master/resources/contracts/workbench-summary.v1.schema.json` |
| G09 | 真实待办与下一动作 | 功能差距，P02实测（W01 W04） | [B01](task-cards/B01.md) | 当前attention恒not_recorded；增加可溯源确定性动作投影 | `app.js:overview` / `src/deck_master/workbench.py; src/deck_master/resources/static/v2/views.js` |
| G10 | 总览待办区与矩阵 | 设计差距（W04） | [A03](task-cards/A03.md) | 最新优先待办/余项/章节/提示词/下一步；禁用硬编码24页与样本结论 | `app.js:overview` / `src/deck_master/resources/static/v2/views.js` |
| G11 | prompt摘要 | 读模型差距，P02实测（W01 W02） | [B01](task-cards/B01.md) | 准备/冻结/实际提交独立事实，摘要不载入全文 | `app.js:matrix` / `src/deck_master/workbench.py` |
| G12 | 整稿网格/连续/并排/列数 | 已有能力，重做呈现（W04） | [A04](task-cards/A04.md) | 按新图面、筛选与比较布局集成 | `app.js:gallery` / `src/deck_master/resources/static/v2/gallery.js; src/deck_master/resources/static/v2/gallery-state.js` |
| G13 | 大图缩略图缓存与导航 | 未闭合故障（W04 W12） | [A04](task-cards/A04.md) | 旧压力记录有候选读取时导航timeout；定位并复验 | `app.js:gallery` / `src/deck_master/resources/static/v2/images.js; src/deck_master/resources/static/v2/candidate-desk.js` |
| G14 | 整合材料/大纲/逐页关联 | 已有能力，重做呈现（W02 W09） | [A05](task-cards/A05.md) | 真实引用导航，旧项目推导标明，无假来源 | `app.js:content` / `src/deck_master/content_plan.py; src/deck_master/resources/static/v2/content-sources.js` |
| G15 | 材料上传/要求/影响判断 | 已有能力，重做呈现（W09） | [A05](task-cards/A05.md) | 沿用实际inputs路径/格式；已登记、已读取、已采用分开 | `app.js:material-impact` / `src/deck_master/content_ops.py; src/deck_master/service.py; src/deck_master/resources/static/v2/content-sources.js` |
| G16 | 直接编辑正文 | 已有能力，重做呈现（W05 W09） | [A05](task-cards/A05.md) | 保留草稿及局部失效，直接保存与试作候选区分 | `states.js:正文` / `src/deck_master/editing.py; src/deck_master/resources/static/v2/content-edit.js` |
| G17 | 正文与内容变更集候选 | 功能差距，P01实测（W07 W09） | [B03](task-cards/B03.md) | 现只接受图像/SVG trial；增加Page与content_update候选及Task结果合同 | `design-system.html:candidate` / `src/deck_master/changes.py; src/deck_master/candidates.py` |
| G18 | 正文候选左右差异 | UI差距（W05 W07） | [A06](task-cards/A06.md) | Page/Artifact分型，正文diff；不伪造图片预览 | `design-system.html:candidate` / `src/deck_master/resources/static/v2/candidate-desk.js; src/deck_master/resources/static/v2/text-diff.js` |
| G19 | 六阶段导航 | 已有能力，重做呈现（W05） | [A04](task-cards/A04.md) | 来源/正文/prompt/原图/SVG/PPT同页同版本 | `app.js:page` / `src/deck_master/resources/static/v2/page-workbench.js; src/deck_master/resources/static/v2/routes.js` |
| G20 | 准备/草稿/实际prompt/参数 | 已有能力，重做呈现（W01 W02 W05） | [A04](task-cards/A04.md) | 未知明确；冻结请求、Host申报、tool观察区别保留 | `app.js:promptParts` / `src/deck_master/generation.py; src/deck_master/resources/static/v2/request-view.js` |
| G21 | 保存prompt/首次图/重做图 | 已有能力，重做呈现（W06 W07） | [A05](task-cards/A05.md) | 草稿保存不执行；目标/预算/版本plan后提交 | `app.js:save-prompt; queueImages` / `src/deck_master/changes.py; src/deck_master/resources/static/v2/trial-actions.js` |
| G22 | 仅重建SVG | 已有能力，重做呈现（W07） | [A06](task-cards/A06.md) | 保留原图/实际prompt，采用SVG后PPT待更新 | `app.js:rebuild-svg` / `src/deck_master/changes.py; src/deck_master/candidates.py` |
| G23 | 项目/章节/页面/产物标注 | 已有能力，重做呈现（W06） | [A05](task-cards/A05.md) | 范围与版本清楚；意见保存不自动创建执行 | `app.js:save-note; states.js` / `src/deck_master/annotation_service.py; src/deck_master/resources/static/v2/annotations.js` |
| G24 | 点/框/文本选区与无鼠标输入 | 已有能力，重做呈现（W06） | [A05](task-cards/A05.md) | 缩放/letterbox坐标与Unicode范围准确，旧选区不自动迁移 | `app.js:bindRegion; apply-region` / `src/deck_master/text_sources.py; src/deck_master/resources/static/v2/text-selection.js` |
| G25 | 批量事务/同页意见/幂等 | 已有能力，保留回归（W06） | [A05](task-cards/A05.md) | 不重建事务服务；UI合并同页独立选区，错页负例 | `states.js:batch` / `src/deck_master/changes.py; src/deck_master/operations.py` |
| G26 | 复制制作要求/手动发送 | 已有能力，重做呈现（W06） | [A07](task-cards/A07.md) | 复制成功只复制；真实task start才处理中；工具打开仅预填 | `app.js:copyText; task-copy` / `src/deck_master/changes.py; src/deck_master/resources/static/v2/change-handoff.js` |
| G27 | 请求/Attempt/调用/结果绑定 | 已有人机链路证据（W02 W07） | [B06](task-cards/B06.md) | 继承真实W07证据；新增正文和风格路径分别补证 | `app.js:handoff` / `src/deck_master/generation.py; src/deck_master/tasks.py` |
| G28 | 风格固定参考/选维度/目标事实 | 已有能力，重做呈现（W08） | [A06](task-cards/A06.md) | 参考+目标+一句话默认，精细参数折叠 | `app.js:style` / `src/deck_master/styles.py; src/deck_master/resources/static/v2/style-calibration.js` |
| G29 | 风格单页试作后扩展 | 效果缺口（W08） | [B06](task-cards/B06.md) | 已观察未选构图漂移；约束和真实正向扩展证据尚需补足 | `app.js:batch-rest` / `src/deck_master/styles.py` |
| G30 | 原图/SVG候选固定比较/采用 | 已有能力，重做呈现（W07） | [A06](task-cards/A06.md) | 等比例完整图，采用plan失效保护，参考放大 | `app.js:compareTask` / `src/deck_master/candidates.py; src/deck_master/resources/static/v2/candidate-desk.js` |
| G31 | 保留当前决定/再次打开 | 功能差距，源码确认（W07） | [B04](task-cards/B04.md) | 现keep只是返回；新增持久决定和reopen，不删除候选 | `app.js:keep-task; keep-style` / `src/deck_master/candidates.py; src/deck_master/resources/static/v2/candidate-desk.js` |
| G32 | 重试新请求与保留旧候选 | 已有能力，重做呈现（W07 W10） | [A06](task-cards/A06.md) | 保留retry关系、原调用事实，不用传输重放当模型重试 | `app.js:retry-task; retry-style` / `src/deck_master/changes.py; src/deck_master/resources/static/v2/trial-actions.js` |
| G33 | 候选后续失效/旧成品可访问 | 已有能力，保留回归（W01 W07 W09） | [B03](task-cards/B03.md) | 新增正文候选也走统一失效；未改页保留，整稿PPT标旧 | `app.js:staleReason` / `src/deck_master/candidates.py; src/deck_master/editing.py; src/deck_master/workbench.py` |
| G34 | 重排与移除 | 已有能力，重做呈现（W09） | [A05](task-cards/A05.md) | 保持身份/记录历史/取消受影响未完成任务 | `states.js:structure` / `src/deck_master/content_ops.py; src/deck_master/resources/static/v2/content-edit.js` |
| G35 | 合并/拆分/跨页改写 | 已有能力，重做呈现（W09） | [A05](task-cards/A05.md) | 复用Host局部content_update与新页来源；新增回传后候选采用依赖B03，不假定已有该步骤 | `states.js:structure` / `src/deck_master/content_ops.py` |
| G36 | 运行进度/部分返回/任务筛选 | 已有能力，重做呈现（W10） | [A07](task-cards/A07.md) | 工作面层级简化，结果逐页对应，处理PR66状态水合竞态 | `app.js:runs; states.js:batch` / `src/deck_master/run_desk.py; src/deck_master/resources/static/v2/run-desk.js` |
| G37 | 30分钟超时/取消/晚到 | 已有能力，保留回归（W06 W10） | [A07](task-cards/A07.md) | 真实生命周期，超时后用户决定，无自动新调用 | `app.js:task-cancel; states.js` / `src/deck_master/run_desk.py; src/deck_master/tasks.py` |
| G38 | 刷新/隐藏/重聚焦/断网 | 已有能力，保留回归（W03 W10） | [A07](task-cards/A07.md) | 依现有策略、保存读取位置和固定版本不跳动 | `states.js` / `src/deck_master/resources/static/v2/summary-poll.js; src/deck_master/resources/static/v2/project.js` |
| G39 | 草稿ACK/跨端口/未知保存/冲突 | 已有能力，重做呈现（W02 W03 W10） | [A07](task-cards/A07.md) | 保留原operation先查询、双稿并列，不自动覆盖 | `states.js:unknown; conflict` / `src/deck_master/ui_journal.py; src/deck_master/resources/static/v2/drafts.js; src/deck_master/resources/static/v2/business-operations.js` |
| G40 | 清除本机数据 | 功能语义必须收敛（无） | [B05](task-cards/B05.md) | 仅当前项目个人草稿/阅读设置，预览/备份/确认；禁止删业务项目任务候选 | `app.js:reset` / `src/deck_master/ui_journal.py` |
| G41 | 历史指定版本读取/比较 | 已有能力，P04实测（W01 W11） | [A07](task-cards/A07.md) | 之前的revision路由缺口已解决；只重做UI并回归 | `states.js:history` / `src/deck_master/web.py; src/deck_master/snapshots.py` |
| G42 | 历史恢复为新版本 | 已有能力，未最终验收（W11） | [A07](task-cards/A07.md) | 先查看比较再plan/commit；调用事实不回滚 | `states.js:history` / `src/deck_master/exports.py; src/deck_master/resources/static/v2/delivery-desk.js` |
| G43 | review/delivery/engineering导出 | 已有能力，未最终验收（W11） | [B07](task-cards/B07.md) | 最终安装重验冻结快照、隐私清理和工程包恢复；UI不照抄未连接 | `app.js:export-review; export-engineering` / `src/deck_master/exports.py; src/deck_master/resources/static/v2/delivery-desk.js` |
| G44 | 下载/重取/越界防护 | 已有能力，未最终验收（W11） | [B07](task-cards/B07.md) | 实际同源下载hash，跨项目/失效ID拒绝，不绕过Origin | `app.js:export` / `src/deck_master/web.py; src/deck_master/exports.py` |
| G45 | 交付readiness和专业质量 | 已有能力，保留回归（W11） | [A07](task-cards/A07.md) | 工程/专业/桌面证据分层，采用不等于PPT完成 | `design-system.html:status` / `src/deck_master/editing.py; src/deck_master/resources/static/v2/delivery-desk.js` |
| G46 | wheel/sdist离线资源/Skill | 未最终闭合（W12） | [B07](task-cards/B07.md) | 旧安装93c76a1摘要可追回，最终SHA必须重建 | `index.html; style.css` / `pyproject.toml; tools/build_hook.py` |
| G47 | 300×5×3压力/20分钟内存 | 未最终闭合（W01 W04 W10 W12） | [B07](task-cards/B07.md) | 已有pressure failure；保持原门槛，修根因后重测 | `app.js:gallery` / `src/deck_master/resources/static/v2/images.js; src/deck_master/workbench.py` |
| G48 | 30页真实项目与两轮视觉修改 | 缺实际验收材料/记录（W12） | [B06](task-cards/B06.md) | 真实项目选定后执行；不得合成样本冒充真实项目 | `app.js:全链路` / `docs/reports/workbench-v3-execution-20260926/W12.md` |
| G49 | 正常安装/回退/默认切换 | 未最终闭合（W12） | [B07](task-cards/B07.md) | 临时目录回退演练与实际HOME迁移仍待用户执行；默认入口已按用户发布授权切换（2026-10-01，/legacy/ 回退保留） | `product-ui-language.md` / `src/deck_master/install.py; src/deck_master/cli.py` |
| G50 | 六状态规范与完整动线 | 设计已收讫，产品待验（W12） | [A08](task-cards/A08.md) | 逐状态实际HTTP/浏览器证据；状态规范页不进产品导航 | `states.html; states.js` / `src/deck_master/resources/static/v2/app.js` |
| G51 | 原型localStorage/硬编码示例/模拟执行 | 仅设计参考，禁止移植为真状态（不适用） | [A01](task-cards/A01.md) | 保留原文件作设计；生产使用Python真数据，模拟只用于独立状态参考 | `app.js:initialArtifact; task-claim; reset` / `src/deck_master/resources/static/v2/app.js` |
| G52 | 合并/拆分回传后采用 | 采用时机功能差距，源码确认（W09） | [B03](task-cards/B03.md) | 当前_accept_content_update接受结果即改稿；先存内容变更集候选，查看影响后原子采用 | `states.js:return-structure / confirm-adopt-structure` / `src/deck_master/content_ops.py; src/deck_master/tasks.py` |
| G53 | 材料影响判断回传后采用 | 采用时机功能差距，源码确认（W09） | [B03](task-cards/B03.md) | 新输入可登记待协调，trial回传先存候选；正文/大纲/输入对齐在用户采用后变更 | `app.js:material-impact` / `src/deck_master/service.py; src/deck_master/tasks.py` |
| G54 | v1格式项目写端点格式门 | 端点行为不一致，B02评审实测（W12） | [B07](task-cards/B07.md) | candidates/inputs/run_desk/exports/restoration 写路径无 workbench.v3 门（v1 项目实测可写并会原地升级）；补齐端点门或在合同明确放行，消除与投影/B02-AC03 的分歧 | `exports.py:359; candidates.py:198; restoration.py:48; service.py:1155` / `src/deck_master/ui_journal.py` |
