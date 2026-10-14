# RC3-01 方法与加载工程交接

**内容工程交接已形成（2026-10-14 18:48 UTC）：B 两份当前稿合格；Q1-A 对照有新开放 F2。文档尚待独立增量 review/提交后当前 head CI。**

基线：main `71c18f3acf87da7a7f62bf5501511f8179c1500c`（PR115 已合并）；方法产品提交 `1fb3ddacbb75a2d891b5a14d955cf23db9460931`，实施工作树 `impl/rc3-01`。该方法提交的工程检查与隔离安装已通过，十二锚点校准已完成限定范围的独立初判/修复/复评。四个真实 native 内容运行的首份 SDK 接纳完整稿和首轮独立内容 Review 已保存；Q1 接纳稿的口播含 controller 要求的机械 kind 纠正，不能称为未改动的原始 native 首稿。原作者正确 cue、SDK 拒收、接纳稿 F2 与运行限制分别保留。RC3-01-S01 最终 core `cc6150da513ce38060b0a8ad045ea5159a56cae6` 经第三轮独立 review PASS，新 A/B 安装和四份 fresh 复核已正式执行。B 的 Q1/Q2 当前内容 gate pass，固定稿可交后序卡；A 残余失败保留。详细身份/hash/范围见 [实际内容工程交接](RC3-01-HANDOFF.md)，不把该工程出口扩大为 E1 方法效果、全体 AC/CQ 或人类专业发布。

## 本卡实施

五份 canonical 方法分别补齐全文材料消费、用途/权威/已知未知/条件、实质论证与逐页增量、四类完整正反页、六组成对浅稿及具体返修。四类是方法覆盖，不规定每稿四类齐全。保留培训、研究、阅读和说明任务，不统一套销售结构。

纠正既有 `54 条需补问版本`：Q2 观察是 `120 条中 54 条首次提交缺型号或版本`，不是补问计数、唯一主因或 45% 收益。推理必须保留前提/测量限制。Plan 不复制 Page 正文，atom/source/Narrative/notes 映射保持现行合同；必要限定上屏，制作记录内部留存。篇幅 exact/target/max、口播/互动/总时长、cues/verbatim/none、已确认稿 fidelity 与越界问题按有效任务范围处理。

`method_resources` 新增唯一 `content-calibration` ID，只有 preproduction review 增加这一读取资源；普通 compose、输入修订、最终 review 和版本号保持现行协议。前审的真实 packet 仍包括 Task、完整来源 extract、Narrative、Plan、全部页正文和 notes。既有 Runtime/provider 边界继续生效，默认没有 provider 时为 needs_reviewer；普通独立模型可由受信非作者 native controller 的实际观察形成 host_attested 回执，不要求平台密码学签名。synthetic provider 仅在测试使用，不作为真实独立执行/人类专业验收。

五固定 CyberPPT 全文读取及原始 SHA/字节/行覆盖见 `rc3-01-method-source-consumption.json`；固定 commit 为 `980e5576565f0673c67ee41b01d20ed66cb8417c`。学习实际对象证据、内容关系和静态/渲染复核；参考脚本、生成器锁和审批规则不作为本次执行授权。仅选择 b00df87 的五 canonical 方法相关内容，并补正/扩展；没有引入其他混合代码。

## 活动原件与历史

上传 R2 活动锚点 SHA `3f58b7392b30ceb4304699071cc12cc6b4eff487af512b48e4121a1e43efb2bc` 按原字节接收。旧锚点 `42774a7006dec5e8e319cfbd9c58d0cf9c3cc52f1e67793d81cfb9133643ad4c` 原字节归档；五份旧 evaluation 原件保留原位置和字节。fixture manifest 区分 current_inputs、historical_reviewed_inputs 与 historical_artifacts，记录当前规范在导入时未执行独立重评。README 标明历史 pass 不自动关闭新 CQ。

锚点导入属于规范一致性修正，不是双盲结果。控制映射、期望标签和投放归实验控制方；真实独立初判、分歧和裁决另存，不发标签给 judge。原始完整稿、至多一次自主返修后的首次 Owner 稿、后续修改和方法复跑分别保留，不用当前稿改好回写历史首稿通过。

## 当前 canonical 方法身份

| 方法 ID | SHA-256（UTF-8 原字节） | bytes |
|---|---|---|
| `source-reading` | `44eb27513dc6af907484ca0b60d77a0aa211ffe1f6d43339876ab6a904e18f08` | 6353 |
| `content-methods` | `ca27c8fea86784d1236c2b5d13ff51ad8616a5f594ce8ca037742def1dc71130` | 16268 |
| `content-examples` | `cace2f4dfb12c904bcaa4b011239cc186516510fbe90a56cfc2b35f53f6c995d` | 12121 |
| `content-calibration` | `bb672652bf1f0e7c1248a423af8ce432793bc0eb2fd4905c9a423ebea0a9718c` | 7824 |
| `review-and-repair` | `cf66ea3c6ad0c5776ebf8feb409f00530369823368fcb6f44f11c05b93b63f20` | 5838 |

实际消费示例：从当前 review 工作单取 task_id，运行 `deck-master methods --project <project> --task-id <task_id>`，保存返回的真实全文和 dispatch/current 方法身份。`basis_changed` 不重标旧任务；缺文件报错，不借另一个安装的旧方法。`methods --kind review --intent preproduction --read` 可只读当前安装内容。返回文本证明 Runtime 交付字节，Host 应用方法与专业效果由真实执行档案证明。

## 验证及尚缺证据

owner targeted：`test_rc3_content_methods`、`test_rc3_early_methods`、`test_content_preproduction_review`、`test_content_mapping_claims`、`test_compose_v2_phases`、`test_flow_quality` 共 122 passed。Ruff 和 git diff --check 通过。env-01 的 module_origin 为本卡 src，不混用 /source。新增测试覆盖真实前审 Task 读取五方法和完整 packet、只变 calibration 的旧任务 basis_changed、缺 calibration 拒读且保留原 Task/packet/current、默认真实 needs_reviewer、当前 R2 与历史原件 hash 关系。测试 provider 明确 synthetic L1。

固定 `1fb3dda` 的独立代码/方法审查 PASS，独立 focused 50 passed；root 全非 browser/render 回归 1677 passed、455 deselected，该旧 head 的 7 CI success（由 root 核对报告）。隔离 wheel SHA `7a5140186dc329bb8c8955b93ce9ce42d6aec57f5e5af3afbc218c548da345ed`，source tree `40e5e25c95bebea0407b0c44e0c1d00ebb5560d7`，source/package/install 245 文件一致。检查记录来自 root/独立 reviewer，本 owner 不冒称自己执行了这些检查。新 S01 第三轮独立 review PASS、162 targeted、Ruff/diff-check；root 广泛首次 1742 passed/455 deselected，五项因遗漏离线环境导致安装 DNS 失败，原日志保留。无新代码离线复跑五项 5 passed/17.41s，合计覆盖 1747，不能说是单次全绿。新 A/B 同共通修复四 core 模块、分别保留原 Skill 字节，A 244/B 245 文件源/包/安装一致，实际 HOME 未变。旧 1fb3 七 CI 不代表 cc6150 或本次最终 docs head；当前 head CI 待 root push 后执行。

实际记录原工作路径位于 root 受控 workspace，公开选定原字节由 root 导入 [native 内容交接证据](native-content-handoff-20261014/README.md) 并用 [manifest](native-content-handoff-20261014/manifest.json) 定位：115 原件/6479571 bytes，manifest SHA `dd3c276256a8eed0059f1f572643805043f3689c5b4eb7df6ff767432c89a0aa`，另两份导航文件。下面记录固定文件名/hash，仓库不导入运行用 .deckmaster/.venv 目录。对照原始 RC3-01 卡、R2 I01/I02/CQ-01/02/11 和唯一 ACCEPTANCE §1.1/1.2/1.2.1，工程接口、合成校准、真实内容前审与后续使用/人类/文件验收分层登记。

## 十二锚点校准：已完成范围与原始限制

公开证据见 [完整校准报告](anchor-calibration-20261014/report/rc3-01-anchor-calibration.md)、[完整替换/来源与机器摘要](anchor-calibration-20261014/report/rc3-01-anchor-calibration.json) 和 [路径/hash 映射](anchor-calibration-20261014/path-mapping-manifest.json)。两位 fresh native 评价者各匿名初判 16 项：12 负例、4 正对照；冻结初判之后才解盲和裁决。12 项实质修复冻结后，由原两位各自完整复评，24 项 `none/pass`。4 正对照只保留原初判 pass，未假称再次复评。原 12 负例的 fail/needs_review 没有被当前修复 pass 覆盖。

AN-Q3-2 必须保留三份结论：原 A `F0/fail`，原 B `F2/fail`，root 本次来源限定裁决 `F2/fail`；历史 R2 F1 原段也保留。此次范围仅 P2–P5 正文/限定移至 notes，P1/P6 和既有中心/章节关系仍在；恢复该局部可见内容不等于更换主线，不强制旧 8/2/2 分布。不声称 A 已改判或两初判一致。AN-Q2-5 原两人 `F2/needs_review` 也保持原判，后续完整条件未来段是新修复。

A 复评收到 canonical FINAL，但 roster 淘汰前未观察到 `list completed`；B 的 canonical FINAL 与 `list completed` 均实际观察到。两份原复评输出/读日志保持原字节，不补 A 的历史 completed。复评允许原 judge 记得自己的初判，未读取他评或 root 裁决；不是重新 fresh 初判。native 观察为 host_attested，平台 event/签名/未暴露模型配置 unknown；本锚点校准没有消费 SDK Review gate 回执，更没有人类签字。

已核对公开复制的 38 个原件共 912285 bytes，hash 全与路径映射相符；另两份导航文件使目录共 40 文件。历史 `evidence/repair/controller/historical-q3-2.raw.md` 原末尾空行有唯一 `new blank line at EOF` whitespace 提示，按原字节保留，不裁剪，也不声称全部新增原件零 warning。此处的校准 PASS 仅支持本卡第 5 项/AC-B03/CQ-11 的合成校准范围，不能替代六组成对浅稿的其他实际覆盖、Native Writer 效果或整卡 ready。

## E1 实际内容子任务：原 native 输出、SDK 接纳稿与 Review 分列

四个真实 native 内容运行来自安装 A `575eca2/90a59eec…` 与 B `1fb3dda/7a514018…`，双方原输入、页数/时间/口播预算及最多四个实质阶段保持冻结。四份 `raw-first-complete-draft.json` 是首份 SDK 接纳完整稿快照；Q1 的原 speech envelope 本来正确将 nonspoken 互动标 cue，但旧 SDK 拒收，原未成功采用的文件与限制另存。Q1 快照已包含其后 controller 要求的机械 kind 纠正，不能据文件名把它当成未改动的 first-native 内容。实际首轮前审均正式 SDK accepted；accepted 指协议接纳，不能把 Review 的 fail/needs_review 改称通过。当前是 Q1/Q2 两臂内容子任务，公开同题 `seen_example=true`；不是原十二完整 Host 会话，也不是陌生迁移或盲效果比较。

| 首轮 Review（对象为 SDK 接纳稿） | argument | page_copy | progression | speech | 实质问题/限制 |
|---|---|---|---|---|---|
| Q1-A | pass | fail | fail | fail | 原 page_copy 的 P06 练习答案提前可见/反馈顺序 F2；controller 机械纠正后的主持段标 verbatim F2；控制确认缺口另记 needs_judgment |
| Q1-B | needs_review | pass | pass | fail | 控制确认缺口另记 needs_judgment；controller 机械纠正后的 P05 主持/互动段标 verbatim F2，原 native 三段正确 cue |
| Q2-A | pass | pass | pass | pass | P03 一项简繁文字 F3/advisory；不把内容前审 pass 当实测十分钟或业务效果 |
| Q2-B | pass | pass | pass | needs_review | 唯一 finding 为未实际完整试讲的 needs_judgment；没有已确定超时或 F0–F2 内容失败 |

首份 SDK 接纳完整稿快照 hash（Q1 含机械 kind 纠正，不冒称 untouched first-native）：Q1-A `27ae55d1b4beaf2d3dae915354cbd64749e2189cc8af0f7ac408d781adf77620`；Q1-B `ecc05cb06e0a983145233befe09cc7e65db295fe4fdee777beb00ede5fa8636b`；Q2-A `7a65dbc17acdaced36fabaa51cd5383e6633bac42df290a3a5441c14ed74d6ea`；Q2-B `240a1d9fb1937e3f551cce134b6a4cd3db01c3a4ef0a1ce83d87024d4fa770ff`。每臂 `raw-first-complete-draft.json` 和 `stages/05-independent-review/model-output.json` 保留，不用后续当前版本倒写。

四首轮真实独立 Review 由非作者 native controller 观察，经显式注册 ProviderRuntime 接纳，绑定 Task/packet/subjects/result/authors 与只写 review 范围；四臂 ordinary JSON context 和 changed-result replay 负控均拒绝。provider 只具独立模型回执能力，verified_user/human=false；不是平台签名或反同权限恶意 Host 的证明。重启后重新观察 native 可达/完成与当前 bootstrap，不推断重启前未见的 roster 状态。

只读范围核对 `rc3-01-preproduction-scope-audit.md`（原报告 SHA `445e272010887fee3c49873870e9fff564b0bc412e043335954a22317731e601`，选定原件经公开 manifest 定位）明确：Q1 的合成方向采用与 `content_only/content_full` 请求只是六页内容前置，零视觉授权/调用/产物；原主线→P5 试样→再授权其余五页的门序仍保留，不能因未有样页确认推断本轮已越权视觉生产。Q2-B 的纯未试讲风险应交 AC-U03/use_validation 的后续真实计时，前审仍须核算估算可行性。该范围裁决不重写原 Review、不自动代填 pass、不关闭 Q1 已确定 F2，也不能 report-only 绕过 gate；Q2-B 未试讲也不据此成为 AC-M03 前审通过证据。原 needs_judgment 已由 fresh 独立核验者按具体原规范/实际控制证据提交显式 replacement/accepted_variance 并由正式协议消费；原 raw 不改，实际完整试讲仍单列 NOT_RUN。

Q1-A page_copy 实质返修正式 SDK accepted（raw SHA `c9bfa31a3fe6511c1a582d4fccc7bf068d11208e2b73d2e34bbd3ab40c37a64a`）；两份 repair-speech 原 raw 经新 SDK 正式接纳，旧拒绝不改。四个 fresh verifier 已完成/正式接纳：Q1-A 首份 SDK 接纳稿三项 F2 fixed（speech 分类源于 controller 机械纠正），但新发现漏测“交接完成≠解决”的 F2，当前 gate 缺 page_copy、未 Ownerfreeze；Q1-B、Q2-A、Q2-B 当前四 unit/gate pass，三个首次供 Owner 快照已冻结。B 两稿工程交接，A 失败保留；不追加第二次 Writer 反馈修到 PASS。人类 Owner 未审，不能把“首次供 Owner 稿”称为 Owner 已接受。

## 实际暴露、S01 必要修复与效果限制

Q1 第一位 speech Writer 的原始 native envelope 本来正确将 nonspoken 互动段标 cue：A raw SHA `e01881d913f23c6ee88ac7ae45eef25f27f137a0968e68630f00b8cf09ad3013`，B raw SHA `fb830a670821652782b409543ac99631c80c48591853fde584e0f6d30733c5f6`。旧 SDK 对 verbatim task 严格要求全段 verbatim，拒绝了这些合法 cue；controller 要求同一实际作者仅改 kind，接纳后独立 Reviewer 才给 speech F2。该 F2 是首份 SDK 接纳稿在机械纠正后的真实缺陷，不能归因为原始 native 作者误标互动或方法质量失败。原 native 输出未成功 formal adopt，其正确语义/未采用状态和原拒绝均保留。A 至少一额外 native turn；B attempt-03 原记录为两次 metadata 修正加一次 verification，共三个额外 native turns，含 attempt-02 的实际拒绝。原 raw、差异、拒绝、作者语义限制和真实 followup 完成均保留，不能当作恰好四个模型 turn 或一次无瑕疵正式链成功。Q1-B 本轮 repair 只恢复原来三段 cue，原文本、映射及 20/30/10 秒估计均不变；它是恢复被协议强改的分类，不是重新写出更好的原始口播。Q1-A 另有原 page_copy 练习答案提前可见的真正内容 F2，已真实修改正文和衔接；该实质返修与 speech 协议归因分开。

Root 已据实际复现授权 **RC3-01-S01**：修正 verbatim task 错拒真实 nonspoken cue，以及 preproduction gate 未消费中央 `Review.finding_closed/replaces`。由独立产品 owner 最小修复并受审；本方法/ledger owner 不改功能。必须用正式路径验证合法提示/互动与逐字口播并存、旧错分类仍拒/报、既有 finding 的真实修订/复核可被 gate 消费、关闭不能自报或泛化为清除未解决问题，并保留取消/晚到/结果精确绑定/历史原件。S01 对官方 null 全稿 finding 闭合的第三轮独立 review 最终 PASS，原两轮 REQUEST_CHANGES 及修复依据保留。新 SDK 的真实消费和中央 explicit closure 由四份 fresh 内容核验与 gate 结果验证，不能用修复后的新 pass 抹开放新 finding；Q1-A 新 F2 仍真实阻塞。软件修复处理共通协议缺陷，不回写原冻结 Runtime 的拒收/失败。RC3-05 应分别解释原始作者质量、controller 机械纠正后的分类变化和正式执行链失败，并在修复后的共同 Runtime 基础上做 A/B 公平复跑；不能以旧运行修好后回填来证明原方法效果。

Q1-A page_copy 返修作者实际调用 `collaboration.list_agents`，意外读到其他臂 FINAL 摘要。作者报告未读其他臂文件、未采用其内容，但 controller 不能证明没有影响。`repair-page-copy-integrity-exposure.json` 原记录保留：该返修可供真实 native 作者/SDK消费和局部工程交接核对，**不能作为洁净盲 A/B 方法效果样本**。暴露发生在原始稿之后，不改写原始稿身份；首次供 Owner/返修效果的污染另列。后续实际阶段不再列全树，不用自报“未使用”消除这项限制。

本次首轮真实前审是独立审阅，不宣称版本身份已盲化。E1 的 C 原生参考臂、各臂原稿/返修匿名效果评阅与裁决、陌生实例迁移、方法修改后原输入复跑仍由 RC3-05 按冻结协议汇总；额外 turns、SDK修正、重启与污染必须随成绩一起报告。人类 Owner/L4、受众/L5、完整试讲/AC-U03、目标桌面/文件专业验收按用户明确安排后置，均 NOT_RUN；不改实际 HOME。

## 对原规划的交接清单

| 原卡/AC/CQ | 已具备工程证据 | actualfinalhandoff / 后续待证据 |
|---|---|---|
| 工作 1–2；CQ-01 方法部分 | 五方法、四类完整正反页，固定全文/来源/hash；独立方法审查 | 当前范围完整稿/预算/映射固定，真实逐页增量与必要限定审查记录；不以示例替代生成稿 |
| 工作 3；M01/M04 | 四个真实内容运行的作者原件、SDK 接纳快照与前审分列；Q2 两臂的实质正文均被审 | B 两份合格全文/Refs/Plan/notes/scope 可交 RC3-03；A 原项已关闭但新练习漏测 F2 阻塞，保持当前不合格对照，后续效果不能省略 |
| 工作 4；CQ-02/M05 | 六对公开校准已被派发，真实前审读取全材料/任务/全稿并定位实际缺陷 | 六组浅稿/合理稀疏/不确定性逐组独立定位与实质修订覆盖仍待后续准确索引；十二旧锚点不能机械冒充这六对全部运行 |
| 工作 5；B03/CQ-11 | 匿名独立初判、来源限定裁决、12 实质修复/24 独立复评及原字节索引 | 只签合成锚点校准范围；A 原分歧/未观察 roster completed 与旧原判永久保留 |
| 工作 6；B02、M01–M05 | 双方隔离安装实际 task claim/read、四个实质阶段的作者原件及接纳快照、一次首审、额外 turns/费用/范围事实 | S01 复审/检查/新安装及四份 fresh 复核完成，B 两当前稿已固定；原三首次供 Owner 快照在合格 gate 下冻结。新的同修复 A/B 公平复跑及 E1 完整三臂效果归 RC3-05，不抹原链失败/额外 turns/污染 |
| 工作 7；M02/M03 | speech-policy/双用途/fidelity 方法与旧协议回归；live cues/verbatim 真实稿 | S01 允许真实主持 cue/互动并保留逐字内容的正式路径已验证；Q3 read_alone/none、mixed/同源两版的真实版本化产物与授权内零额外生产；Q2 五分钟变更/取舍验证与后续真实计时 |

产品卡内容工程出口已形成：S01 第三轮 review PASS，新 A/B 安装及受信独立核验真实完成，B 的 Q1/Q2 当前全文、Plan/mapping/notes 固定且 current gate pass。交 RC3-02/03 时只交范围内内容输入；A 新 F2 不被 B 成功抵消，不授权额外视觉生产。B03/CQ-11 仅合成校准范围 PASS，其余本卡 6 AC/2 CQ 最终适用证据继续缺证/回填，工程交接不关闭 RC3-05 效果、人类或全套发布验收。当前 docs 增量与 push 后最终 head CI 尚待 root 处理，release_conclusion 仍 NOT_RUN，其余 Owner 条目不改。
