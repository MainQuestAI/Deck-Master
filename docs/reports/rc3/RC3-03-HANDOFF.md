# RC3-03 密度设计、关系保真与实际 native 工程交接（实际单页链已闭环，待文档终审/最终CI）

运行代码、合同、方法与测试冻结于 `cf61e5e717fc852263b5a5baf4d97a07e126362b` / tree `96188d691ced737113019aea4a61a769812f6794`；本次仅准备可审阅文档。真实图像在805执行，真实SVG/native链在固定5db安装执行，cf61的代码/回归复审与reader兼容另列，不把它们混成一个执行版本。当前v3真实compile/readback/render、尺寸/逐run字号正确；Task24962551ff10三项page_visual实际SDK accepted/completed PASS，run06独立headless机械A–D结果符合预期。**F07只对精确新SVG/PPT与新review关闭，本卡单页native工程链已成立；原37AC/13CQ完整专业验收、未覆盖风险和整体RC3未关闭。** Root已保存最终report/完整FINAL与agent completed观察；本文档独立终审/全7CI/PR合并仍待，不凭代码或实际单页通过代签这些事件。当前文档身份以包含本清单的Git commit及Root后续准确tree记录为准。

[证据导航](native-design-handoff-20261015/README.md)、[逐字节复制清单](native-design-handoff-20261015/manifest.json)、[原卡逐项映射](native-design-handoff-20261015/acceptance-map.md)、[实际分相记录](native-design-handoff-20261015/actual-chain-phases.json)供审阅。旧失败与原观察独立保留；[唯一37 AC/13 CQ台账](evidence-ledger.json)仍是最终结论位置，六个本卡条目的专业状态尚未关闭。

## 原卡与当前结论

原不可变 `RC3-03.md` 的工程目标是：无需旧蓝图形成真实代表候选，完整内容/密度进入请求，关系与主要信息可编辑，范围调用不扩大。原卡工作 7 的公平 E2/E3 及全部适用 AC/CQ 最终关闭仍遵循 RC3 ACCEPTANCE 与 v1.2 ACCEPTANCE；工程交接不自动签专业 AC。

已观察到固定软件/合同/方法接口、正式SDK合成正负轨迹、真实Q2-B p04图像/native consumed/candidate/非作者阅图/显式同页采用，以及实际v1/v2/v3 SVG、preview/native PPTX/readback/render。v1物理尺寸失败、再次转换字号失败、v2真实readability失败均保留；v3当前实测尺寸/字号/内容回读正确，新subjects下非作者视觉与独立机械均有真实终态，原失败不会由新PASS覆盖。此结论只交接单页工程，不替代全风险、公平E2/E3、真实人类或桌面。

复制清单逐项给出白名单原件路径、repo内副本路径、大小与SHA；原始运行项目/安装树/缓存/私钥不复制。失败索引保留每个正式固定HEAD及dirty/live诊断边界。本文及分相/映射均为开发交接导航，不新增Runtime批准状态或第二套AC结论。

## 版本、审查与正式检查

| 阶段 | HEAD / tree | 真实结论 |
|---|---|---|
| RC3-02 实际合并基线 | da7bcbc97475d10907b0c795026af5652c3a95d9 / 9f18bc200508dbcec03c2acd05ab73b9bd3d95ee | 继承 getter、Page/Plan/notes/scope 与 rc3.v1 floor；不当成03专业验收 |
| 03 R1 | 4e342b81390186b8b090bc31ffa6af7bef46b165 / 7c801ed0f4383969c3169fa5868cba2ab47e459d | code 与 regression REQUEST_CHANGES；Owner unit2000+1FAIL、render70+1FAIL |
| 03 R2 | 5fa4834b3d07d1a0690ed53f8259d20572db7694 / a1fe4405c54632a7e5fa848d0d022c17d80dde38 | F1–F5复现通过；F6独立RQ；Owner unit2066/render71/ruff PASS |
| 03 R3 / 实际图像安装 | 8057905162f20926cfc1a0a96252bc6745f4e700 / dda627ebcaa016716ebba0be16288ab573ce1e82 | F6双独立PASS；Owner fixed affected117/ruff PASS；真实image/候选/采用发生在此安装，不重绑定成5db调用 |
| 实际交接 R4 | 同805 | 实际重建工单丢 requirements/basis/recipe，F7 REQUEST_CHANGES；原旧Task与workorder永久保留 |
| 03 R5 | 9dc661989e930c9fc08d7d179390e7cc61d47748 / 495f23e60d386a4199d3861c676f0d926c7f6c48 | F7全context已修；F8 direct accept独立2FAIL/5PASS，RQ；Owner broad环境失败，不能写全PASS |
| R6 / 实际下游安装 | 5dbdf72089d6625449a23a52ef3e23859c597b4e / 1b69a05050c63d0a2fbc4aaac86350611ad9f504 | handoff limited PASS（自跑source41+独立17）；regression limited PASS（176 selected+独立5）；后来独立scope审计真实发现F9，旧RQ不覆盖 |
| 当前 R7 / F9 reader | cf61e5e717fc852263b5a5baf4d97a07e126362b / 96188d691ced737113019aea4a61a769812f6794 | scope独立limited PASS（47selected、公开/只读/跨真旧安装/费用对照）；regression独立limited PASS（217selected+5probes）；Owner固定affected349/ruff PASS；实际p04只读资格重核保持原805/5db来源 |

5db Owner完整固定检查：unit **2111 PASS /474 deselected**，render **71 PASS /2514 deselected /22 Pillow getdata弃用警告**，ruff PASS；0 fail/error/skip。before/after全 **2913** tracked SHA、HEAD/tree/clean、6模块origin与专属absolute Python均相同。整个父环境显式 `PIP_NO_INDEX=1`、`PIP_FIND_LINKS=/workspace/work/rc3/wheelhouse`、短TMPDIR，所有子进程继承。它不是cf61的新fullsuite结果。

包 `rc3-03-5dbdf-fixed-verification.json` SHA `3fca6593d98661bb714be7854d9e84180bc373a2c54212cc449e1d67b6ec6500`；unit log `7d79f1e9e0b5c975d198f953de2c75cc5d86d2b7143fe366d3752cb8b374358a`；render `6ce7d682758ad304d62d82d2f614994aaf01548cc97932f5a3562c4a9c1d6ad8`；ruff `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。该包的 actual_pilot 字段如实保留当时 pending，不修改为后续完成。

cf61固定最小影响验证为 **349 PASS /2 render deselected /86.57s**、全src/tests ruff PASS，0fail/error/skip；全部 **2914** tracked SHA、HEAD/tree/clean、9模块origins和安装身份前后完全相同。packet `rc3-03-cf61e-fixed-verification.json` SHA `5d9c5e2d2dff0defb504407418b4c6b3e78fced7434fe0798b2d3e342bda11d2`；原unit log `2ef4ebe31e92b844ec8fae7811828470530976e335a170c6b6bbe22308559513`。此范围包含F9、requirements/recipe/workflow/feasibility/restyle、native reuse、notes/Plan、F7/F8、legacy candidate/styles及当前内容预审；不是fullunit/render/browser/CI。Root新的isolated wheel/source/package/method共256文件一致，manifest `673ba5c39f11d3c53f08d19990bfd9ddbf89a28376d23b3ee813176ed1b12f82`，wheel `a8d812c66ca36c8d47a435b9a77b7967368878c68d6cbe56afb124b464c2a2c3`，release `cf61e5e717fc-a8d812c66ca3`。03 CI/PR/merge未签PASS；02 CI只属于02版本。

## F1–F9 修复闭环（代码审查编号，不是 ACCEPTANCE 的严重度 F0–F3）

| finding | 原触发版本与事实 | 修复版本与边界 | 关闭证据 |
|---|---|---|---|
| F1 | 4e missing data默认写“示意数据”兜底 | 5fa 必需量化依据缺失回内容；明确非量化教学/机制示意可留 | R2/R3原独立prompt复现PASS；原R1失败报告保留 |
| F2 | 4e notes-only改whole PageRef使native proof降级 | 5fa control只含scoped visual digest；共享task freshness保notes/P2正例，body/role/arrow/target/control负例及consumed/unknown保留 | R2/R3独立配对与native_visual_reuse；不改原Request/费用 |
| F3 | 4e classic旧Task暗消费新requirements但无cap | 5fa 按真实协议 ancestry保旧Prep/dispatch；新格式精确cap及同CAS rc3.v1 | 原classic与新缺cap独立复现PASS；不把技术floor当授权 |
| F4 | 4e summary重算旧/默认context | 5fa blueprint summary用完整immutable getter；旧prompt前缀仍原样读 | R2/R3历史真实R1 Request读取及summary等值PASS |
| F5 | 4e 正式0call design.feasibility/propose grant被styles.propose硬查旧action拒 | 5fa registry/schema/eligibility/方法限纯planning兼容；无Page真实Narr/Plan、命名Page不越scope、空pages不变all | R2/R3正式feasibility正负与实际805零call feasibility |
| F6 | 5fa 无口播none/none的source-only变更stale图像 | 805仅normalize该未消费origin，原PlanRef和active speech/file依赖保留 | R3双独立PASS；before/after opaque context两相pair及candidate_ready |
| F7 | 805真实已采用图→reconstruct丢全context，style deps回default | 9dc owned Artifact→Request→Attempt→author Task.inputs唯一完整来源；writer/asset/SVG basis/pagevisual同源，legacy不伪升级；preproduction仍可先审内容 | R5 actual805全11keys/current consumed/coldread PASS，全部原件hash不变；29 source+独立5保护用例 |
| F8 | 9dc 新direct changes.v1消费者无claim或损坏saved cap仍采用 | 5db 通用accept在既有费用结算之后要求running/execution_ref/check_host；原exact terminal recovery在其前；无fake change_binding | R6原2失败独立重跑拒绝，三类consumer正负+terminal replay PASS；41 source、176reg、完整2111/71 |
| F9 | 5db公开同ID同值Decision replaces后resolver收旧Ref而拒；仅审计Ref混入consumed，真实Decision变更又可能被content_identity快路漏过 | cf61只收真实current head，以实际Decision identity+registered effective SHA比较；全audit Ref保真；现代actual preparation比较在快路前；旧candidate exact digest仅在完整消费等值后复用自身owned frozen audit壳 | R7 scope正式最终报告SHA `59d80f3e4bd0e811b3126a6841eca25e8bc469dcc42a3fd57119857db182dc98`；reg报告SHA `6a207902a22f0bd8b74bef7617334f675453011d6c232b8b8a942a271fe28bc4`；真5db候选→cf读取/采用、falsehash拒、费用正负。实际p04只读资格重核只属于其选定旧revision `eea9ee0eb41242a59d3e75d687426527`，不能沿称新SVG后的旧review仍current |

F7/F8修复不重认证已关闭805原调用，也不把新reader安装身份冒充原执行安装。source Request/Attempt/proof/原PNG始终保持805原件。

## 所有旧失败保留与归因

- 4e 正式 unit 1FAIL 是旧 run_desk fixture 对 writer floor 的过期预期；render 1FAIL 是旧 installed positive 把表格原子放同一列/行导致真实关系检查拒绝。5fa修正式期望及真实行列SVG，不降门禁；旧log/packet不改。
- 4e 两独立 RQ、5fa F6 独立 RQ、805 actual F7 RQ、9dc F8独立 RQ按上述固定head保留，不把旧失败涂为后来PASS。
- 9dc formal unit **2094 PASS +2FAIL +3ERROR /474 deselected**，render **69 PASS +1FAIL +1ERROR /2502 deselected /22warnings**。都来自临时安装 pip/setuptools>=77 的 DNS/离线参数遗漏；不是产品断言PASS。Owner启动漏offline env已明确纠正；raw packet SHA `f9d33eea90e8337cc2483478d1b20510fdaae6df7c0a1aeb03056ef72c420799`，三log及before/after保留。当前5db全套在显式offline环境重跑通过，不覆盖旧环境失败。
- Native关系baseline曾实际漏行/列、责任绑定与物理归属；visible arrowhead反向而端点不变也有定向诊断/修复；当前render71含实际native-only坏例与几何正例。早期部分live模型/源码混合、selector/harness错误均仅诊断，不能倒签成clean HEAD正式PASS。
- F6第一次新测试调用不存在helper._accept；F7首轮page_visual输入缺SVG/preview、change_intent漏字段及plan_id读取错误；F7同时发现并实修target降legacy、classic generated_from_page、initial compose proposed Page与preproduction阶段边界。原focused失败log仍在，属于dirty/live修复上下文，不凭后续commit给它们虚构固定tree。
- Root private controller/helper R1–R3与entry helper R1–R3原报告保持；其合成probes是L1。actual run-01 request-start后grant的stop_conditions自然语言被schema拒绝，失败原件保留；grant未落地、未begin、0真实image、无费用结算记录。Root修helper并独立delta审后全新run-02，不复写失败项目。
- F9 Owner live R1为20PASS；补测试后的R2为21PASS/3FAIL，三项真实SDK已正确抛 `AdoptionConflict`，是新增断言误写成 `TaskConflict`；修预期后的R3为24PASS。live日志不绑定cf61 clean正式结论；cf61固定349与两独立复审另列。原5db scope RQ继续保留，不倒签原版本PASS。
- F05辅助测量helper首次修订 `0a148342…` 只查global min/max且漏无sz文字run，独立RQ；后续 `7fe47e10d9e419cd8408aa8316c032fca6ff122e2e15059c118419ac27232251` 逐run按两个显式headingAtom与其余body检查，独立有限PASS（report SHA `ebea2703ebae4f3330eb8e0a228618748eb3df27923fd21d52b8a9f1d966e31e`）。早期inspect捕获mutable helper的竞争/缺输入traceback也保留，不改成产品或转换失败。

## 真实 pilot 的分相与当前边界

1. 原输入：真实合格 Q2-B 的8页 Page/Narrative/Plan/notes/citations；原内容-only grant不扩义。只读纯字节副本 source-copy-verification 保留。新controlled软件/效果测试指令及bounded计划由真实host_attested instruction登记，非verified_user/人类扮演。
2. **805安装实际phase**：0call feasibility→新p04-only scope，1call/1candidate→完整8935字符prompt冻结→image_gen真实1次，retry0→sealed native context→consumed/native accepted→candidate_ready。候选阶段不自动adopt/expand。
3. 原 PNG `1595347 bytes`，SHA `8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c`，实际 **1672×941 RGB**，请求1600×900 contain。保留原字节，不重编码伪装尺寸合规。未知 model/seed/price/platform invocation保持unknown/not_reported，不能写actual$0。
4. 真非作者 native agent查看原图与完整工作单，建议 **adopt_visual_reference_only**。其17原子/四节点/三箭头/两行三列实际观察不是Unicode逐码点证明；四findings须分列：F01主链适用条件视觉绑定偏弱；F02安全留白不足；F03表格/底部提示间距不足；F04实际画布尺寸差异。它们不是代码F1–F8，也不直接映射统一F0–F3严重度。
5. Root用完整 `assessment.json` 实际登记后续同页采用scope，显式adopt。原 `actual-reviewer-observation.json.actual_final_answer` 是缩写转录，**只算摘要**；必须同时索引 `actual-reviewer-observation-correction.json` 的精确原FINAL。两原件均不改；摘要不是verbatim、平台receipt或采用授权。
6. **805→5db相位切换**：旧reconstruct Task6626b919b45f/workorder保留，F7/F8修复与独立复审完成后Root显式cancel旧Task；新5db installed Task `a68c58884f9a` 消费完整public workorder开始真实SVG。原805执行identity与closedreceipt不因新reader变化失效，新的reader身份独立记录。这是跨source工程链，**不是共同候选公平E2/E3**。
7. **5db真实SVG v1与局部视觉评阅**：作者Task `a68c58884f9a` 的SVG实际接受，artifact `b65db8f40a6e6265813a9927e1ad287fe036e0f4d61df0f963269809a3b0fdd3`，SVG bytes SHA `1223a9d6c9c89bb998434395e58dfee8c77c3d95d918fca7b8a613c54739a00b`；实际预览SHA `654e94f95b34f61e2914da5ccf96d8442986751e2c6dec536c763c1f44af6cd6`。真实非作者Task `89aefcb92514` 完成且三项v2 page_visual accepted/PASS（revision `0dfb15da19a344b5a3452fa6f8e499ac`）；是 `independent_host/host_attested/identity_receipt=null`，不是sealed preproduction receipt/平台签名/人类。首次content/readback/native对象检查可复用，但新增转换缺陷单列。
8. **原生转换F05真实失败**：首次工程PPTX `c93179007f6e478a3ac8736d712e18a709519ddc7a027550228745619274a4ae` 实测 `15240000×8572500 EMU`，即16⅔×9.375in，工单要求13⅓×7.5in，比例仍16:9。Root helper把逻辑1600×900错当96ppi物理compile尺寸；正式pipeline本来使用 `slide_*_in×96=1280×720`，未发现产品尺寸缺口。原初机械JSON的pass仅反映其当时未检物理尺寸的检查范围，不足以盖过F05 HOLD。
9. **第二次真实转换：尺寸PASS、字号FAIL**：`run-03-native-ppt-correct-physical` 的PPTX SHA `8affb8957e63919b73ea8be326786b5a322b1bd94418b0bba53a6c092c66ca1e`，实测 `12192000×6858000 EMU`符合工单；全部35可见run实际14.4/24pt，低于各自body18/heading30pt，整体 `FAIL_TYPOGRAPHY`。`root-physical-unit-instruction-correction.json` 完整保留Root原“18pt=24px/30pt=40px”的错误作者指令及helper参数，明确Root遗漏SVG contain 0.8 scale；不归咎作者能力或假造产品缺陷。逐run角色用title与exceptions-heading两个固定Atom明确指定，不按字号/粗体猜角色。
10. **v2正确字号/尺寸，正式readability FAIL**：Task `955ec4bc6827` 实际接受SVG `82d3430688b9c4ff2fb89cedb99cabfd643fbb39cb03d274b65a60a2de245ded`；run04实际PPT `4c951dde9044506ad7cade8e06de13c50ed25e5173210265cd2b7c61d2c38ef6` 和render `35358c312eed62a02cf2bc25fe6cb83fb5aaa965ec5973bf3e8cd9a0e1d4a840` 实测13⅓×7.5in、36run18/30pt、60native/0picture。非作者Task `405175566aaf` 正式SDK accepted的结论是content PASS、fidelity PASS、**readability FAIL/F07 must_fix**，并非全PASS。F05/F06只对这份新产物关闭；原c931/8aff失败不回写。F07表头约9–10px、三行格约10–11px底部净空小于冻结12px；SVG约13–14px。XML表线坐标一致、native文字墨迹约下移3px，没有据单字体/LibreOffice直接修改全局`.88`。原模型FINAL/完成观察和crop测量均保留，report SHA `46714b217ac23866f6a41a8b97113cd06bda2d27d3972f893756583acd0c1a9e`。

11. **v3第二次自主layout修复与一次机械修正**：新Task `53be66431623` 同页/同grant，作者第三次真实任务执行、自主repair round2，原始模型SVG `97df8d71e641c778e644bbddbb9e98a68be9a1b08a2ef56068cd2e9ed7cce005` 的31px行距在真实字体ink检查中出现最多1px重叠；原SVG及首次失败保留。只做一次33px行距/容器联动机械修正，实际提交 `fb9eb0ce88c0db3cc7d0c82255ac1fefeec11cb6491aaa82c199446faa81b5a1`，与staging/accepted blob逐字相同，但**不等于原始模型首次SVG**。实际artifact `8c197386cb7168d3df1a6391559b29bcd9f5f7f08a69469fb89c27a53b17814d`，revision `ce601a8dd04543d5b15f7d968eb85ca2`。全文/关系/30px正文/50px两标题/48px外距/24px模块距/12px内距门槛均未放宽。Root完整FINAL/completed观察保留，不称零返修或首稿一次成功。

12. **v3实际PPT、新视觉与机械终态**：run06 PPTX SHA `0c145ff3f055c5c7926f97ee9ec5bdbd641bb4fbc1bcbbae732b7fd828d057c8`，实际render SHA `ca645a40136d48b072fd87b674cc6cb56d441715e10a102a449182bbb441cbc1`；实测EMU `12192000×6858000`、36run18/30pt、60native/0picture，真实readback PASS。新page_visual Task `24962551ff10` 正式SDK accepted/completed，selected revision `a8f7556fca0644ebb232c12949d00736`，blueprint_content/fidelity/readability三项均PASS。已冻结after-scope readback显示Page entries/Narr/Plan/outputs均不变，不再读取运行project current扩大delta。F07全9格×4边×双层检查含淡抗锯齿，SVG最小12px/PPT最小13px，行墨迹分离、模块净距24px；只对本轮精确SVG `fb9…` / PPT `0c145…` 与新review关闭。一次辅助脚本SyntaxError发生在任何SDK执行前，原错误保留，不记SDK失败。旧405评阅Task在新SVG后 `inputs_current=false`，失败记录保留；F9只读兼容的旧revision `eea9ee0eb41242a59d3e75d687426527` 也不能代替新artifact评阅。

13. **机械证据相位限定**：旧 `rc3-03-actual-ppt-mechanical-edit-run02/report.md` SHA `a6ae66e38f574ba42c612b72de41bd71b118cafa1ce13b5c9cdf06276ea339fc` 在c931旧大尺寸文件上真实完成native文字edit-save-reopen、相同35run/428字符行归属交换（仅2个table_cell_ownership_mismatch）、箭头反向（仅reversed_arrow）、真实main-chain+2px布局compile/readback正例。这些是headless工程观察，不能重标为修正尺寸下新文件的结果或PowerPoint桌面PASS。


14. **正确尺寸下独立机械闭环**：run06机械report SHA `480f00565cfe6eaab7f1f70464b6aa9de16b888e93d0299cedcb015c40382314`，manifest SHA `64938335b7a1585baec5ae4523220e8694b79fd0bfceb053547e921e8c90f9bf`。固定5db安装对精确0c145原件独立readback无findings；A native title edit-save-reopen真实持久、对未改Page应失败；B交换两action格各3个carrier且36run/428字符序列相同，仅2个ownership mismatch；C端点+可见箭头镜像，仅1个reversed_arrow；D真实SVG主链+2逻辑px，以正确1280×720重编，readback PASS。各copy物理尺寸/角色18-30pt/notes逐项核验。26对象真实移动15240EMU，34对象不动。它们是headless工程A–D，不是PowerPoint桌面或人类/公平E3；不复用旧尺寸常量或旧PASS。

实际模型工作阶段逐项留原始spawn/claim/FINAL/完成观察：图像工具1call/retry0；候选非作者阅图；SVG作者共3个实际Task执行（原v1、repair1 v2、repair2 v3），v3有1次明确机械spacing调整；page_visual至少包含v1已接收局部PASS、v2正式readabilityFAIL和当前v3实际三项PASS。它们不等于可核对provider API/model turn/token/fee总量；未知值保持unknown，不把作者repair或审阅次数藏入“零返修”。完整8页PageRefs/Narr/Plan/outputs持续保留，单页engineering PPTX不得登记成8页Document.outputs或全稿交付。

## 最终实际评阅与新reader重核身份

最终视觉 [report](native-design-handoff-20261015/raw/reviews/rc3-03-actual-page-visual-review-run06-v3/report.md) SHA `002fe5cd28172fcfb29de125284fad4e2ac92b4029c98d98b26c0c8139da5865`；assessment `bc94a17150511949cd2a79125841d16105aba629a551ac674be7746d35a4408f`；evidence manifest `cb383cb3e49d53da32e98da3896c33ccfad6c1aaa4cd2a4bd585961337def80e`；Root实际FINAL/完成观察 `46c5e55406671cac8b4c0d6d7e848eb23990eb5dcc2980d55687da6264fc9117`。这仍是 `independent_host/host_attested/identity_receipt=null`，没有将Host真实观察冒充平台签名或人类批准。

Root用真正cf61隔离安装SDK作 [终态只读重核](native-design-handoff-20261015/raw/native-image-pilot-03/run-06-final-readonly-requalification-cf61e5e.json)，SHA `3c8df25a358b2cc5ab10945f3e22e6d6ceb6c04ab29f19eb99dd38d3fd25c546`。只选定revision `a8f7556fca0644ebb232c12949d00736`：236项目文件、107纯输入文件、73原immutable objects逐hash不变；所有8PageRefs/其他7entries/Narr/Plan/Task/Sources/outputs/content_basis不变；完整11key实际context逐字等原805 frozen Request；249Task completed且inputs_current、三维PASS且全部deps current；256安装文件admission前后相同。没有新图、新SVG、新compile或review提交，它只证明新reader兼容，实际图像执行仍805，SVG/PPT/模型评阅执行仍5db。旧F9审计的eea9时点资格没有被重标为最终v3，此处另有新的准确证据。

## 未关闭与交给04/05

真实p04 chain的单页工程出口现有新视觉与机械终态支持；F05/字号/F07旧失败及返修原件仍保留，不能倒签首稿/旧版本通过。原卡AC-D03/CQ-05的研究/数据/架构及最密页风险，不能由一个机制+异常表p04或合成工程页代替。公平E2/E3、原12真实Host会话、两个任务Owner及各≥3真实受众、真实计时、目标PowerPoint桌面编辑保存重开、适用human professional delivery、全8页原生生产仍 **NOT_RUN，evidence=null**，按Root既定RC3-05安排。实际headless机械编辑证据不是“桌面用户已测试”。

真实评阅的A01限制继续保留：异常与恢复条件需要完整阅读下方表格，未测真实受众是否只看主链而误读。A02记录PPT模板`type=screen4x3`元数据仍在，实际cx/cy精确16:9且渲染无拉伸；不据模板标签推断已完成或失败的PowerPoint桌面行为。原PNG尺寸差异F04仍为已保留variance，不把它改成符合1600×900。

04仍负责全入口/四Skill/统一新建导入迁移/正式安装与恢复/交付集成。03不扩大到这些产品。最终方法/合同索引见本报告的原卡逐项映射；没有发现需要现在扩卡的新产品改动。旧方法开头“Desktop唯一已验收宿主”属于历史兼容表述，最终文档必须明确它不能证明本轮真实桌面或人类通过。候选当前详细失败消息中的旧“first try exactly one”措辞不得作为否定v3合法首批两页的证据；正式方法与实际guard/test支持1或2，改文案若需要应另行Root决策，当前不编辑冻结源码。


## 当前必须保留的后续边界与待文档终审项

- [04/05物理单位与双层padding交接](native-design-handoff-20261015/raw/reviews/rc3-04-native-svg-physical-units-supplement.md) SHA `5e62d762fd085a26c155ea8fc9ab2b105fdfe9c0f02d52f0f13ca3a4165c4dcd` 是未来方法/实测要求，NOT_RUN，不声称旧Task已消费它，也不把Root两次单位错误倒灌为产品缺陷。
- 当前运行代码/合同/方法仍cf61；所有报告新文件只构成文档delta。5db fullsuite2111/71、cf61影响面349及两独立限定复审各属准确版本，旧packet.actual_pilot pending保持历史值。
- 最终整体docs HEAD/tree、独立docs终审、全部7项CI以及PR/merge都需Root另行记录；此稿不会以运行代码已有PASS代签这些后续事件。
