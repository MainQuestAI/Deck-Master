# N6 内容方法与真实任务证据（工程内容已完成，2026-10-19）

本轮完成了实质方法增量、真实 Host 的完整六页内容稿、具体问题的 v1/v2 修订和实际非作者复核。用户 2026-10-19 04:49 UTC 的后续真实指示接受当前产出方向并要求继续工程；据此已通过现有 `direct_user / host_attested` 合同记录方向、采用 Narrative/Plan，并由真实新 Task 首次接纳完整 v2 Page/Plan。当前 `content_only / content_full` 的 Runtime `completion.state=completed`、`next_action=return_requested_content`；**真实用户本地效果与可信 Host 验收按用户指示延期，不把它们写成已通过，也不再称缺方向或未采用。**外部证据根的可移植保管 locator 为 `N6/`，原件未加入 Git；相对文件名与 hash 见 [证据索引](N6-evidence-index.json)，实际路径映射由集成 Owner 在外部保管。本文件只索引原件及必要短句，不另建正文真源。

## 实际问题与方法改动

固定历史输入为 `docs/reports/rc3/native-content-handoff-20261014/actual-Q2-B-run-v1/raw-first-complete-draft.json`，SHA256 `240a1d9fb1937e3f551cce134b6a4cd3db01c3a4ef0a1ce83d87024d4fa770ff`。作者实际读完全部八页客户可见正文与 notes；它是历史固定输入稿，不能称为本轮首次稿。未取得其原始 sources，因此不据稿件中的定位认定来源已核实，也不重开历史已关闭的布局和 notes 问题。

具体缺口：p05 的四行准备表已经完整承载资料、只读入口、提示/未知和记录资源的启动准备。p07 的标题“启动条件落实后，用四周形成可复核的去留依据”、副标题“准备核查完成后再安排四周”与首段 `start-gate` 再次重复同一个计时前提。p07 的四周动作/交付表本身有独特贡献；问题是多个表达层反复重启前提，而不是整页无用。p01 的附条件推荐、p03 的选项适用条件和 p08 的具体待决启动项服务各自判断，属于不可机械删除的正对照。

旧方法已有“独特贡献”“必要限定可见”等要求，但没有告诉作者：面对重复限定应移动哪一处、哪一处必须保留，以及怎样查同页标题/副标题/首段的语义重复。新方法补了五步实际操作：识别同一命题与作用域；判断删掉后的具体误读；完整前提归入解释条件/责任的页；后页保留最短且可定位承接并写本页独特动作；遮住同页一处表达检查余文，再回读 notes/结论与限定。独立单页、操作边界、附条件推荐和教学回顾另有明确保留规则。

- `skills/deck-master/references/content-methods.md`：新增“把重复前提归位，再检查推进”的可执行步骤。
- `content-examples.md`：新增自包含中性“共享工具站”连续三页完整修改前/后正文，分开准备、归还操作和熟悉安排，附合理重复正例与单页分发边界。
- `content-calibration.md`：补具体审查动作、应删位置和不可删的异常/结果限定；没有另建评分或固定页型。

完整 diff：`N6/method-change.diff`；旧文件原件：`N6/method-before/`；新旧 hash：`N6/identity.json`。三个文件仍是唯一 canonical 来源，没有复制进其他 Skill。本次接续未再次修改这些方法，既有新 Task 的 manifest 身份继续保留。

## 新任务、真实身份和稿件

任务 locator：`N6/normal-task`；项目 ID `normal-task`，request `req-9c4e4f9321dd`。受众是首次接手读书会报名的协调员，目标是按席位、候补顺序和回应证据处理补位与交接。委托为 `input/commission.txt`；全部材料为 Host 实际编写并完整读取的自包含中性合成材料：S1 规则、S2 记录/访谈/练习、S3 当前工具说明。不是客户制度、真实运营数据或效果测量。

范围为 `content_only / content_full`、独立阅读、约六页软目标、无讲稿、无图像/SVG/PPT、无发布或外部发送。没有用现成确认稿隐藏替代原材料，也没有把方法里的工具站例子直接当任务答案。首稿/v1 Host 为 `codex:/root/impl_n6`；v2 接续作者为 `codex:/root/rc4_quality`，配置请求为 `gpt-6.1-sol / xhigh`，可独立核验的实际 serving model ID、采样参数和后端版本仍为 `unknown`。未付费调用外部模型。

原始输出与身份分开保存：

| 原件 | 身份 |
|---|---|
| `host/framing-payload.raw.json`、`framing-envelope.json` | 实际 Host framing 与提交信封 |
| `host/argument-payload.raw.json`、`plan-input.raw.json`、`argument-envelope.json` | 实际 Host argument/完整 planned Plan 与提交信封 |
| `host/pages-first.raw.json` | 首次写完六页的 Host 原始内容与逐块映射选择；不是脚本答案 |
| `host/page-copy-first.payload.json` | 机械展开真实 source/version/locator、atom ID 后的完整 Page/Plan payload；绑定已存的未采用 Narrative proposal |
| `host/first-complete-draft.md` | 上述六页稿的完整可读投影，仅供审阅，未冒认 Runtime 已采用 |
| `host/pages-revised-v1.raw.json`、`page-copy-revised-v1.payload.json`、`revised-v1-complete-draft.md` | 作者自查后的独立保存修订版；首次成功采用前的独立保存版本 |
| `host/pages-revised-v2.raw.json`、`plan-input-revised-v2.raw.json`、`page-copy-revised-v2.payload.json`、`revised-v2-complete-draft.md` | 处理实际非作者 finding 后的完整修订版；含 Page/Plan/来源映射，现已通过新 Task 首次采用 |
| `runtime/framing-accept.json`、`argument-accept.json` | 首次实际成功接纳的阶段提案，均 `adopted=false` |

`mechanical.py` 仅负责信封、来源别名/atom 选择器展开和可读投影；所有判断、正文、关系、Plan 角色及映射范围均由本 Host 先写在原始 JSON 中。它不生成结论、不伪造模型/收据/批准，不修改 Runtime 对象存储。第一次机械检查曾误用 `plan_input` schema 名，改为实际 `content_plan_input` 后通过；原始内容未因此改写。

新方法在实际训练结构中被应用：p01 主承载状态定义和工具范围；p02 直接写补位链，p03 按三种中断写保留信息与责任，p04 实际拆解记录，p05 独立练习，p06 反馈与交接。未回应限制在 p02/p03/p06 出现，分别约束推进、异常交接和答案判断，按方法作为有效重复保留。没有把所有条件搬到脚注，也没有把流程边界隐藏进空 notes。

作者对完整稿自查发现一项局部实质缺陷（`host/author-findings-v1.json`）：p04 标题“活动A：三个缺口没有核查，不能从旧记录直接补位”把缺记录误写成从未核查。修订为“活动A：席位、顺序、回应仍缺可核对依据”，并将同页 `atom:p04:item:response:text` 的“未核查前”改为“在回应尚无可核对依据时”。回读 p04 全文、p06 的未回应/历史未记录区别，以及 Narrative `case-a`、Plan p04，未保留“从未核查”的断言。首稿未覆盖，修订后 schema/source/atom 检查通过。此为真实作者发现与改稿，不冒充独立审查；其后 v2 是新 Task 首次接纳的 Page 稿，不冒称对已采用首稿做了一次 Runtime 返修。

实际非作者 root 完整读取委托、三来源、首稿，再完整复读 v2 六页、修订 Plan 与原 Narrative，记录 `N6-root-F1 / F2`：p04 的“核查……再如实补记”和 p06 的“本次实际联系时间须补记”可能把历史缺失写成必能补齐。S1 L8 要求未知及原因保留，S2 L4/L6 均未提供联系时间。真实独立审阅原件为 `rc4-input/N6-independent-review-20261019.json`，索引保存其 hash；它不是 Runtime trusted receipt，也不授权方向采用。

v2 对实际 Page/Plan 做了以下修改，原稿/v1 均保留；完整前后文见 `host/revision-v2.diff` 和 `host/author-findings-v2.json`：

| 对象 | 原表达 | v2 实际表达与依赖 |
|---|---|---|
| p04 `atom:p04:item:response:text` | “应核查实际回应与联系时间，再如实补记” | 当前保留“回应状态与联系时间未知，历史记录未记”；取得可核对依据后补记，无法追溯则保留未知与未能核实的原因。映射补既有 `handoff` 节点和 S1 L8。 |
| p06 `atom:p06:block:record:text` | “本次实际联系时间须补记” | “联系时间未知（题目未提供）”；实际交接先核查，能核查后补记，无法核查保留未知及原因。已有 `practice-b/handoff` 和 S2 L6/S1 L8 映射继续适用。 |
| 待提交 Plan 输入 p04/p06 | 核查缺口与记录联系事实，未展开不可恢复分支 | 同步两页 takeaway；p04 加 `handoff/S1 L8`。已接纳的原 planned Plan 提案保持原件，未改 Runtime 指针。 |

作者复读全部六页标题、正文、表格、脚注、空 notes、完整 Narrative 和修订 Plan：p02 的正常新联系记录要求仍成立；p03 的未知保留与 p04/p06 一致；p05 不提供联系时间，p06 不补造；没有增加截止时间、跳过规则、收益或个人数据政策。Narrative 的 `handoff` 已明确未知及原因不能消失，`case-a/practice-b` 没有承诺补齐时间，无需重写。root 在独立审阅 followup 中已将该 finding 的**内容修复**关闭。之后的正式 Runtime 采用已完成；可信前审能力与真实用户验收仍按本次指示单列延期。

## 实际 Runtime 与检查

源码开发使用仓库 `.venv/bin/python`，doctor 实际核对为本 checkout 的 `src/deck_master`，compose `ready`；这不是隔离 wheel 或用户 HOME 安装证据。方法读取走 `read_skill_methods('deck-content', entry_mode='named', project=…, task_id=…)`；两个新 Task 都有自动生成的精确 manifest，argument 自动冻结 `argument-connectivity.v1`。原件见 `runtime/*-task.json`、`*-methods.json`、`doctor-compose.json`、`capabilities.json`。

用户新指示前的首次实际公共调用链为：`service.create` → `task_start` → `accept_result(framing)` → `continue` → `task_start` → `accept_result(narrative + planned Plan)` → `continue`。该历史时点返回 `needs_input / record_direction_decision`，completion `awaiting_decision`，当时的 Narrative/Plan/Page 指针尚未采用；下述真实后续决定及正式采用已改变这一状态。Narrative proposal 为 `afb4961aafe0e9199c451a3800926d8a58585729450c4277b06d045e58e96c0d`；planned Plan 为 `2e780db8679fbfc692bbe343e9286c655f0a92bd974629cf2c9647158af65f66`。

机械检查完成六个 Page 的 schema、58 个真实可见 atom 的覆盖、source version/locator 存在性、Plan schema；notes 为零，符合范围。存在性不证明主张获得来源支持，专业审阅另记。既有方法回归命令为 `.venv/bin/python -m pytest tests/rebuild/test_rc3_content_methods.py tests/rebuild/test_rc3_early_methods.py -q`，实际 **9 passed**，原始输出 `runtime/method-tests.txt`。`git diff --check` 对三个方法文件通过。没有声称验证视觉、PPT 或真人计时。

v2 新检验由仓库 Python 运行 `N6/check_revised_v2.py`，结果在 `runtime/revised-v2-mechanical-checks.json`：六页/58 atoms、全部 source version/locator、Plan 输入与真实 Narrative 节点、raw→payload→可读稿精确投影通过；p01/p02/p03/p05 的完整 Page 与 v1 相同。两个原 Task 的 `read_skill_methods` 再读仍为 `current`，manifest 与已冻结 SHA 一致。整个 Runtime 项目文件 hash 集合在检验前后相同，revision 仍为 `e197feb18885424ea8d140d789353cb7`，completion 仍 `awaiting_decision`。机械检验不承担来源支持或专业批准判断。

## 当前 Runtime 结果与延期观察

真实用户指示原话与接收来源保存在 `runtime/actual-direction-20261019/01-actual-instruction.json`。其含义是按当前产出方向继续工程、真实验收待用户本地执行；它作为普通 Host-attested 指令记录，`actor_id` 与 transport receipt 均为空，没有伪装成已验证用户事件或专业批准。

本次通过公共 Runtime 完成：`record_decision(authority_mode=direct_user, disposition=accepted)` → `adopt_proposal(Narrative)` → `adopt_proposal(planned Plan)` → `continue` 派发 Page-copy → 实际 `task_start` → 原有完整 v2 payload 的 `accept_result` → `continue`。Page-copy Task 为 `7e5ca2e5f1c6`，实际接续/传输 Host 为 `codex:/root/rc4_methods`；原作者/v2 修订者身份仍单独保存。新 Task 的方法 manifest 再读为 `current`。全部六个采用 Page 与原 v2 payload 逐一相等，bound Plan 的 input、Narrative Ref、六个 page_links 与采用 Page Ref 一致。没有用脚本生成新的正文或判断。

当前 revision 为 `cd2fd8310b25487389f9efff18db186c`；Narrative 为 `afb4961aafe0e9199c451a3800926d8a58585729450c4277b06d045e58e96c0d`，bound Plan 为 `9c7422d1781b99f6fb1e5513c9e94c0aae3ed4cb5e018cf372b7d2e7de3b36eb`。精确 Ref、成功回包、当前完成状态和身份见 [Runtime 采用证据](N6-runtime-adoption.json)；外部原件在 `runtime/actual-direction-20261019/`。原始 Host 首稿/v1/v2、输入及 method-before 的完整 hash 集合经前后比较保持不变。原 Narrative 仍保留作者在提案时记录的 `direction-unadopted` issue；实际方向决定与采用是另外的 Runtime 事实，没有为更新文字而重标该不可变对象。

`content_only / content_full` 的真实 `continue` 返回 `completed / return_requested_content`，`requested_content=pass`，没有缺失项。这是本次约定内容的完成事实，适用 N6 §5 步骤4“正常任务是 content_only 时，完成该子意图的完整产物与适用检查即可”。没有图片、SVG、PPT 或 notes 的交付义务。不得在此追加该合同未要求的前置生产 gate。

为明确后续审查能力，另外调用现有 `dispatch_preproduction_review`，实际返回 `needs_reviewer`，要求仍为 `independent_model_or_human`；`independent_review_receipts=false`、`human_review_receipts=false`、`providers=[]`。该调用提供六页完整 review packet，未创建审查 Task/受信收据，current revision 不变。它说明目前不能接纳受信独立前审，不反向把已完成的 content-only 内容标为未完成。用户本地真实效果与可信 Host 验收保持延期；不降为 `host_self`，不虚构专业 PASS。

`authorizations` 全程仍为空，`quality_profile` 与采用前逐字相同；没有调用 `grant`、没有新增 provider 或付费调用。旧 `pending-authorization/` 与早先 direct-user pending 请求原件均保留未提交身份；本次使用另存的真实指示和实际请求，不执行旧 grant。实际执行来自源码 checkout，观测到的 source identity 为 `dirty:true`；不是安装版执行。仓库的独立 installed 资源检查不能重标这条 N6 实际应用链。

## AC 映射（本文件不替代唯一执行台账）

| AC | 当前证据结论 |
|---|---|
| N6-01 | 建议 PASS：委托、三份完整中性来源、受众/目的/产物/范围已固定；符合 AC“明确受众、目的、来源、产物及范围”。 |
| N6-02 | 建议 PASS：首份完整 Host 稿、v1/v2 与首次成功采用稿 v2 分开保存；符合 AC“首份完整稿、首次接纳稿和修订稿按实际身份分开”。§5 步骤2允许正常自主编辑，不要求先采用缺陷首稿。 |
| N6-03 | 建议 PASS：历史 p05/p07 重复前提定位、三文件 canonical diff、可执行五步与完整正反例齐全；符合 AC“对应具体问题并给出可执行步骤/完整例子”。 |
| N6-04 | 建议 PASS：实际 Host 读取当前方法并完成全部六页；framing/argument 和新 page_copy Task 的 manifest 可核对，当前完整 v2 已由真实 Task 接纳。符合 AC“存在真实运行与完整约定产物”；源执行身份与 installed 资源身份分别陈述。 |
| N6-05 | 建议 PASS：正式采用的 Narrative、bound Plan、六 Page 与源/atom 映射对应；不是确认稿导入、脚本答案或补造批准。符合 AC“具备实际 Narrative/Plan/Page 的对应主线”。 |
| N6-06 | 建议 PASS（真实修订链限定）：首稿→作者 v1→实际非作者 finding→v2→新 Task 首次成功接纳 v2→Page/Plan 精确回读；原句/改句、来源/atom、完整依赖复核保留，两个内容 finding 已关闭。符合 AC“保留原句/原结构与实际改动…一并检查”及 §5 步骤2；不声称已采用首稿经历 Runtime 返修，不以工程 PASS 掩盖开放问题。 |
| N6-07 | 建议 PASS：仅内容任务，无视觉/notes 改动，不要求或声称视觉产物改善；符合 AC“未做视觉时不宣称视觉已改善”。 |
| N6-08 | 建议 PASS：保存方法前后 hash 后创建适用新 Task，保留旧稿和历史身份；符合 AC“正式创建适用新方法的任务…不重标为当前首稿效果”。 |
| N6-09 | 建议 PASS：按实际 content-only 完成返回，工程、真实方法应用、已修内容与延期本地观察分别记录；符合 AC“不新增这些门槛…分别陈述”。可信前审能力缺口不被变成额外 content-only gate。 |
| N6-10 | 建议 PASS（有边界的本卡证据报告）：实质 diff、完整首稿/当前稿、真实 Runtime 采用、具体修订/复核及未知边界齐全；符合 AC“提供实际 diff、完整稿/成果、修复证据与有边界的结论”。不是由测试数量推出质量或用户验收。 |

以上是供唯一台账 Owner 采用的逐项证据建议，不另建 Runtime 批准。**延期项单列为 `DEFERRED_USER_LOCAL`：用户本地真实效果/可用性验收、可信 Host/独立审查收据验收。** 不因这些延期追问方向，也不把尚未执行的专业/用户认可写成 PASS。

没有相同条件的旧/新首稿对照，不声称总体提升、比例、速度或因果效果。当前可支持的结论是：实质方法已在此六页 Host 正常任务中应用，原始稿与真实修订链保留，v2 已正式成为当前 Runtime Page/Plan；“缺记录写成未发生”和“缺失时间必须补齐”两项内容问题已修复，后者获实际非作者复核。真实用户效果与可信 Host 验收待本地执行，不声称总体提升或专业批准。
