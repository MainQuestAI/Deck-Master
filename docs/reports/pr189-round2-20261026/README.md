# PR #189 第二轮修复与验收边界

基准 `f06a8061490296588e3bc4d4d4ea5b4ce5593b62`；本轮按两份独立评审与用户确认的“全部纳入”方案执行。PR 保持 Draft，不含合并、发布或实际 HOME 迁移。

## 行为与接口

| 问题 | 本轮处理 | 核验入口 |
| --- | --- | --- |
| F1 旧待采用原图候选 | 候选依据统一使用完整冻结契约选项；未知契约拒绝，不改旧对象。精确 main afcc23d 源码创建的候选升级后正式 plan/adopt 成功，43 个原对象及调用账本不变。 | test_pr189_round2_candidate_visibility.py；独立 exact-base 反例 |
| F2 省略 finding 的中间复查 | 显式同身份替代链继续遍历，节点可无新判断；端点依原 finding owner 的当前主体、依赖、实质变化与证据决定。重开恢复待返修，生产仍阻断。 | test_pr189_round2_finding_structure.py；test_pr189_reopened_finding.py |
| F3 暂停污染已采用正文关系 | 内容语义比较排除已知请求控制字段；阅读保留，写入/采用/交付仍由实时门禁判定。 | test_pr189_round2_completed_controls.py |
| 安装坏邻居与合法中断误诊断 | collect 返回逐条可信/不可核实结果和 pending 核实状态；strict discover 继续阻断不可信全局现场。status 与恢复共享纯阶段观察，backed_up 可续跑，归属冲突移除 resume。 | test_install_transaction_diagnostics.py；既有子进程中断恢复矩阵 |
| 历史文件识别及读取成本 | 历史元数据和普通对象 stat 建索引，候选有界读取，仅对匹配原件读取并验证 hash。返回所有匹配 revision/output 引用；断链或损坏明确 incomplete/gap，仍 blocked。 | test_pr189_history_handoff.py；test_selected_file.py |
| finding 计数口径 | 原阻断记录保留，附明确来源和逻辑 owner；新增 blocking_record_count / logical_finding_count。open_findings 保留记录数 alias；UI 分别标记问题数与记录数。 | 核心计数回归；资格与共享提示 |
| 个人清理回包丢失 | 请求及 operation 在发出前保留本机；未知结果刷新可恢复，同编号同请求主动重放。新回执绑定 input_digest，不清后增草稿；旧缺 digest 回执仍可读/恢复备份，无法证明精确请求时拒绝重放。 | test_pr189_clear_replay.py；test_pr189_clear_transport_browser.py |

`historical_output` 仅证明匹配已提交的原始文件，不批量重建历史 sanitized copy，也不构成交付许可。history_status=complete 表示已提交元数据索引完整，不表示复读了每份历史 PPTX 字节。机器冲突 code 替代自由文本判断，尺寸/读取变化继续 HTTP 409；读取路径仍拒绝 symlink、设备、FIFO 和目录。

安装状态 v1 输出加法提供 discovery_complete、recovery_blocked、diagnostics、pending、记录 verification 和 action.phase。不完整发现不等于没有 pending；指定不存在 ID 时可以扫描完整而所选记录不可核实。状态是无锁只读观察，执行始终在 prefix→Host 锁内重验。

## 定向证据与失败保留

- 历史交接的有效红批 5 failed，修复及成本补例后 6 passed；首次 fixture 构造错误另留，未计作产品缺陷。与文件核验、review/notes/trial、个人清理邻接最终 165 passed / 1 deselected。
- 个人清理请求绑定红批 5 failed；丢回包真实浏览器红批 2 failed。修后包括未送达、成功后丢响应、不可解析响应、刷新重放与首轮 CAS 拒绝。个人恢复/控制邻接浏览器、共享错误提示分别验证，不累加重复覆盖。
- 核心第一阶段定向 333 passed，保留精确旧源码候选采用反例；随后补充公共多轮省略再重开流程和省略后保持关闭场景，最终统计见 PR 当前候选验证段。
- 安装红批 16 failed / 4 passed；核心 262 passed，Host/入口邻接 69 passed，资源映射 38 passed。调整当前冲突的可用动作后，控制/诊断 54 passed，是核心子集复跑。状态旧版抛错断言改为不可核实结果，同时保留 strict recover 必须拒绝的断言。
- Ruff（src/deck_master 与 tests/rebuild）、JS 语法与 diff 检查通过；最终冻结后的全矩阵、完整浏览器、渲染、独立安装和离线证据另以候选提交记录。

## 测试与 CI 声明范围

第一轮“无删除断言、无新增 skip”的声明仅限 `c217d342..f06a8061`，不能扩大到整个 PR。相对 main 的全 PR 还包含 #185/#188 的断言替换、真实渲染工具条件 skip，以及 DESIGN.md 于 2026-10-24 授权的桌面 32/36px、触控 44px 规则。第二轮对安装状态的失败方式作了明确合同变更，公共复查测试参数化增强；均需在最终差异审计中独立列出。

CI 是每个事件 7 项检查（含汇总），push 与 PR 两次执行。矩阵、安装、定向和重试不可相加成独立覆盖。历史候选 f06 的成功不证明本轮候选成功；最终以 PR 正文记录的新 Head、日志及证据包为准。

## 尚未替代的验收

本地旧基准同样失败的 11 项渲染与 3 项键盘用例保留，未据此宣称通过或确认平台根因。Frozen A 外部资源、真实 Host/S3、专业效果、原生目录选择器取消、用户视觉认可及来源 owner/第二人签收继续独立记录。工程 gate 不代替人工批准；Mac 锁屏不作为当前阻碍。
