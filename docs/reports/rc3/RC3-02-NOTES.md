# RC3-02 notes 与实际文件工程交接

RC3-02 已实现当前 Page notes → native PPTX → 选定容器导出 → 最终客户文件完整回读的路线，并修复 notes-only 的视觉复用、Plan links、最低 writer 与旧协议隔离。Runtime 实现 `ca0351d2397ba154e9f77363bd0f325629eb0ebd` / tree `05191deede70f26e661b28f4221c3c0d00ef2ecf` 第三轮独立 code/regression 均 FINAL PASS；原0d12固定文档 audit FINAL PASS 后，实际PR117四组unit CI暴露测试渲染依赖分界错误，已做bc0b39测试修复且第4轮code/regression影响复审均FINAL PASS，随后53f4真实CI的installed示例又发现正文notes-canary与Page不一致；65d8203已做examples-only修复、第五轮限定复审双FINAL PASS，真实installed w12完整9checks PASS；同版本完整installed recovery238PASS/1FAIL定位为图片decoded与下一帧真实fit的测试测量竞争，已做acf2b2e测试等待修复，准确三viewport/受控加载对照PASS，第六轮code/regression限定复审均FINAL PASS；新固定docs审与七CI仍待。当前完整代码冻结为acf2b2edd4a88f74e8b671a18e32eb74b780eb84，产品字节保持上述Runtime身份，尚未合并。目标桌面备注视图/编辑保存重开、真实 Owner/受众和专业使用验收仍 NOT_RUN，最终 N01–N04/CQ-06 保持 BLOCKED。

本卡基线 main `8e274576e7a93de7d10c054558991878501fff0c`。当前工程输入是明确合成三页与真实不可变文件；fixture 的权限、Review、native observation、费用是 L1 协议证据。实际 native PPTX、完整回读、LibreOffice/PDF/PNG 是 L6 文件工程证据，不等于目标 PowerPoint 或人类验收。RC3-01 的 Q1-B/Q2-B qualified owner-draft 可以供后续原稿实际交接，但本卡合成包不能替代它们或原 E1 公平效果结论，也没有新增视觉授权。

## 共享实现与后续卡消费

- `production.stored_blueprint_request(store, task)` 只从真实 `Task.inputs` 取唯一 immutable request，核对 schema、稳定身份与 prompt。缺失、冲突、坏 Ref 明确拒绝，不创建 Task.preparation 副本。
- `visual_dependencies.py` 统一客户可见内容 + 完整 visual_spec 的消费切片、实际历史 Page 等价、scoped Plan role 与全局顺序；generation/tasks/candidates/styles/workbench/review/eligibility 共同消费。notes-only 不改原视觉 Ref、Review 字节、freeze/request/hash、allowance、attempt；真实语义、箭头、归属、目标原图、style/font/权限变化仍阻塞。历史 Page 不被全局标成 current。
- `content_plan.refresh_v2_plan_links` 是手改与 speech 共用落点，bound/imported_mapping、null Narrative 均检查完整稳定 ID 与实际 before/after Ref；只更新合法 links/版本审计，保留角色、预算、来源和原确认状态。seeded imported_mapping 明示不是 RC3-04 正式 import E2E。
- native 编译按稳定 page_id 写 notes，LF 归一化保留连续空行与末段。`pipeline.output_matches_current_svg` 共同验证 ordered SVG 与 page_notes 依赖；notes 改动使旧 PPTX/ppt_preview/file review 过期，SVG/svg_preview 与适用视觉 review 可复用。开放 must_fix 不能因整 Page hash 变化而自称修复。
- `exports.resolve_notes_policy` 从同一选定 Plan 的实际 effective policy 或显式选择派生 pptx_notes/separate_script/both/pure_reading。Page 是唯一正文/notes 真源；脚本 TXT/JSON 为有序完整投影。none 不新凑口播且保留原注；纯阅读只清理所选客户副本。
- sanitizer 验证原完整 count/order/ID/notes，再重建仅受信正文 notes；所有新 notes-aware/显式 policy 输出即使 notes 全空仍验证配对。纯阅读/独立脚本 PPTX 也保留安全稳定 ID，清除 presenter notes。notes/脚本/manifest/policy 的全部公共字符串统一检查可识别本地路径、credential/token link，拒绝时不改原 Page/原件；不是通用 PII 检测声明。
- `models.require_writer(..., rc3.v1)` 在首次新 notes/策略/文件消费的同一 CAS 单调提升；rank、Store 支持集、document schema 与唯一镜像同步。rc3 技术 floor 不制造 collaboration region、Narrative 或新协议资格；真实 control 不得因更高 floor 被删除。`Store.workbench_protocol_required` 根据已提交历史推导原协议，全部适用 workbench 写族、派发、Stage、UI 与费用分支共用。无法证明历史时 fail closed，无 --legacy 绕过。

RC3-03/04 必须直接消费以上 getter/slice/Plan/policy/floor，不能重新复制判定或清空原前审/权限/最终文件门。legacy 技术兼容不表示 RC3-04 的新建/迁移/专业交付总流程已验。

## 14 组正式验证与边界

| 组 | 实际工程路径 | 尚未完成的范围 |
|---|---|---|
| N-01 | 三页 native compile/正式 export/download 的稳定 ID、全 notes、中文/数字/限定/换行完整回读；全空新输出 count/order 负控 | 目标桌面 notes 视图 NOT_RUN |
| N-02 | cues/verbatim × 三容器，default verbatim 的真实 effective cues；脚本直接来自有序 Page | policy Plan 初态为明确 seed，非正式 import E2E |
| N-03 | none 保留用户原注、不自动脚本；pure_reading 仅清理副本；全空新消费也严格配对 | 实际阅读使用效果后置 |
| N-04 | 真实 Task.inputs 在 claim 前、freeze 前、freeze 后、begin 后 notes edit；同 request/hash、一份 attempt/allowance，费用保留 | fixture observation 不是实际生图质量/美元成本实验 |
| N-05 | SVG trial→notes edit→正式 candidate plan/adopt，原蓝图/new notes 保留，无新增调用 | 非全部候选种类的笛卡尔积 |
| N-06 | body/visual/design/font/style、箭头/责任/表格归属/Plan scope 与真实 revoked 负例；已发生调用结算但不采用旧正文 | 不声称全 mutation × 生命周期组合 |
| N-07 | 完成视觉→正式 notes edit→原 Review/视觉 Ref 当前→真实重编译→最终 export 新 notes；旧输出失效，Task facts 不新增 | legacy 正常继续 produce 与新 Stage 资格严格分开 |
| N-08 | bound speech 与 imported_mapping/null Narrative 正式 accept、当前 Plan links、合法完整 mapping；非 speech 前审重用、speech 失效 | 两变体已有视觉→正式speech→实际native/export全文件双轨已在当前真installed -I补齐；seed 不称正式04导入 |
| N-09 | notes-only 后开放视觉 must_fix 仍阻塞；仅援引新 Page hash 的 fake fixed Review 正式拒绝 | 未进行真人缺陷评阅 |
| N-10 | 正式 content operation reorder/remove/split/merge 后 native compile/export/readback 与 lineage；未知映射拒绝 | 初态为明示 v1 合成稿 |
| N-11 | 正式顺序 live/read 子请求、共享 Narrative、单 current、独立 revision/Plan/Page/export、第一份不被后续覆盖；无自动第三份 | 两版完整 native notes 总路线尚待04/05综合验证，不冒称本卡全组合已跑 |
| N-12 | notes 与公共 ID 的路径/Bearer/sk/token-link 正反；hidden metadata 清理、合法全文保留、原件不改；最终 hash 与原件 hash 分开 | 通用 PII、真实私有材料验收未宣称 |
| N-13 | 精确 edit/export replay、不同 policy 冲突、未知/重复 speech、旧/stale/duplicate Plan links 与 CAS 拒绝 | 不声称全文件系统故障矩阵 |
| N-14 | 真冻结 A CLI/SDK 拒写 compile/assemble/claim/accept/edit/restore/历史 delivery，实际 pointer/Page/PPTX/ledger/files 不变 | floor 不是授权或全部验收 PASS |

当前 N08 [真实安装双轨总索引](notes-engineering-20261014/ca035-speech-native/trace-catalog.json) 绑定 ca035、实际 `-I` module、固定测试源与执行前后246源码/包/安装字节。bound 最终下载 PPTX SHA `2b2bf06042a259072c24be99bc4bca8114eea808146ebfb17809c1842773fa03`；imported/null Narrative 最终 SHA `f0c63d91efe72f49aa2e14a2cf222aeab1df27372522039d64771f91dcfa12d1`。正常 continue 生成真实 SVG preview 并派发 PageVisual，真实旧任务仅正式 cancel，不删原件或省略主体；原 Review/视觉/task/费用完整保留。

两轨 notes speech 后当前前审分别缺 speech 与 page_copy/progression 时，首次 pipeline 编译仍执行；imported 初态新补合法 mapping 改变了非纯 notes 的语义消费，所以旧 page_copy/progression 不被 notes 等价放行。该首次真实 report/Document 从实际 immutable history 独立归档，不能写成“guard拒绝”。随后各自正式补齐当前适用的合成 L1 independent review 至 pass，再第二次 compile/export，最终 notes/Plan/零新增图像 ledger 观察归此后状态。原 main 与本卡的 PREPRODUCTION_GATED_ACTIONS 同为 dispatch.blueprint/style.trial/style.expand/change.commit，没有 compile.ppt/stage.assemble；此已有生产入口差异交 RC3-04 统一 guard 集成核对，本卡未扩大/清空前审枚举。此行为没有改既有 compile 枚举；未证实未补 units 的真实 delivery 误放行，不能定为本卡新增 P1，也不能写成 content/delivery 资格通过。RC3-04 仍须完整 selected-file/current-control 交付集成 audit。文件工程通过不表示原生产准入或全交付已通过。

三项新增正式回归还验证：legacy notes-only 前后 content_ops edit/reorder、annotations、styles、screenshot references、icons、新 compose/recoverable inputs/Stage/candidate/changes 资格不因 floor 偷迁移；原 workbench 项目正常正例保持。

## 原失败、修复和验证身份

| 版本 / 观察 | 实际结论与原件 |
|---|---|
| 首次广泛 unit | 7 FAIL /1805 PASS /456 deselected；修 caller/fixture 的真实合同，不降 Store control/geometry/final file 绑定。原 `rc3-02-unit-first.log` 保留 |
| 首次 unit 修复后 | 1814 PASS /456 deselected /160.01s；此后又有窄改，不能归到当前 head |
| `27823c5` / tree `dcda89be3e1eeef5ba040f076e5f0df307241772` | 两组独立 FINAL REQUEST_CHANGES：legacy 二次 produce；空 notes 新承诺错序/少页；公共 stable ID privacy 泄漏。原报告和反例保留，不改旧判 |
| 文件三 RQ 修复 | 88 PASS /8.68s，原 `rc3-02-files-empty-identity-privacy-fix-final.log`；只归实际匹配代码文件，不冒称当时已冻结新 head |
| `0b0ed2a` / tree `a306e063e8bd93365f1406cd9004c454c3dda3b4` | 第二轮独立实际 notes 前后 content_ops edit/reorder、annotation/reference 入口偷迁移，整体 REQUEST_CHANGES。此前三个 RQ 已独立闭合，保留此版安装与失败 |
| `0b0ed2a` render | 完整同一冻结代码 53 PASS /2249 deselected /22 warnings /63.27s；之前49 PASS4FAIL后4修复轨迹PASS是另组分段证据，不覆盖历史 |
| live unit 时间归属 | 1846 PASS /456 deselected /164.49s 的运行期间活动源码开始新修复；标 MIXED_LIVE_SOURCE、exactHead=false，不绑定0b0或ca0351d |
| 第三代码增量 | 原协议全门相关174 PASS /2 deselected /18.41s；加入edit正反后19 PASS /2.81s；Ruff/diff-check PASS。同一fixed snapshot完整 unit1851 PASS/456 deselected/212.91s、render53 PASS/2254 deselected/22 warnings/71.73s；独立round3 code/regression均 FINAL PASS |

测试误调用不存在 test 文件的 no tests ran、首次 canonical UUIDv4 输入失败及各真实失败原日志保留。合成 human adapter 的旧兼容正例只是 L1 谓词；strict notes 来自显式 policy、真实 page_notes 依赖或实际非空 expected text，绝无测试名/零 slide 特判。有新承诺的损坏/零 slide 文件不允许兼容通过。

## 安装和本地包

历史 `0b0ed2a` wheel SHA `6ac332e86904629ebf1171eddf0fb6c6ac2f7e1e9a57c316a44d7582c867af60`，真实独立 prefix 安装246份 source/package/install逐字一致，未激活、未改 actual HOME；[manifest](notes-engineering-20261014/isolated-install-manifest-0b0ed.json)。该历史版本仍有第二轮 RQ，不能当当前最终包或当前代码验收。[历史再验原件](notes-engineering-20261014/historical-0b0ed-revalidation/isolated-wheel-r4/revalidation.json) SHA `cd002fabee44cc0caa13f575b2a546bff57210f8805c11db1c5a685c6a3a997a`，[历史controller索引](notes-engineering-20261014/historical-0b0ed-revalidation/controller-index.json) SHA `a3f1b8a005e621b9b0d932dfd9826ebe160a91a27ce8d1f61b9bacf380277c85`；仅归历史0b0ed，不倒签原包或当前source。

旧本地合成包25files的最终公开 PPTX SHA `7446e7b505139505bd8853b2e74a19eaa77d9f386f30a4871fffdd3871c06c45`；外 ZIP SHA `b431e5ce983fc242901f23c0079fe8e32a42c143cc6404bf5e1b683c6a9c0ef2`。旧构建当时未冻结 Git 身份，原 manifest/hash/原件不覆盖。旧3张 actual-render 来自内部 native PPTX，不是最终 sanitized public PPTX；历史0b0独立安装重新实际 compile/readback/sanitize 并渲染最终 public 的新证据独立存放，不倒签旧构建。当前 `ca0351d` 真 isolated wheel `-I` 已另行完成 [再验](notes-engineering-20261014/ca035-installed-revalidation/revalidation.json)：246 source/package/install 文件逐字一致，实际 native 重编/full notes 回读、raw 仅 ZIP 时间差异且全部内部部件一致，sanitized public 重建仍逐字同上述 hash；[final public 回读](notes-engineering-20261014/ca035-installed-revalidation/final-public-full-readback.json) 与3张真正 final-public 实际渲染 PNG 独立保留。当前 wheel SHA `17a3bb5c40bdec788548fe17a3906e40524b41378f27d6ac77bc9c65bd543182`，[安装 manifest](notes-engineering-20261014/isolated-install-manifest-ca035.json) SHA `1085ec1051ca8d66e73d7fdacc51e3593425a05e2b7138a29d51afdd7b34925f`。这仍是工程再验证，原包构建身份没有倒签。

本地包提供逐页核对、notes-view、编辑保存重开、文件 hash 与回传格式，用户后续可本地执行或给材料远程执行。headless LO 成功不能替代用户目标桌面检查。真实 Owner/至少3名未写稿受众、独立阅读/培训实际效果、完整计时和professional approval均按原规范保留，未删 Runtime 原门。

[证据清单](notes-engineering-20261014/manifest.json) 精确指向选择的原字节/hash/原路径；不复制运行项目/缓存/安装树或可编辑内容真源。最终唯一 ledger 只回填本卡 N01–N04/CQ-06 的工程观察与待执行项，原 T06 Owner/signed_by 及整体 release gate 不变。

第三轮 [regression 原报告](notes-engineering-20261014/rc3-02-independent-regression-round3-ca035.md) 的77定向PASS、实际Chromium legacy/v3连接能力正反、真实冻结A两项目26拒写及已消费费用不变归独立reviewer执行；[code 原报告](notes-engineering-20261014/rc3-02-independent-code-review-round3-ca035.md) 只签固定 ca035 工程；[交付phase1](notes-engineering-20261014/delivery-review/phase1-report.md) 与 [phase2草稿预检](notes-engineering-20261014/delivery-review/phase2-preflight-report.md) 原件保留。phase2 的历史0b provenance缺项已补件独立核关闭，仍不冒称最终文档 audit 或专业验收 PASS；最终docs固定后由root独立终审，再跑准确最终head的全部必要CI；原0d12的src/skills/tests/pyproject与ca035零delta；bc0b39只有下述测试分界与helper真实状态断言delta，runtime src/skills/pyproject仍零delta。

## 追加：真实 CI 工具条件与测试分界修复

原 PR117 source `0d12a9d78ed0526f0fb74d1b8abed0a2ec154b4e`、实际 PR merge checkout `2b6764d91afecaa5765c4379f39772e2b735ef64`、run `38639118685` 的四组 unit 矩阵各 **3 FAIL /1845 PASS /3 SKIP /456 deselected**；原 [CI守门观察](notes-engineering-20261014/ci-marker-repair/0d12-ci/report.md) 与四份完整失败trace按当时观察原字节保留，观察时browser尚在运行。不是A不存在的skip造成这三项失败，也不能用本地1851数字覆盖CI。

`_completed_visual` 在正式SVG accept后通过正常continue调用真实rsvg-convert生成SVGpreview，才能获得PageVisual任务。unit CI没有安装这条渲染工具链。Owner在准确0d源、固定0d测试fixture下做 [缺工具/有工具实际对照](notes-engineering-20261014/ci-marker-repair/0d12-reproduction/reproduction.json)：使用受支持的配置指向真实不存在的renderer时，continue正确返回needs_tool、0pending、preview=null；恢复真实renderer后实际生成PNG并派发1个PageVisual。无mock renderer/待办。三原测试的缺工具复现同样3FAIL，错误是helper无条件索引空pending。

修复提交 `bc0b39fd9265d3408f69e95bc09047bf59a802d4` / tree `6f860d74e88543e965023b36ca0ee25ed4884f53` 仅改一份测试：四个真实渲染fixture调用者归render，包括CI三失败与同依赖的真实冻结A SDK测试。helper显式检查实际continue的status、单个PageVisual、非空真实preview；不fake任务，不降级review，不偷偷给unit工作流安装renderer，不增加skip。剩余unit在缺renderer配置下15PASS/4deselected；四项在真实renderer下4PASS/15deselected。[完整纯bc0b unit](notes-engineering-20261014/ci-marker-repair/rc3-02-owner-pure-bc0b3-unit.log) 1847PASS/460deselected/210.51s，[render](notes-engineering-20261014/ci-marker-repair/rc3-02-owner-pure-bc0b3-render.log) 57PASS/2250deselected/22warnings/73.20s。2307个case集合保持不变，4个真实预览调用者在render各恰一次、unit中为0；实际总unit+render仍1904，不删用例/不新增skip。原ca035的1851/53只归原观察，不误作新分组数字；新remote七项CI必须另据准确最终head执行，不能由本地4项全跑推断远端执行或skip原因，原-q的3skip具体原因未知。

[0d12文档最终审查](notes-engineering-20261014/delivery-review/phase3-final-0d12/report.md) 的FINAL PASS只归准确0d文档/证据/ledger；不能替代随后真实CI或新固定文档审查。既有140份历史原件/旧报告没有重写，新修复证据是追加导航。当前真实installed/native包再验证仍准确归ca035（runtime产品字节未变），不倒签为bc0b的新wheel构建。最终N01–N04/CQ06及人类/桌面/04/05总验收状态不改变。

第4轮 [code影响复审](notes-engineering-20261014/ci-marker-repair/rc3-02-independent-code-review-round4-bc0b3.md) FINAL PASS只签准确bc0b的renderer测试分界与实际断言；[regression影响复审](notes-engineering-20261014/ci-marker-repair/rc3-02-independent-regression-round4-bc0b3.md) 也FINAL PASS；新固定docs audit/准确新head七项CI待root执行。

## 追加：53f4 installed 示例真实失败与65d82文件闭环

[旧53f4 CI](notes-engineering-20261014/installed-fixture-repair/53f4-ci/report.md) run38642260224的全部七job已完成，5success、browser/groupFAIL。403browser实际PASS/1904deselected/1410.49s，wheel build/install成功；w12_offline在w11 fixture真实readback处因speaker_notes_mismatch失败（actual private canary、Page期望无notes），installed recovery尚未运行，不能借旧或本地结果回写为PASS。

Owner以准确53f4 snapshot新建真实isolated wheel/install，246 source/package/install逐字一致，-I预载site-packages core、仅固定example兄弟目录加入import；[实际旧失败复现](notes-engineering-20261014/installed-fixture-repair/original-53f4/w12-old-r3.log) 同一正文notes mismatch。最初直接-I导入example兄弟失败和canonical skill agents映射遗漏都是harness失败，原脚本/log分别保留，未记作额外产品缺陷。预提交live新例子三export正反是带实际example字节/hash的快查，不倒签为固定65执行。

65d8203/tree e4e94f7仅改两个examples：Page声明完整合法合成notes，经SvgInput真实编译并严检；同privacy canary仍在原件private author与notes隐藏shape描述，未删隐私验证。原正文注入canary另存独立真实PPTX，readback必须speaker_notes_mismatch，不能修改Page期望、关闭检查或允许私密Page正文导出。新file deps包含page_notes，rc3 floor与fixture artifacts同CAS。w11/w12共用实际下载检查：公开PPTX逐页完整notes/稳定ID一致且所有parts无canary；engineering实际保留原bytes及author/notes两位置canary。

[当前65安装来源](notes-engineering-20261014/installed-fixture-repair/fixed65/w12-installed-provenance.json) wheel b13629f0f67c17883bcc0a610b7fc2fd0951a1c714b4b3b3f90b616b664265a0、246source/package/install一致；[实际完整w12](notes-engineering-20261014/installed-fixture-repair/fixed65/w12-complete/checks.json) 9checks verified：真实browser三固定下载/完整notes/隐私净化/engineering原件、installed全部static/font/无外部请求与module无src借用。此新安装准确归65新source，不倒签53失败，也不把ca035旧native包重命名成65的新构建。

[第五code](notes-engineering-20261014/installed-fixture-repair/rc3-02-independent-code-review-round5-65d82.md) 与 [第五regression](notes-engineering-20261014/installed-fixture-repair/rc3-02-independent-regression-round5-65d82.md) 限定影响复审均FINAL PASS，独立执行与Owner完整w12/recovery分列。src/skills/pyproject对ca035、tests对bc0b零delta，原软件/分组审查只按这个明确相同范围复用，未把remote全部CI签绿。

本地完整installed recovery首轮因Owner任务TMPDIR过长，所有首批Chromium日志明确FATAL Socket path too long（Unix IPC路径长度），中断时63FAIL/68ERROR/1warning，85.22s。该原log/长路径/harness/module来源保留，不是product/example失败，也不是/usr/bin/chromium无效；早先根据浏览器差异推断的归因已更正。只改短TMPDIR=/workspace/work/rc3/t65r，同一system Chromium真实launch PASS后用新名字执行完整recovery，源码固定且无修改。新轮完整结果为238PASS/1FAIL/797.48s，唯一窄屏case的实际box y639.805664、高208.999939，底848.805603超过844；该原完整suite保留FAIL，不能由w12或独立限定PASS替代。

运行中fixed snapshot出现已知browser生成out，tracked源码/tests/head保持固定；不声称整个worktree无任何生成文件，不删除未知out，不提交运行目录/缓存/安装树。原165份历史证据/报告不改，新的实际失败、复现与修复是追加来源。专业N/CQ、真实Owner/听众/桌面及04/05集成仍按原状态保留。


## 追加：真实 installed recovery 的初始图像与 fit 生命周期

[65完整recovery原log](notes-engineering-20261014/installed-fixture-repair/fixed65/installed-recovery-r2.log)及module/provenance均是准确65 installed core、system Chromium151.0.7922.173与短TMPDIR；238项实际PASS和1项FAIL分别保留，未把完整suite改成PASS。同一原测试独立单case真实PASS1/1只是单次观察，透明记录的box原返回不作修改，不能覆盖原FAIL。

[受控实际图像成对观察](notes-engineering-20261014/installed-fixture-repair/fixed65/mobile-lifecycle-control-r5/observations.json)把真实SVG请求暂存后原样继续：fonts始终loaded；图片decoded且canvas刚进入DOM、reading mode仍null时，高209、底848.428528；11ms后原controller在下一RAF设置既有data-reading-mode=fit，高184.59375、底823.991455。没有替换图片、修改geometry、改变用户视口或产品等待。原测量只等待外层可见，能落在这两个状态之间；image ready仅表示解码完成，适应窗口有其明确真实fit状态。

修复提交acf2b2edd4a88f74e8b671a18e32eb74b780eb84/tree0d3ce4982e24a081cbf964259ea85891cd713aed只有测试3行：窄屏量原box前等待既有data-reading-mode=fit；原bottom<844、内容层切换、URL与水平布局断言保持。没有固定sleep、轮询同一个geometry断言、阈值放宽或runtime修改。src/skills/pyproject完全ca035同字节，两个examples完全65同字节，余238项实际观察按相同范围复用，未另跑本地完整suite；最终必要CI会真实重新执行installed recovery。

诊断harness的null-after-content-layer观察hook INTERNALERROR、scratch递归collection FileExistsError以及最初缺失观察字段的各原log/script也分别保留；它们没有额外产品finding，也不能当case结论。当前新固定acf测试源与实际65安装core的来源分别记录，65wheel/build绝不倒签为acf构建；第六限定独立报告已FINAL PASS；新最终docs与准确新head七CI仍待。


[准确acf限定来源](notes-engineering-20261014/installed-fixture-repair/acf-test-fit/acf-scoped-provenance.json)记录新固定测试SHA/tree与三份helper hash；实际core仍为65构建wheel b13629…，246份acf源码/65wheel/当前安装逐字一致。原3viewport case真实3PASS/5.07s，受控image loading→decoded-before-fit→实际fit真实1PASS/2.03s。不是新的acf wheel构建，也未重新执行239全套；第六独立限定复审已FINAL PASS，当前必要CI待准确最终head。


[第六code原报告](notes-engineering-20261014/installed-fixture-repair/rc3-02-independent-code-review-round6-acf2b.md)与[第六regression原报告](notes-engineering-20261014/installed-fixture-repair/rc3-02-independent-regression-round6-acf2b.md)均FINAL PASS，仅签固定acf这3行等待的限定影响。code reviewer自执行精准390case与actual installed held-image/完整实际628bytes hash对照；regression reviewer自执行原3viewport、held时fit超时负控与actual continued response/fit对照。各自原harness错误也原样留证，不复用Owner执行冒充本人结果，不宣称本地239全套或remoteCI通过。

当前清单239份copied evidence逐字/hash与raw一致；原53f4的165份既有原件/元数据不变。唯一ledger仅N01–N04/CQ06 findings随新增工程历史更新，原Owner/card/各状态/签名/全局release保持。产品src/skills/pyproject/examples/tests与固定acf零delta，最终docs固定后由root做准确限定终审并运行全部7CI；本卡尚未合并。
