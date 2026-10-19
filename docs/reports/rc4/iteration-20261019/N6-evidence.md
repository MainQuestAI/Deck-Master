# N6 内容方法与真实任务证据（进行中，2026-10-19）

本轮完成了实质方法增量、真实 Host 的 framing/argument/Plan 提案、完整六页内容稿，以及具体问题的 Host v1/v2 修订和实际非作者复核。**尚未完成正常任务的 Runtime Page 采用、Runtime 返修与受信独立前审，不能关闭 N6。** 项目准确状态为 `awaiting_decision`。外部证据根的可移植保管 locator 为 `N6/`，原件未加入 Git；相对文件名与 hash 见 [证据索引](N6-evidence-index.json)，实际路径映射由集成 Owner 在外部保管。本文件只索引原件及必要短句，不另建正文真源。

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
| `host/pages-revised-v1.raw.json`、`page-copy-revised-v1.payload.json`、`revised-v1-complete-draft.md` | 作者自查后的独立保存修订版；仍未由 Runtime 采用 |
| `host/pages-revised-v2.raw.json`、`plan-input-revised-v2.raw.json`、`page-copy-revised-v2.payload.json`、`revised-v2-complete-draft.md` | 处理实际非作者 finding 后的完整修订版；含 Page/Plan/来源映射，仍未由 Runtime 采用 |
| `runtime/framing-accept.json`、`argument-accept.json` | 首次实际成功接纳的阶段提案，均 `adopted=false` |

`mechanical.py` 仅负责信封、来源别名/atom 选择器展开和可读投影；所有判断、正文、关系、Plan 角色及映射范围均由本 Host 先写在原始 JSON 中。它不生成结论、不伪造模型/收据/批准，不修改 Runtime 对象存储。第一次机械检查曾误用 `plan_input` schema 名，改为实际 `content_plan_input` 后通过；原始内容未因此改写。

新方法在实际训练结构中被应用：p01 主承载状态定义和工具范围；p02 直接写补位链，p03 按三种中断写保留信息与责任，p04 实际拆解记录，p05 独立练习，p06 反馈与交接。未回应限制在 p02/p03/p06 出现，分别约束推进、异常交接和答案判断，按方法作为有效重复保留。没有把所有条件搬到脚注，也没有把流程边界隐藏进空 notes。

作者对完整稿自查发现一项局部实质缺陷（`host/author-findings-v1.json`）：p04 标题“活动A：三个缺口没有核查，不能从旧记录直接补位”把缺记录误写成从未核查。修订为“活动A：席位、顺序、回应仍缺可核对依据”，并将同页 `atom:p04:item:response:text` 的“未核查前”改为“在回应尚无可核对依据时”。回读 p04 全文、p06 的未回应/历史未记录区别，以及 Narrative `case-a`、Plan p04，未保留“从未核查”的断言。首稿未覆盖，修订后 schema/source/atom 检查通过。此为真实作者发现与改稿，不冒充独立审查或已完成 Runtime Page 修复。

实际非作者 root 完整读取委托、三来源、首稿，再完整复读 v2 六页、修订 Plan 与原 Narrative，记录 `N6-root-F1 / F2`：p04 的“核查……再如实补记”和 p06 的“本次实际联系时间须补记”可能把历史缺失写成必能补齐。S1 L8 要求未知及原因保留，S2 L4/L6 均未提供联系时间。真实独立审阅原件为 `rc4-input/N6-independent-review-20261019.json`，索引保存其 hash；它不是 Runtime trusted receipt，也不授权方向采用。

v2 对实际 Page/Plan 做了以下修改，原稿/v1 均保留；完整前后文见 `host/revision-v2.diff` 和 `host/author-findings-v2.json`：

| 对象 | 原表达 | v2 实际表达与依赖 |
|---|---|---|
| p04 `atom:p04:item:response:text` | “应核查实际回应与联系时间，再如实补记” | 当前保留“回应状态与联系时间未知，历史记录未记”；取得可核对依据后补记，无法追溯则保留未知与未能核实的原因。映射补既有 `handoff` 节点和 S1 L8。 |
| p06 `atom:p06:block:record:text` | “本次实际联系时间须补记” | “联系时间未知（题目未提供）”；实际交接先核查，能核查后补记，无法核查保留未知及原因。已有 `practice-b/handoff` 和 S2 L6/S1 L8 映射继续适用。 |
| 待提交 Plan 输入 p04/p06 | 核查缺口与记录联系事实，未展开不可恢复分支 | 同步两页 takeaway；p04 加 `handoff/S1 L8`。已接纳的原 planned Plan 提案保持原件，未改 Runtime 指针。 |

作者复读全部六页标题、正文、表格、脚注、空 notes、完整 Narrative 和修订 Plan：p02 的正常新联系记录要求仍成立；p03 的未知保留与 p04/p06 一致；p05 不提供联系时间，p06 不补造；没有增加截止时间、跳过规则、收益或个人数据政策。Narrative 的 `handoff` 已明确未知及原因不能消失，`case-a/practice-b` 没有承诺补齐时间，无需重写。root 在独立审阅 followup 中已将该 finding 的**内容修复**关闭，并说明正式 Runtime 采用和可信前审仍未解决。

## 实际 Runtime 与检查

源码开发使用仓库 `.venv/bin/python`，doctor 实际核对为本 checkout 的 `src/deck_master`，compose `ready`；这不是隔离 wheel 或用户 HOME 安装证据。方法读取走 `read_skill_methods('deck-content', entry_mode='named', project=…, task_id=…)`；两个新 Task 都有自动生成的精确 manifest，argument 自动冻结 `argument-connectivity.v1`。原件见 `runtime/*-task.json`、`*-methods.json`、`doctor-compose.json`、`capabilities.json`。

实际公共调用已执行：`service.create` → `task_start` → `accept_result(framing)` → `continue` → `task_start` → `accept_result(narrative + planned Plan)` → `continue`。最后一次返回 `needs_input / record_direction_decision`，completion `awaiting_decision`，current Narrative/Plan/Page 指针尚未采用。Narrative proposal 为 `afb4961aafe0e9199c451a3800926d8a58585729450c4277b06d045e58e96c0d`；planned Plan 为 `2e780db8679fbfc692bbe343e9286c655f0a92bd974629cf2c9647158af65f66`。

机械检查完成六个 Page 的 schema、58 个真实可见 atom 的覆盖、source version/locator 存在性、Plan schema；notes 为零，符合范围。存在性不证明主张获得来源支持，专业审阅另记。既有方法回归命令为 `.venv/bin/python -m pytest tests/rebuild/test_rc3_content_methods.py tests/rebuild/test_rc3_early_methods.py -q`，实际 **9 passed**，原始输出 `runtime/method-tests.txt`。`git diff --check` 对三个方法文件通过。没有声称验证视觉、PPT 或真人计时。

v2 新检验由仓库 Python 运行 `N6/check_revised_v2.py`，结果在 `runtime/revised-v2-mechanical-checks.json`：六页/58 atoms、全部 source version/locator、Plan 输入与真实 Narrative 节点、raw→payload→可读稿精确投影通过；p01/p02/p03/p05 的完整 Page 与 v1 相同。两个原 Task 的 `read_skill_methods` 再读仍为 `current`，manifest 与已冻结 SHA 一致。整个 Runtime 项目文件 hash 集合在检验前后相同，revision 仍为 `e197feb18885424ea8d140d789353cb7`，completion 仍 `awaiting_decision`。机械检验不承担来源支持或专业批准判断。

## 当前窄阻断

实际动作/目标是为上述冻结 Narrative proposal 记录有效方向采用决定，再完成 Page 接纳与 Runtime 修订。Runtime 要求有效 accepted direction 决定或 delegation；现有真实用户限制禁止改授权，且没有已认可该 Host proposal 的证据。**未提交** `collaboration.grant`、方向决定或 `adopt_proposal`，没有把同一作者改名、确认稿导入或手改对象存储当替代路径。此处为政策范围未解决的 pending 状态，不是自动批准审查拒绝，也没有不确定提交。

早期拟调用链保存在 `pending-authorization/`，状态明确 `PREPARED_NOT_SUBMITTED`，未执行。集成复核确认更窄的路径可用：若用户真实确认该方向及六页 Plan，可按原话记录 `authority_mode=direct_user` 的方向决定，再采用所指 proposal；不需要新增 grant。普通 Host 证据仍准确标为 `host_attested`，不伪称验证了用户身份或专业认可。原始委托不是对后续 proposal 的自动批准，收到真实决定前继续保留 pending。

第二个能力缺口：`capabilities.independent_review_receipts=false`、`human_review_receipts=false`、`providers=[]`。独立实际阅读可以保存为真实非作者审阅，但当前不能冒认 Runtime 已接纳受信独立前审，也不降为 `host_self`。受影响项保留 BLOCKED；其余方法、完整稿和修复工作继续。

## AC 映射（本文件不替代唯一执行台账）

| AC | 当前证据结论 |
|---|---|
| N6-01 | PASS：完整中性材料、委托、受众/目的/范围已固定并执行 |
| N6-02 | PASS（身份保存）：历史固定输入、阶段原始/成功接纳提案、首次完整未采用稿分开；不存在已成功接纳的完整 Page 稿，不能补造 |
| N6-03 | PASS：具体历史位置、旧方法缺口、三文件实质步骤与完整前后例 |
| N6-04 | BLOCKED（部分已完成）：新 manifest/hash 与真实 Host 完整稿可核对，正常任务尚未完成 Runtime Page 采用与适用前审 |
| N6-05 | BLOCKED（部分已完成）：真实 Narrative/Plan 提案与完整 Page 对应主线存在；正式当前指针未采用，无确认稿伪装 |
| N6-06 | BLOCKED（内容问题已修复并获实际非作者复核）：p04/p06 的原句、v2 Page/Plan/映射及完整依赖复查可核对；尚无 Runtime Page 采用/修订，真实审阅不冒认受信 receipt |
| N6-07 | PASS（内容范围）：无视觉/notes 修改，不要求也不宣称额外视觉产物 |
| N6-08 | PASS：先保存旧 hash，改完方法后新建任务，未重标历史稿/旧 Task |
| N6-09 | PASS（判断纪律）：未新增听众、人类签字或计时门槛；Runtime 能力/采用缺口明确保留 |
| N6-10 | BLOCKED（交接已提供）：方法/完整稿/证据可审阅，整卡关闭所需 Runtime 应用与修订仍未完成 |

没有相同条件的旧/新首稿对照，不声称总体提升、比例、速度或因果效果。当前可支持的结论是：实质方法已在此六页 Host 任务中应用；“缺记录写成未发生”和“缺失时间必须补齐”两项内容问题已在完整 Host 稿中修复，后者已获实际非作者复核；正式 Runtime 采用与修订闭环尚未完成。
