# WU00 当前只读核对

观察日期：2026-10-20（UTC）。云端 /workspace/Deck-Master；不访问用户本机。

## 已确认事实

- 初始分支 work，工作树干净，HEAD=09f0213d07fc718dc4d41a52bb69c4595fcb1ac8。
- git ls-remote 与 fetch 成功：远端 main/HEAD 同为上述 SHA；codex/rc5-content-methods-20261020=02627c17d5046428609e6806569ad3cd790e7d26。此值仅观察，不是最终实现基线。
- base 到观察 head：122 文件，5078 insertions，276 deletions。主要新增 resource_catalog.py、canonical resource-catalog.json、方法/案例与 selected_resource_ids 生产入口；web.py 与 resources/static 无 diff。因此不能把 PR127 视为已实现本轮 WebUI。
- 结束前再次 ls-remote 发现该分支推进到 d1ee1c7d1f16db120fd4c91c2cc9e71ce31b915e；fetch 后只读核对 02627c17→d1ee1c7d 的 8 文件增量（159 insertions，15 deletions）。其中 blueprint 在持久请求之前校验最终选择；compose design/production/delivery 不再默认 method-selection；Review 方法读取固定 review phase/units；正式重派只移除早期错误默认，旧 manifest 不改。另有案例算术与测试改动。六项裁决仍适用，R2 必须使用最终 selector 语义。main→最新观察 head 总计 122 文件、5223 insertions、277 deletions。该新 SHA 仍不是获确认的最终基线。
- 现有 UI 已有 collaboration-desk 的请求、范围、内容完成、审阅方式及用途相关设施；现有 launcher 支持 plan_only/write_only/speech_only。增量应扩展它们；没有据此重建管理台。
- 已读取 AGENTS、agent-task-index、agent-recovery-playbook、当前 RC4 handoff、DESIGN、product-ui-language；/workspace/.agents 与 .codex 目录为空，仓库无嵌套 AGENTS。当前任务限制优先于旧 handoff 的实现指令。

## 六项源码依据

行号以下按 main 09f0213d，另注明观察 head 的变更：

| 项 | 真实源码 | 裁决 |
|---|---|---|
| R1 | collaboration.py:553 record_decision；content_production.py:1646 adopt_proposal；eligibility.py:172/237 | 两事务不同准入；采用要求 effective accepted direct_user/delegated 决定、精确 scope/subject/projection、当前 CAS。不能共用一个 allowed。观察 head 未改变 adopt_proposal。 |
| R2 | 观察 head service.py:988–1007；resource_catalog.py select；collaboration_api.py continue | 新 selection 写入口拒绝补 frozen Task；complete 可能早返回；选择器 role/phase/scope 不可由 UI 随意放宽。新只读方法浏览/准备状态尚需实现，不得调用 continue 来预览。 |
| R3 | web.py:684；content_plan.py:362–409；content_production.py:485 | fixed revision Plan 读取已存在；planned mode 无 Page link，投影 page_ref 可 null。该端点只读 snapshot 当前 content_plan，不能自行解决候选 Plan 关联。 |
| R4 | content_production.py:1710–1775；snapshots.py | 比较应是合法可达对象的只读投影，不继承采用的“必须有决定”。写入必须重新按 current 校验；比较并不创造权限。 |
| R5 | contracts/review.v1.schema.json findings.required；content_review.py:835–861 | 当前 v1 要求 finding_id，摘要与真实 schema 有差异。读取方仍有 finding_id 或 id 兼容；fallback 是新投影设计，不能据此声称当前对象都没 ID。 |
| R6 | content_plan.py:355；view.py:79 | 已有不可读局部投影；新 schema 必须明确 false/null/error，不伪造必填业务字段。 |

## 阻塞与未验证

1. 附件官方 prepare_materialize 成功；官方 transfer helper materialize 到 /workspace/webui-spec-input/spec.zip 返回 exit 1，download failed。目录检查无文件。失败原因未细分，不能断言权限拒绝；传输失败已确认，本地无交付。无 raw URL 替代、无换环境、无重复下载。原包最小 diff、15 文件结构、验证脚本及 50 AC owner 均 pending。
2. gh pr view 127（只读 GraphQL 元数据）返回 Forbidden。该动作 denied；没有重试或改渠道绕过。PR open/merge/check/review 状态不可据此确认。远端分支 SHA 可读不等于 PR 可合并。
3. 最终 PR127 基线待父线程确认，产品实现 pending。没有自动合并 PR127。
4. 未执行产品 tests、browser、Host、安装、构建或方法脚本；没有实际业务项目读写。工程仅静态核对；Host 应用、独立审阅、人类认可均 NOT_RUN。

## 续接

先取得原规格文本并逐条合入 API/UI/AC/traceability；原 WU owner 与 AC 不变。待父线程确认 PR127 最终可用 SHA，再 fetch 并核查与观察 head 的差异，迁移此规格提交到独立新 PR 分支，复核这些源码锚点和协议。完整 WU01–WU08 同一 Draft PR；在该门槛前不启动实现。
