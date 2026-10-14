# Supplemental content verification adapter：工程自审

实现：`postrepair-verify.py`。作者：`/root/restart_recovery_audit`。2026-10-14。待 Root / 独立工程 reviewer 核验之后使用；本记录不表示新的内容评阅或 S01 安装已运行。

## 本工具的边界

不改 frozen driver.py/protocol.json、原首次稿、原评阅、旧 refusal、旧 stage accepted 或实际用户 HOME。不调用模型，不生成/补写 Review 内容，不替 reviewer 关闭 findings，不产生假 Native event。Root 必须自己保存真实 spawn canonical 返回、Native FINAL envelope 原文与结果 SHA。

工具独立校验明确给定的新 installation manifest、source SHA、wheel SHA、实际当前安装身份与 isolated Python；不调用 frozen `load_run/identity`。旧 run-manifest 的 source/方法身份保持原值。新 admission、Task、Review proof 与 snapshot 单列在 `run/verification/`，一律标 `supplemental_protocol_repair_not_original_frozen_E1`。

提供五个命令：

- `accept-existing-speech`：在旧安装的真实拒绝已保存后，使用新明确安装公开 service.accept_result 消费**同一 Task/原作者/原 raw output**。只许 04-speech 或 repair-speech，不 re-claim、不改元数据。验证原 refusal 的输出 hash/作者、原 claim 与真实 FINAL、当前方法 basis 和正文保护。结果写 `verification/post-failure-consumption/<original-stage>/`，不覆原路径。
- `prepare`：支持 postrepair、final-content-verification、post-failure-verification。检查实际原始独立 review 已正式接纳并有持久化 authenticated receipt，必要的真实 repair phases 都完成；尚有 running/awaiting compose 时不准备。通过 runtime trustedbootstrap + 公共 dispatch_preproduction_review 产生 fresh Task 与真实不可变 packet。
- `claim-read`：只能由新的真实 canonical verifier 执行；拒绝每一名实质作者及旧 reviewer。公开 task_start/read_task_methods 保存新的原 claim 与全文 bytes，不能覆盖旧领取记录。
- `accept`：消费 Root 原生真实完成观察及实际 raw Review；在注册/绑定的 ProviderRuntime 中构造 opaque context、调用 service.accept_result，保存正式 receipt 原始 event。只许 Review，所有生产/作者内容及外部调用保持不动。失败照实另存，不补内容 fallback。
- `freeze-owner`：仅 actual verification 各 unit pass、无 unresolved blockers、**当前 SDK preproduction_status=pass** 才冻结。保留未执行的 advisory/F3及原稿/原初判定位；没有实际 repair 时不制造 repair。Owner/试讲/受众/桌面仍 NOT_RUN。

## 来源、独立性和 scope

作者 provenance 不只用 Runtime 对当前 Ref 的直接相交：逐一对应所有 completed compose Tasks 与真实 accepted record、dispatch、原 claim/method-read、raw 输出 SHA及 Root Native FINAL。包括最初 Page copy 被 speech 派生 Ref 替换后的原作者和实际 repair 作者；缺任一真实来源便拒绝。新完成的补充 speech 接纳也要同样对应。旧 reviewer refs/full objects 从当前 Store 原样保存。

fresh verifier 输入包包括当前完整 Narrative/Plan/Page/notes/mapping、材料 extract、真实旧 Review refs/full records，以及 Root 显式给定且以 hash 固定的 scope evidence。scope role 只允许原规范、实际 Root 观察、独立 scope audit 和实际用户验收延期；不能把它们当新的写稿资料或目标 PASS。

replacement 的旧 Ref、logical review_id/kind/stage/shared finding IDs 只提供 metadata 指向，具体保留/关闭、resolution_reason、观察、evidence/replaces 均由实际 verifier 作出。AC-M03 estimate 与 AC-U03 真实完整试讲分层；cue/练习、原 sample scope/0 images 或用户延期不变成人类验收。

Provider 仅继承 frozen 真观察 transport helper，使用独立 provider ID，在当前 trustedbootstrap 注册 sealed runtime。普通项目 JSON 不注册 provider 或选择 assurance。唯一 channel 是 independent_review_receipts；verified_user/human channel 保持 false。结果/Task/packet/subjects/作者/write_scope 原绑定由实际 SDK 派生，没有替换 Runtime 真值。

完成观察一律需要 Root 真正观察的 list_agents completed，加实际 spawn canonical 返回与 Native FINAL 原文/hash绑定。新 verifier、原 speech 补充消费和历史作者 provenance 均无 unknown/restart 接纳例外。Root 已确认待消费原稿和 repair 记录的完成观察实际具备，历史旧 roster 曾不可见的限制只能单列，不能转成资格。对同一历史 speech 结果，不把原 observation 的时间后改成新完成；其历史时间必须合法非未来，另以真实当前 SDK admission 与 Task/current basis 核对消费。新 verifier completion 有 45 分钟 freshness 限制。

## 新安装和方法 identity

`--installation-manifest`、`--expected-source`、`--expected-wheel` 是实际新安装；所有命令必须用明确的 `--expected-python` 路径，工具核对实际 sys.executable、安装 module 与 prefix。`--transition-record` 加 raw SHA 固定旧→新差异。transition record 结构如下，Root 使用真实值形成独立文件：

```json
{
  "classification": "supplemental_protocol_repair_not_original_frozen_E1",
  "old_installation": {"source_sha": "ACTUAL_ORIGINAL_FULL_SHA", "wheel_sha256": "ACTUAL_ORIGINAL_WHEEL_SHA"},
  "new_installation": {"source_sha": "ACTUAL_NEW_FULL_SHA", "wheel_sha256": "ACTUAL_NEW_WHEEL_SHA"},
  "permitted_method_change": false,
  "difference_record": {"path": "ACTUAL_SOURCE_DIFFERENCE_RECORD", "sha256": "ACTUAL_RECORD_SHA"}
}
```

示例仅说明 shape，不是来源证据或可复制的真实 event。工具实际读取原/new packaged skill 根下每个文件，比较 bytes/hash；布尔声明不替代实测。正式同一旧 Task 消费再次要求真实 read_task_methods.status=current，归一化的每个 id/relative_path/hash/content 相同。新 release_id/路径可以不同，旧 Task 的 dispatch_method_release/execution_ref/start_time 不改；结果记录分别保留 dispatch/current release 与真实 current basis。若仍 basis_changed，拒绝，不修 Task。

Root 另需完成新安装的 source/package/installed byte audit；本工具不代替该打包验收。A/B应分别保留各自原方法，避免 A 共用 B 方法造成 basis 改变。现尚未提供新 S01 installation，所以新安装 consume/review acceptance **NOT_RUN**。

scope evidence manifest 是一个列表，每项 `{path,sha256,role}`。其 raw SHA 通过 `--scope-evidence-sha256` 提供，工具逐项核对真实 source bytes 并独占复制到 fresh packet。Root 提供实际引用，不编造审批。

## 自动负控

实际 `accept` 执行时会核验：

1. 每一位真实完整稿作者都被 controller 的独立性 guard 拒绝，包括 Runtime 当前 Ref 直接相交遗漏的旧 Page copy 作者。
2. 普通 JSON adapter_context 被当前真实 SDK 拒绝且 current revision 不变。
3. 改动 actual Review notes 的跨结果重放被 registered provider 拒绝。
4. 把 actual receipt 放到另一个 Task identity 被拒。
5. 正式接纳后正文、页成员、Plan、设计、文件和输出未改变；Task.result_refs 保存且只有一个 authenticated receipt，其 raw_event_ref 逐字节等于实际 Root observer。

这些负控使用真正收到的结果进行拒绝检查，不构造假 Native positive。此时还未有新的实际 verifier 输出，故 acceptance/运行时负控正例未执行，不能先填 PASS。

## 已执行的工程检查

- Ruff 和纯语法编译通过；没有修改产品或 frozen 文件。
- 临时沙盒 `/workspace/work/rc3/postverify-engineering-_oi0xxu1/` 复制实际已完成的 Q2 A。只重定位沙盒 project path，用原 A 安装作机械 API 检查；**不是新 S01、不是真实 E1 run、不消费真实工程**。
- 公开 SDK 在该沙盒成功创建 fresh full packet / Task `74ac1cf888a8`；父稿和生产对象保留。
- 四个真实原作者 canonical 分别试图 claim verification，被独立性 guard 拒绝；每次沙盒 current.json 字节未变。
- 本工具作者的真正 Native canonical `/root/restart_recovery_audit` 成功在沙盒领取工程检查 Task/read_task_methods。仅证明真实工程领取与 SDK 返回方法全文，未产生 Review 输出、完成 observer、receipt 或质量结论。
- 把**真实旧 initial review 的原始 bytes/observer**当 fresh Task 完成证据，纯 identity checker 拒绝。没有生成 fake Native event。第一次检查器脚本读错 Task 的 project_id 字段，失败日志保留；改为从实际 sandbox Store 读 project_id/Task 后拒绝检查通过，没有补造 claim。
- 沙盒 summary、prepare/claim stdout/stderr、旧真实评阅重放负控日志均保留；最初 positive preparation 发生于自审中段，后续 helper 细化没有改变真实 run。Root 应在最终 code review 完成后为真实 verifier 全新 prepare，不能复用工程 sandbox。
- 最终严格来源版本另在 `/workspace/work/rc3/postverify-final-engineering-9u6aqjkq/` 的完整复制目录尝试 prepare，因历史 observer 指向实际原 stage method-read 路径，而复制目录路径不同，来源检查如实拒绝；没有进入 dispatch 或写真实工程。本次没有改旧 Native observer 以适配副本。真实 run 未搬目录时应使用原实际路径，Root 后续新安装集成检查照实执行。

## 自审中发现与保留的限制

旧 SDK 的 strict kind、preproduction closure 及 PPTX 依赖问题有单独定位报告：`reviews/rc3-01-s01-speech-and-review-boundaries.md`。adapter 不修这些产品语义，不令新 pass 自行抹掉原 open finding。即使 fresh Review 已真实 accepted，当前 gate 仍 blocked 时 owner freeze 仍拒绝。owner freeze 还逐一核对全部 prior open must_fix/needs_judgment 的中央 finding_closed 链，包含已经 stale 的原 owner；任何旧 blocker 没有 genuine explicit current replacement closure，就不冻结为通过。只读使用 SDK artifact-digest getter 为中央解释提供上下文，不改 review/closure 或另建状态。

独立工程 reviewer 的第一轮提出 completion 证据、stale prior blocker closure、expected Python path 与 repair 原始 evidence snapshot 范围四项，均已修正；originals() 现在覆盖全部已存在 stages（包括 repair 的原 raw/refusal/observer）。作者来源同时检查完整 spawn tool/fork/returned canonical、method/project/path 和真实 completed 观察。

独立工程第三轮最终 review **PASS**：exact script SHA `33db044489a642da749ef06c5de19b5d33c76b19cd19c181c03e37b6809efbfc`；五项 finding 均关闭，9 个纯 helper 工程检查及 syntax/Ruff 通过。报告 `reviews/rc3-postrepair-adapter-review-round3.md` SHA `b36430b824146ee10e02725f54f535f05a9abfddfc3ad8af4e328e64b54572c2`。此 PASS 仅工程准备，不表示新安装 consume、实际 Review 正例、内容效果或人类验收通过。

新 SDK、实际 raw verifier acceptance 与所有 formal postrepair/owner snapshots 均须 Root 后续实际运行。模型精确配置、tokens/费用未可观测时保持 unknown；Native执行不是人类或专业验收。本工具属于受信 Root controller 集成，host_attested 的共同文件/工具边界如原规范，不声称能抵御恶意同权限 Host。
