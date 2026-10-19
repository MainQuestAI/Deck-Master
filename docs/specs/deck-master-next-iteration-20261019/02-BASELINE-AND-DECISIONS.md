# 02 固定基线、审查事实与设计裁决

## 1. 基线和证据用途

固定提交：[a08bc68c1cbbbc806205104c2bb01f3f096305f0](https://github.com/MainQuestAI/Deck-Master/tree/a08bc68c1cbbbc806205104c2bb01f3f096305f0)。

2026-10-19 编写本包前，已再次查询远端 main，未较前一轮审查变化。当前源码是 1.0.0rc3；下一轮 1.0.0rc4 为建议候选。PR 120–123 已合并。旧 draft PR 113 仍需核对后续替代关系；是否关闭它不影响本轮不受影响研发，也不是自动授权的仓库操作。

已有 CI：[Rebuilt Core Gate run 39170555082](https://github.com/MainQuestAI/Deck-Master/actions/runs/39170555082) 的七个 job 成功。上轮审查记录的单元矩阵各 2972 passed/2 skipped、render 133 passed/1 skipped、browser 491 passed、installed 240 passed、offline 9 verified，是该基线的证据。它们不是新实现通过的证据，也不是后续必须维持的用例数量。

编制时 GitHub 已发布 Release 与 main 源码候选存在时间差；latest Release 仍为 v0.9.14-preview.2。N5 应准确区分源码版本、候选包、活动安装与已发布 Release，不能用更新 README 模拟发布完成。

本机安装、开发工作树、Host 模型和工具链可能不同，**需要 Codex 核验**；不得把此隔离审查环境说成用户本机已验证。

## 2. 已确认的问题及其实际边界

| 编号 | 证据与定位 | 已确认影响 | 不扩大解释 |
|---|---|---|---|
| B-N1-A | [service.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/service.py) 的 _read_input_operation / inputs_update；[operations.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/operations.py) | 旧 inputs update 成功后删回执缓存，同 ID/base/payload 重试返回 revision conflict；通用 operations show 无原子 receipt 可验证 | 旧缓存读取已经核验 revision 在 current 链，不是“预写缓存即可制造提交成功”；复现没有重复写入 |
| B-N1-B | [web.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/web.py) 老路由错误处理；[eligibility.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/eligibility.py) | pause 条件下服务层的 409 与详细原因经旧 HTTP 变为 422、信息损失 | 请求仍被拒绝，不是暂停绕过 |
| B-N1-C | eligibility.describe 与 [collaboration_api.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/collaboration_api.py) 的 eligibility | orphan revision 的 Python describe 可读，CLI/HTTP 在已提交快照边界拒绝 | 只修已确认入口，不泛化成所有 SDK 都有写入越权 |
| B-N2 | [install.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/install.py) 的 _compensated / activate / _sync_host_skill | 隔离的旧单 Skill → 四 Skill 升级，第 3 个链接处 KeyboardInterrupt 可留下 current 已切而四链接不齐 | 已有 OSError 补偿测试通过；未证明常规四链接 → 四链接都会缺链 |
| B-N3-A | [models.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/models.py) validate_narrative_semantics；[content_production.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/content_production.py) _accept_narrative | 含中心与孤立节点、无边的 argument 在正式 task accept 路径被保存为 accepted proposal | response adopted=false，当前 Narrative 指针未改变，不能声称它已经交付或绕过正式采用 |
| B-N3-B | [method_resources.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/method_resources.py) 与 service.task_summary | final Review 的默认方法集合缺内容方法/校准，role 集合与 Skill 正文有差异；Task 未记录精确有序 manifest | 方法文件本身已存在；不能把“文件齐备”视为“实际派发和应用正确” |
| B-N4-A | service.task_summary、method_resources 的 bundle | 一个新 Task 样本的 34850 bytes 方法正文被同响应带两份，总 JSON 86343 bytes；未结束 Task 还会展开全部 source extracts | 样本只证明重复与读取机制，不是所有任务的恒定开销；已结束 Task 有提前返回 |
| B-N4-B | operations.committed_record、[store.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/store.py) operation_receipt、[snapshots.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/src/deck_master/snapshots.py) | 合成 100/500/1000 revision 的重复查询每次仍完整解析 100/500/1000 份历史 JSON；写出的 index 未被查询消费 | 未证明真实客户当前已卡顿；缓存优化不能改变 canonical ancestry 作为事实来源 |
| B-N5 | [ROADMAP.md](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/ROADMAP.md)、[CLAUDE.md](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/CLAUDE.md)、[test_package_boundary.py](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/tests/rebuild/test_package_boundary.py) | 活动路线图仍要求旧 backend bind；CLAUDE 带本机配置断言；扫描未覆盖四 Skill 和 CLAUDE | README 的 create → continue 已能正常进入 framing，不应称新手路径完全不可用 |
| B-N6 | [RC3 收口报告](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/docs/reports/rc3/closeout-20261018/README.md) | 已有完整稿、八页产物和定向返修记录，但不足以推出“从原料生成的首稿总体提升” | 历史 18 条几何 finding 已有定向修复，不作为本轮仍未修的 bug；原产物包在仓库外，未取得时不得假装复查完成 |

上轮规模盘点：已跟踪文件 4117 个，docs 3293 个；约 146.2 MB 的 docs / 164.9 MB 全工作树已跟踪内容；860 个 Markdown、约 10.5 万行。以上是工作树内容统计，不是 Git 对象库大小、下载体积或 wheel 大小。68 份活动 schema 与各自 spec 镜像已一致，不能为减文件数删除。

## 3. 设计裁决

以下 D01–D14 是跨卡实现必须一致遵守的决定，不能由并行 Agent 分别选择。

| ID | 决定 | 理由/约束 |
|---|---|---|
| D01 | 继续单 Runtime、单 current revision、既有 Task 与 CAS | 修复已知缺口，不建立第二事实中心 |
| D02 | N1 共用 canonical receipt resolver，旧输入 ID/digest/response 通过适配保留 | 直接启用新分支会误拒旧合法非 UUID ID |
| D03 | 提交事实只来自已提交链及原子 receipt；磁盘缓存/索引只能作派生提示 | 缓存缺失、损坏或伪造不能改变提交事实 |
| D04 | 同操作可核实重放优先于旧 base 的新写 CAS；payload 冲突必须拒绝 | 已完成请求丢回包应取回结果，不应再提交 |
| D05 | N2 持久安装事务；可选 transaction-id 区分精确恢复与新的 rollback | 无 ID 的已完成 rollback 再调用保留现有切回语义 |
| D06 | N3 新 argument 结构实施显式校验政策，旧历史读取/已提交精确重放不追溯判错 | 修复新写入，同时保持历史可读可核对 |
| D07 | Task 新字段在 schema 中对历史兼容可选；新派发 producer 必写 manifest，适用 argument 必写 policy；首次相关持久写入提升 rc4-content.v1 writer floor | 当前 schema additionalProperties=false，旧 writer 不得误写含新事实项目 |
| D08 | 旧活动 Task 的方法变化显式 basis_changed，走既有正式重新派发 | 新方法清单不得悄悄塞给旧 Task；不凭当前文件冒认旧 hash |
| D09 | N4A 为显式协商 work_context.v2，只读投影；v1 默认不变 | 去重和延迟全文改变响应语义，不能继续冒称 v1 |
| D10 | v2 读取不提升 writer、不记“已读/已认可”业务事实；有副作用入口先协商再执行 | 上下文优化不增加权限或制造阅读/同意证据 |
| D11 | N4B 冷启动验证完整 canonical ancestry；热态可用轻量签名，unknown 不等于 not_found | 可优化 JSON 解析，不以未经验证的索引证明不存在 |
| D12 | N5 活动文档统一入口、历史报告保留时点；版本由集成 Owner 一次更新 | 避免另造一套当前状态，避免多分支版本冲突 |
| D13 | N6 必须把具体方法/布局改进应用到正常完整任务和实际产物 | 工程 fixture、记录模板或结构检查不能代替效果工作 |
| D14 | 已取消实验/固定人数/默认人工审批不恢复；缺能力只阻塞相关证据 | 依据当前任务完成，不向用户附加试验组织负担 |

## 4. 命名与权威

- `content-ops.v1`：现有持久操作能力，N1 优先复用。
- `rc4-content.v1`：本轮新增持久内容功能 writer 边界，仅 N3 Owner 修改合同，由集成 Owner 合并。
- `work_context.v2`：本轮新增只读上下文响应能力，N4A Owner 实现；不是 Task protocol_version。
- 安装事务 schema：安装前缀内的控制记录，不放进项目 Document，不构成新的用户审批事实。
- N1/N4 resolver 的逻辑三态：committed、not_found、unknown；verified 只描述验证过程，不是第四种 state。对外错误须保持稳定映射，具体遵循任务卡。
- `execution-ledger.json` 与 `quality-observation.json`：离线开发文档，不是 Runtime schema。

以上名称若因核验现有实现存在同名冲突而必须调整，应在改代码前更新本包设计裁决和所有消费方；不能只在某个 PR 中静默改名。常规函数/局部变量命名由执行 Owner 自主决定。

## 5. 继承与优先级

RC3 和内容协作 v1.2 中未被本包明确修改的业务合同继续有效。专业内容判断继续引用当前适用的 [RC3 ACCEPTANCE](https://github.com/MainQuestAI/Deck-Master/blob/a08bc68c1cbbbc806205104c2bb01f3f096305f0/docs/specs/deck-master-v1.0.0-rc3/ACCEPTANCE.md) 与其链接的原能力判据。本包 AC-N1…AC-N6 是增量开发验收，不重新创建全量专业 AC/CQ 的第二套 PASS 状态。

历史证据可以带准确版本和依赖范围引用。新行为、新方法 hash、实际安装资源、当轮产物及效果改进必须补当前候选证据。旧报告中曾因已取消实验阻塞的条目不能批量改为 PASS。

