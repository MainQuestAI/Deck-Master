# 生成工作台 v3：独立工程 Review

核验日期：2026-09-26。范围：W01–W12 / 87 AC，对照 main `d1c7c4600cb0fc781070116ed8cc8a1ff6b8b7ca`。本线程执行目录与 A/B/设计工作树隔离；远端 main 本轮已通过 ls-remote 重新核对。设计提交 `dfeecd9` 作为输入，OpenDesign 当前 8 个活动文件已只读保存到 design-snapshot/，没有回写用户设计。

结论：保留完整产品范围，按下述修订可开始 W01 核心切片。发现 4 个 P1、3 个 P2；本轮另完成 4 项临时项目观察，其他项以源码和包间契约逐项核对。它们是实施前的边界/依赖修订，不表示全部新功能已实现。历史 214 项测试和 17 项观察只作基线，不重算为本轮验收。

## 问题（按严重性）

### F01 [P1，置信度 10/10] 指定版本必须校验项目归属、路径和提交可达性

涉及 W01-AC02/06，W05-AC03、W11-AC01/02 复用。
现状 `web.py:166–183` 的 view/page 读取未传 revision；`store.py:194–206` 直接组成 `self.revisions_dir / f"{revision_id}.json"`，只比较快照内部 revision_id。
本轮 R01/R02：将 B 的 revision 复制或符号链接到 A 的 revisions 后，project_view(A, revision=B) 返回 project-b；R03：仅 save_revision、未切 current 的孤立快照也可读取。
修订：统一 snapshot 读取，严格 revision ID、拒绝 symlink、校验 project_id 与从 current 可达的已提交 parent 链；所有 view/page/lineage/tasks/reviews 的 revision 参数同义，不存在版本返回 typed 404，不退回当前，不泄露路径。只读不增加 token。候选是不可变业务对象，不是可绕过历史规则的任意 Document revision；见 F07。
证据：[新增探测](independent-probes.json)、原探测 P02；需补 CLI/HTTP 负例和历史读不写测试。

### F02 [P1，置信度 10/10] 现有“回执”检查不能用作提交事实的独立证明

涉及 W02-AC03/04/06/07，W05-AC01/02。
`tasks.py:1351–1361` 的 _provider_receipt 只判断 JSON 的 provider、signature 是否非空，未验证签名/签发者或请求内容。它是既有调用账的条件判断，不能升级为新 UI 的 provider_receipt 可信等级。
修订：W02 先验证一个实际可用的证据采集路径；必须把真实工具调用参数/附件、返回与 output hash 绑定，并校验采集来源及字段覆盖。供应商回执无正文不能证明 prompt 一致。任意 Host JSON/假 signature 不可提升等级；缺强证据就保留 host_reported/unknown，W02-AC07 保持未通过，不削弱真实闸门。不要求新增模型执行器或强迫工具经 Deck Master 代理调用。
旧 prepared request 直接复用 `service.py:524–526` 保存的对象，不能重算历史。
证据：上述源码，原探测 P12/P13；真实采集能力仍需 W02 实际验证。

### F03 [P1，置信度 10/10] W02 的丢回执恢复承诺早于 W06 的恢复底座

涉及 W02-AC05/06/07；通用事务最终 owner 仍为 W06-AC04/06，W10 复用。
`tasks.py:1154–1171` 先 commit_change 再 write_operation_journal；`tasks.py:875–881` 在 completed 且回执丢失时拒绝原操作。原 P16 已故障注入复现，不重复跑整套探测。
W02 卡“调用成功而回传失败…允许按同 operation_id 补报”不能等到 W06 才成立。只按 operation_id 搜旧版本也不足：现有 Document.change 未保存原请求 digest 和稳定结果，不能安全识别异 payload。
修订：W02 第一个核心 PR 在现有 Store 原子提交中持久化 digest/稳定结果/提交版本，恢复派生 journal，并记录 result_refs；复用该原语，不另建数据库或调用账。W06 再扩展 plan/commit、批量、operations 查询及全部故障矩阵。W02 包内分串行 PR，通用 AC 不重复计完成。

### F07 [P1，置信度 9/10] “试作不改 current”需要区分采用内容与项目事务指针

涉及 W07-AC01/04/07/08，W08-AC05，W01 投影复用。
W07 写“candidate返回不改current”，同时要求保留 Task/Attempt/取消/结果；现有任务状态与调用事实通过 `service.py:1673–1693`、`tasks.py:1294–1348` 写入 Document 新 revision，`models.py:391–405` 已将任务管理排除在 content_identity 外。
若把“不改 current”验成 current.json/revision_id 永远不动，就无法沿用现有任务事实，也会诱发第二套候选 revision 登记。
修订：trial 提交/返回不得改变当前采用的 Page/blueprint/SVG/预览/整稿输出引用；可以通过正常 Document revision 持久化任务、调用、候选引用。generation_basis 与 adopted content 保持，project CAS 可前进。候选对象从已提交 Task/Document 引用可达，采用才改内容槽。无并发断言采用槽不变；auto 交错的内容变化必须归因给 auto。保留原质量门禁，不增加 hold/租约。

### F04 [P2，置信度 10/10] 局部损坏仍能穿透只读投影，导致整稿读取失败

涉及 W01-AC05/06。
`view.py:66–70` 对 review 读取有局部捕获，但 `view.py:123–125` 随后调用 review_status；`editing.py:203–207` 再次无保护读取 reviews/tasks。R04 注入一个损坏 review、同时存在 PPT，project_view 抛出 StoreError。
修订：新读模型对各层/评审返回局部错误和恢复动作；旧 view 的最终质量投影同样降级为不可核验，绝不显示 ready_for_export。不能靠过滤坏记录后产生 pass。当前/历史其它页继续可读；对象字节读取仍校验 hash。

### F05 [P2，置信度 10/10] W01 全部关闭需要尚未存在的 W02/W07 压力对象

涉及 W01-AC01（summary 唯一 owner）、W04-AC06（首屏/图像）、W10-AC04（heap），W12 复验。
W01 要求 300×5 Candidate×3 Attempt；W02 才定义 Attempt，W07 才实现 Candidate，ENGINEERING-SPEC§6 又把初始工厂交给 W03。原“逐卡全部验完才下一卡”的解释形成隐含循环。
修订：明确 implementation-ready / core-verified / slice-merged / AC-open / accepted 五类状态，单活动卡允许已合入切片为下游提供能力。W01 首轮完成真实读取、错误/兼容、安全和 300 页基础采样；AC01 全项保持 open。W07 形成真实 Candidate/Attempt 后返回 W01 完成原 300×5×3 压力证据，再继续；不造未来 schema 占位对象，不改阈值，不把 owner 转给 W12。

### F06 [P2，置信度 10/10] CLI 读取文档与实际命令不一致

涉及 W01-AC02/06，DX-SPEC§1/§3。
DX 写“view --json 是只读投影”，但 `cli.py:341–350` 实际返回 service_status，`web.py:397–410` 仅返回服务状态/URL。当前 parser 没有 --revision/--page-id/--lineage。
修订：保留无读取选项时的既有服务状态及 --open 行为；增加明确的 --revision、--summary、--page-id/--lineage 读取选项，使用与 HTTP 同一投影。读取选项与 --open 明确互斥；指定页必须存在。卡片补 cli.py 入口、帮助/错误契约；不再把服务状态当 Document。

## 已复用能力及未重新立项的差距

| 范围 | 本轮判定 |
|---|---|
| inputs/content_update | 已在 main；W09 复用，不重做 A 线。专用 reorder/remove、合并拆分来源仍需新增 |
| Prepared prompt | 已存于 Task.inputs，W01 读旧对象；W02 只补请求/尝试事实 |
| 候选采用 | 当前 accept 自动采用是已有生产语义；W07 新增 trial，不把现状描述为旧功能错误 |
| 固定 PPT | pipeline.py:309–323 的有序 SVG 依赖可复用；预览直接 parent 是 SVG，PPT 关联先标 derived |
| 三用途导出 | W11 已覆盖无 PPT review、engineering、固定快照、下载和 metadata canary；不可把现有 review 原样暴露 |
| 自动调度/质量 | 保留本页原图→SVG→page_visual→下一页；个人已看/候选采用不能替代 pass |
| UI 草稿 | W03 建独立 journal，W05/W06/W10 复用；不改业务 revision；跨端口只承诺已 ACK |

## 四部分工程结论

架构：共享 Store/CLI/服务与原生 ES Modules 继续采用。F01/F02/F03/F07 是先落实的契约边界；不增加第二本调用账、候选 revision 注册表或执行器。
代码质量：按 F04 在读取边界处理局部损坏；F06 让 CLI/HTTP 共享纯投影。沿既有模块抽最小函数，不为未来对象提前创建通用框架。
测试：87 个 AC 编号与卡片正文逐字相同、唯一 owner 各一；具体证据层保留。新代码按下表验证，既有测试绿色不能代签新 UI/真实 Host。
性能：F05 明确分段验收；summary 不展开候选/Attempt 正文、大图不进 JSON。缓存如有，按项目/快照/真实对象签名，损坏与更换字节不能被 warm cache 隐藏。

## 执行顺序与首卡

W01 核心可用切片 → W02 → W03 → W04 → W05 → W06 → W07 → 回 W01 关闭完整压力条件 → W10 → W08 → W09 → W11 → W12。

W02 前移排除真实提交记录的不确定性；W10 在 W07 后先完成批量与未知状态恢复。M1a 仍定义“整稿可看”，但执行时间位于 W02 后；M1b 强语义必须有真实绑定。一次仅一张活动卡；代码/schema/CLI/Host 先独立主线 PR，前端随后。核心未合 main 时不接下一段正式前端；发布/默认切换/真实 HOME 迁移没有随交接获授权。

首卡 W01：安全固定版本读取 + 摘要/单页链路 + 明确未知与局部损坏 + CLI/HTTP 兼容。无需模型/真实项目。W01-AC01 全压力和 W02 新对象适配保留待补证，不写“整卡完成”。

## 覆盖与失败路径

```text
CLI read / HTTP GET
  └─ pinned Document [core/http: current + history + concurrent current advance]
       ├─ ID / symlink / project / parent reachability [拒绝，不降到当前]
       ├─ pages → stage metadata [单对象损坏局部错误]
       ├─ tasks → stored prepared / explicit result provenance [不重算、不猜绑定]
       ├─ outputs → ordered SVG dependencies / preview snapshot [known/derived/unknown]
       └─ quality → existing check_summary [损坏不可核验，绝不 pass]
Host request → call → result [W02 real Host gate]
  └─ trial → candidate → plan → adopt [W07 core/http/browser/real Host]
       ├─ pointer/journal crash → replay [W02 minimum; W06 full matrix]
       ├─ target moved → replan; unrelated page → no regeneration
       └─ cancel/late → usage retained; adopted slots unchanged
export(fixed revision) [W11 core/http/browser/packaging]
  └─ review / delivery / engineering [snapshot quality, metadata, download hash]
```

## Implementation Tasks

| ID | 来源 | 实施包 | 行动与完成判据 |
|---|---|---|---|
| R1 | F01/F04/F06 | W01 | 统一安全读取/局部错误/CLI 对应；故障与跨项目负例通过 |
| R2 | F03 | W02 第一个核心 PR | 原请求 digest/稳定结果同事务持久化；丢 journal+后续写入仍安全重放 |
| R3 | F02 | W02 | 实际工具观察能力验证及伪高等级拒绝；真实绑定独立留证 |
| R4 | F07 | W07/W08 | current adopted slots 与管理 revision 明确分开；auto/trial并发回归 |
| R5 | F05 | W01→W07→W01 | 分段状态与完整压力回访，owner/阈值不变 |

顺序实施，不创建平行 Agent 或平行产品工作树。共享核心是连续决策，不适合多线同时改。

## 决策与外部复核

本轮常规修订按用户“常规实施选择自行处理”授权执行；未改用户功能范围、视觉方案、发布权限或真实验证口径。外部原始意见和逐项取舍单列在 OUTSIDE-REVIEW.md。其输入为截取到 30KB 的 PLAN 与明确源码片段，不等同完整独立仓库审查。

未采纳的外部建议：候选必须用离线 Document revision/新增登记表（与当前对象模型不符）；没有供应商签名就放宽 W02/W05 真实 AC（用户明确不允许）；只按 operation_id 补造旧 digest（证据不足）；缺必需 outputs 字段当作受支持旧格式（活动 schema 明确 required）。这些建议不作为已证实缺陷。

## 不在本次实施范围

沿用 TODOS 的全稿原图优先调度、自动风格评分、多人/多 Host、历史大图 GC 延后；不发布或迁移真实 HOME。输入的历史设计截图/合成回归不是新 UI 验收。没有新增产品待决策；主线合入属于实现达到可审查结果后的实际集成步骤。

## GSTACK REVIEW REPORT

| Review | Trigger | Status | Findings |
|---|---|---|---|
| Eng Review | plan-eng-review，用户指定 W01–W12 | 本轮评审完成，修订已确定 | 4 P1 / 3 P2；执行中按卡验证 |
| Outside Review | Claude Code，只读封闭输入 | completed，受输入范围限制 | 原始结果与取舍见 OUTSIDE-REVIEW.md |
| CEO / Design / DX | 本轮未重新运行 | 仅继承历史输入 | 不重复计轮次，不改已认可结构 |

OUTSIDE COVERAGE: completed；原始 modelUsage 保留，不根据工具名称推断模型身份。
VERDICT: 可开始 W01 核心切片；87 个生产 AC 尚未因此通过。
NO UNRESOLVED DECISIONS
