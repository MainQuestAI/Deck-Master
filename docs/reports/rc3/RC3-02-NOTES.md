# RC3-02 notes 与实际文件工程交接

RC3-02 已实现当前 Page notes → native PPTX → 选定容器导出 → 最终客户文件完整回读的路线，并修复 notes-only 的视觉复用、Plan links、最低 writer 与旧协议隔离。当前代码 `ca0351d2397ba154e9f77363bd0f325629eb0ebd` / tree `05191deede70f26e661b28f4221c3c0d00ef2ecf` 第三轮独立 code/regression 均 FINAL PASS，已具备工程交接条件；最终固定 docs audit 与当前 head 七项 CI 待root执行，未推送、未合并。目标桌面备注视图/编辑保存重开、真实 Owner/受众和专业使用验收仍 NOT_RUN，最终 N01–N04/CQ-06 保持 BLOCKED。

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

第三轮 [regression 原报告](notes-engineering-20261014/rc3-02-independent-regression-round3-ca035.md) 的77定向PASS、实际Chromium legacy/v3连接能力正反、真实冻结A两项目26拒写及已消费费用不变归独立reviewer执行；[code 原报告](notes-engineering-20261014/rc3-02-independent-code-review-round3-ca035.md) 只签固定 ca035 工程；[交付phase1](notes-engineering-20261014/delivery-review/phase1-report.md) 与 [phase2草稿预检](notes-engineering-20261014/delivery-review/phase2-preflight-report.md) 原件保留。phase2 的历史0b provenance缺项已补件独立核关闭，仍不冒称最终文档 audit 或专业验收 PASS；最终docs固定后由root独立终审，再跑准确最终head的全部必要CI；产品src/skills/tests/pyproject与已审ca035零delta。
