# RC3-02 独立 code review：第三轮 ca0351d

**结论：PASS（当前固定实现的独立工程 code review）。** F-CR02-03 的实际失败轨迹及受影响正反对照已复测关闭；本轮未确认新的实质缺陷。此结论不替代桌面、人类、真实模型内容质量、正式导入 E2E 或完整 RC3/最终专业 AC 的验收。

Reviewer：`/root/rc3_02_code_review`，未参与实现。日期：2026-10-14 UTC。

## 固定身份与原件

- HEAD：`ca0351d2397ba154e9f77363bd0f325629eb0ebd`；tree：`05191deede70f26e661b28f4221c3c0d00ef2ecf`。
- 快照：`/workspace/work/rc3/reviews/rc3-02-code-snapshot-ca035`；实际执行器：`/workspace/work/rc3/reviews/env-02-snapshot-ca035/bin/python -I`。source `work/rc3/env.sh` 后始终使用绝对执行器，独立探针核对实际 module 来源。
- 完整审查 `0b0ed2a` → `ca0351d` 的全部 9 个产品模块和 1 个测试文件 delta：content_ops、annotation_service、visual_styles、styles、icons、content_production、tasks、ui_journal、web，以及新 notes origin 回归。继续检索全部剩余 format/protocol 判断及其调用者，没有拿 Owner live docs/source 漂移当固定版本修复。
- 独占 scratch：`/workspace/work/rc3/reviews/rc3-02-code-round3-ca035-scratch`。没有装依赖、共享 bootstrap、源码/raw/生产账本改写、commit 或 merge。仅在隔离合成 fixture 中走正式项目操作。`git diff --check` 通过，快照 source clean。
- 初版报告 SHA256 保持 `37e9d155ddff439f6af5b2ee0142b476ddfd303c6e8c2928559d35d2bd2f67ee`；第二轮保持 `c637c05ef3257060f4ef487b5c21b44015296ed9c1416769e1b715cc20e19c45`。两轮 REQUEST_CHANGES 与失败原件没有覆写。

## F-CR02-03 复审关闭

独立脚本 `probe_origin_services_http.py` 重新执行了第二轮的真实服务失败轨迹，增加正文 edit，并用明确创建的 v3 项目作正例。没有 monkeypatch format/Store 或伪造历史祖先：

| 初始协议 | notes 写入前与写入后 | 实际结果 |
|---|---|---|
| 原始 legacy | content_ops reorder、content_ops edit、annotations.save、截图参考 import，各两次，共 8 次 | 全部拒绝，分别为 content_invalid、annotation_invalid、visual_reference_invalid；每次 current 完全不变 |
| 原始显式 workbench.v3 | 同 4 条服务路径各两次，共 8 次 | 全部正式 commit，实际顺序/正文/意见/参考记录正确落盘 |
| 两种来源完成真实 notes-only edit | 最低 writer/current format | 均单调保持 rc3.v1；region 仍 null，来源分别保持 legacy / explicit_v3，技术 floor 不改变来源事实 |

共享 predicate 现已用于全部发现的格式门。剩余直接 format 判断属于 create 的显式输入、schema/writer 技术事实、predicate 对旧祖先的读取或已先执行来源判定的 protocol helper；没有发现遗留公开入口仅由 notes floor 解锁。styles/icon 的负例经过本轮正式 service 测试；合法 v3 的实际提案/确认正例也通过。compose.v2 仍要求真实 collaboration binding，不因来源 helper 为 true 获得新的 region、Narrative 或权限。

UI `project_info` 对 legacy 与 v3 的所有 FORMAT_GATED 家族分别显示不可写/可写，与服务的格式边界一致。这是项目能力投影，不是长期执行授权；仍由正式服务检查具体请求、scope、暂停/撤回等控制。

HTTP 也独立执行：legacy notes 后的 `/api/candidates/plan` 返回 409/unsupported_project_format；`/api/content/plan` 与二进制 `/api/styles/references/import` 返回对应受控拒绝，current 未变。显式 v3 同一 candidate 查询进入实际候选解析，返回 404/candidate_not_found，证明没有被错误旧格式门挡住。全部请求只访问隔离测试服务的 loopback，没有外部通信，也没有输出会话 token。

证据：`probe_origin_services_http.py/.log`；脚本中包含逐次 current、实际提交内容、来源和 UI 投影断言。

## 真实 control region、未知历史与晚到结果

独立脚本 `probe_region_and_late_result.py` 使用明示合成的实际 control region 与正式 start_request/grant。真实授权 notes-only edit 后，floor 为 rc3.v1、来源判定仍要求 workbench。范围内 opinion/reference 两条服务可正式提交；随后正式 pause_request，两入口均以 request_paused 拒绝，current 完全未变。

另一条 legacy 轨迹由真实服务派发 blueprint Task，正式 claim→call_begin→cancel→notes-only edit→accept。晚到 usage 证据明确为 synthetic host_reported unknown，并非 native provider 或实际模型回执。首次 accept 拒绝产物、保存 unknown 调用事实；精确重放只返回历史 already_applied，current、当前新备注、call allowance、result_refs 均不变，不新增调用，也不恢复取消任务。原来显式 v3 的首次和重复晚到均拒绝的语义由独立 targeted tests 验证。

未知 rc3 根祖先保持强 workbench 规则；无法读取指定 origin revision 时明确报错，没有静默取得 legacy 豁免。predicate 的 seen 集合防循环和 Store/load_document 错误路径静态核对通过；未写假历史、未降低 floor。恢复到旧内容后当前暂停/控制与 consumed 调用事实不回退的正式对照通过。

证据：`probe_region_and_late_result-final.log`。最初探针给 unknown observation 绑定了新 invocation_ref 却没有 execution evidence，Runtime 正确拒绝（原 `.log` 保留）；更正的是隔离探针的明确 synthetic host_reported 证据文件，产品始终是 ca035。不把该 harness 缺证据记作产品缺陷或抹去。

## 本轮独立测试与复用范围

以下为两个不同命令，不拼成一次完整套件：

| 本 reviewer 执行 | 实际结果 | 范围 |
|---|---|---|
| 新 notes origin/formal services 定向 | **10 PASS / 9 deselected，0.89s** | floor 来源、正文 edit/reorder 与 UI、全部已发现残余入口拒绝、未知祖先强规则 |
| 正常入口、HTTP、费用/控制对照 | **12 PASS，1.58s** | 正常 annotation/style/icon 提案确认、截图 binary HTTP 与 receipt replay、legacy 与 v3 晚到、合成 native 调用 cancelled 后消费保留、direction 必须、scope 必须、pause 必须、restore 当前控制与 consumed 事实保留 |
| 独立 origin services + HTTP 脚本 | **PASS** | 上述 16 条正式服务对照及实际 HTTP/UI |
| 独立 region + late facts 脚本 | **PASS** | 已授权正例、暂停负例、notes-floor legacy 晚到、unknown/unavailable history |
| diff whitespace / clean source | **PASS** | 固定 delta；未修改产品 |

pytest 日志：`rc3-02-code-round3-ca035-origins.log`、`rc3-02-code-round3-ca035-controls.log`。

Round 2 中本人已实际完成的文件证据仍可按精确 source 复用：`git diff --quiet 0b0ed2a HEAD --` 对 compiler 目录/native.mjs、pipeline、export_sanitize、exports、handoff 返回 0。这些路径及 first-two-P1 的实现没有变化，因此复用本人 Round 2 的实际 native 连续编译、四容器隐私拒绝/无半包、全空 notes count/order 正反和 15 个 missing/duplicate/wrong-ID 最终文件负例；没有声称本轮重新跑了这些实际文件组合。此轮新 tasks journal 分支已独立覆盖，未用文件层复用掩盖它。

## N08 补充轨迹的证据范围

另只读检查了 Owner 提供的 `rc3-02-speech-native-ca035/trace-catalog.json`、bound/imported_mapping_null_narrative 的 summary 与 supplemental-audit。它们记录固定 ca035/wheel、246 个产品文件 before/after 一致，并明确合成 L1 身份；不是我的独立 E2E 执行。

原件如实显示：正式 speech 后，bound 前审缺 speech；imported/null Narrative 初态缺 mapping，新增诚实 mapping 后前审缺 page_copy/progression。两轨**首次 compile 都成功，未 blocked**。随后正式补齐合成 L1 units，再重编译/export，Owner 报告实际文件完整 notes、原视觉 refs/PageVisual Review 复用与零新增 image tasks/allowances/attempts。首次未齐内容资格和后来文件工程结果必须分列，不能把后一次结果追认成首次内容资格已满足。

CONTRACTS 区分工程文件、当前内容资格和正式 delivery。compile/stage 不在 PREPRODUCTION_GATED_ACTIONS 是基线与候选共同已有行为，文件可用于进一步 review；因此本轮没有仅因“首次 compile 成功”静态猜测为新 P1，也没有将它升级为正式交付资格。selected artifact/current-control 下的最终 delivery 应另以实际完整检查与准入结果证明；未补 units 时是否存在真正 delivery 旁路，本轮没有正式执行反例，作为 RC3-04 最终入口集成的待覆盖项保留。不能借不可变旧输出、旧较松策略或工程 PASS 代替该验证。

imported 轨迹依然是 schema-valid seeded initial state，正式 import E2E 为 NOT_RUN。桌面 notes 视图、保存重开、真实 Owner/听众、人类 professional evidence 与实际模型内容质量全部保持各自 NOT_RUN；不会降低 Runtime human policy，也不关闭最终 AC-N01–N04/CQ-06。

## 工程出口

三个已确认 code finding 在指定固定修复与独立反例/对照后关闭，当前 ca035 工程 code review 可以进入既定 merge 流程。是否合并及后续提交身份由 root 决定；任何代码新 delta 仍需按影响复审。此处没有实际 merge、客户安装或发布动作。
