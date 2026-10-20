# PR127 后续独立 WebUI：实现与验证回执

> 本轮正式审查五项P2及P3已修复，最新证据见 [FORMAL-REVIEW-FIXES](FORMAL-REVIEW-FIXES.md)。产品/包源码 `50ef4d2e64e2b732bcd7ade7758a9eb86ac2cf6e`，本轮完整unit/render/browser、安装受影响路径及两份CI安装脚本均已执行，具体统计与Frozen A跳过单列。前轮33b2f522的CI已成功，以下历史PENDING不代表该旧head仍未收口；本轮新head CI单独待远端确认。专业效果与人类认可仍NOT_RUN。

## 历史分轮回执（保留原SHA与当时状态）

> 最新浏览器回归修复见 [BROWSER-LABEL-FIX](BROWSER-LABEL-FIX.md)：测试提交 `11eba83447e121f34fdb95baddfc4ebceea3cb42`，原11项复现失败后修复为11 passed，完整 required browser **548 passed / 3642 deselected**。产品文案符合中性用途合同，仅同步七处精确测试标签；新head远端CI待确认。父线程确认旧d16ed393四组unit/render成功，但browser失败，不能称该head全绿。

> 最新 CI 入口清单修复见 [ENTRY-REGISTRY-FIX](ENTRY-REGISTRY-FIX.md)，源码 `7b414a92c77a2578465e4495f5932320a1a95cb1`。原四个覆盖失败已消除；完整本地unit结果及DNS/旧SDK元数据限制逐项保留，未宣称整组全绿。现有 Draft PR130 等待新head CI。

> 最新独立复审修复见 [REVIEW-FIXES](REVIEW-FIXES.md)：源码/包 `554e9e2f91301f1b2fd223db1552f22d0df05bff`，137项相关回归及6重点分支通过，新安装版双写交接通过。独立代码复审仍进行中，AC49仍PENDING。以下3baf6caa结果为前轮准确历史证据，不重标为新SHA执行。

2026-10-20。完整 WU01–WU08 产品范围在同一云端分支实现，A/B 仅为内部增量。当前工程验收 **49 AC PASS；AC49 等待父线程最终 head CI 与独立 Draft PR 回执**。独立专业审阅、人类体验仍为 NOT_RUN，不自动合并或发布。

## 准确身份与隔离

- 分支：`codex/webui-content-methods-impl-20261020`；基线 PR127 `3217a65630023244eac5a09b3e7570954cce9188`。未合并依赖 base 为 `codex/rc5-content-methods-20261020`。父线程确认的 PR127 CI `39401753812` 仅是依赖证据。
- 最终产品、测试与包源码：`3baf6caa060d95b0f59bc2a3b973b7edc122c553`，构建工作树干净。后续回执提交只含文档/证据，不能将其称为重新构建。
- 原包 15 文件在 `4f7f2a3b` 保留，14 个 manifest SHA/bytes 匹配；六项规格裁决见 [REVISION-NOTES](../../specs/deck-master-webui-content-methods-20261020/REVISION-NOTES.md)。附件脚本只读未执行；未重试失败下载或绕过访问限制。
- 未修改 PR127/128/129。原 `/workspace/Deck-Master` 六份未提交草稿的 hash 再次全部匹配：[隔离证据](evidence/original-worktree-integrity.json)。未访问用户本机，未改真实 HOME。

## 实现与本轮复核修复

六类固定 revision 读取、方法依据、Narrative/真实 Plan/零 Page 阅读、固定双 Ref 比较、独立决定/采用事务恢复、Page 原子来源、Review 精确定位和范围草稿、用途表达、内容到设计要求、方法目录/DAG/只读准备均已实现。七份投影 schema 在活动合同目录注册并与镜像一致。所有新 GET/preview 不派发、不消耗账本、不提高 writer floor。

父线程复核及新增场景发现的问题已复现后修复：

1. 方法准备和 Review 独立草稿支持恢复；服务列表、本机副本、缓冲和导入统一核对 `context_key`，不会将另一 finding 或普通笔记认作当前稿。
2. 对当前版本复制意见保留上下文；方法 ID 保留并重新预览。Review 只复制文字，不悄悄搬运旧 Ref/scope。
3. 交接按钮等待 blur 触发的保存完成，再保存最后输入；一次点击即可进入精确正文编辑。
4. 明确刷新采用准入后，新请求使用实际有效决定 D2；原 pending 重放仍保留原 payload/UUID。
5. 选中、默认或依赖资源缺失/UTF-8 损坏返回 200 partial，完好条目仍可读，禁止复制；目录损坏返回 503。未知/越权 ID 的 400 校验保留。

原始复现：[资源/恢复](evidence/p2-reproduction.log)、[决定/单击交接](evidence/p2-other-reproduction.log)；初组修复 [5 passed](evidence/p2-fixed.log)。后续完整组包含这些场景，没有放松原事务或验收断言。

## 工程证据

| 组 | 结果 | 证据 |
|---|---|---|
| 新验收矩阵、reader、insight browser、旧个人草稿 browser | 83 passed / 126.17s | [日志](evidence/matrix-final.log) |
| RC5 资源/Host、RC4 context、四 Skill、compose、Review policy、content ops、generation unknown、Studio、安装恢复、包边界 | 441 passed / 100.58s | [日志](evidence/regression-closure.log) |
| 长条目、原子与设计限定，390px | 1 passed / 1.79s | [日志](evidence/matrix-long.log) |
| wheel/sdist、隔离 managed 安装、安装版三视口/两步采用 | PASS | [包回执](evidence/package-closure.json)、[浏览器](evidence/installed-browser-closure.log) |
| 实际安装 baseline → upgrade → rollback | PASS | [回执](evidence/rollback-closure.json)、[日志](evidence/rollback-final.log) |
| 三类实际 Host 正文 + 副本 Review 定位/交接 | PASS，质量认可另列 | [摘要](evidence/three-scenario-summary.json)、[浏览器](evidence/three-scenario-browser.log) |
| 修改 Python 的 ruff、git diff --check | PASS | 最终提交前执行 |

组间可能有重叠，不相加为去重测试总数。失败日志保留：测试夹具最初将 imported 的实际空映射当成缺映射、探针最初期待未来 writer 项目能启动服务，均按真实合同修正验证设置，没有修改产品来放行。前一轮 3c6d4a41 的 79/182 项和包证据仅保留作历史，不冒充当前包。

```bash
PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild/test_webui_acceptance_matrix.py tests/rebuild/test_webui_content_insight.py tests/rebuild/test_webui_content_insight_browser.py tests/rebuild/test_pr105_draft_browser.py
PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild/test_rc5_resource_catalog.py tests/rebuild/test_rc5_host_selection.py tests/rebuild/test_rc5_library_acceptance.py tests/rebuild/test_rc4_work_context.py tests/rebuild/test_rc3_four_skills.py tests/rebuild/test_compose_v2_phases.py tests/rebuild/test_rc3_review_policy_ready.py tests/rebuild/test_rc3_review_policy_workflow.py tests/rebuild/test_content_ops.py tests/rebuild/test_generation_protocol.py tests/rebuild/test_studio_content_browser.py tests/rebuild/test_rc3_studio_intake_browser.py tests/rebuild/test_install_preparation_compatibility.py tests/rebuild/test_install_transaction_recovery.py tests/rebuild/test_package_boundary.py
/workspace/Deck-Master/.venv/bin/python tools/build_release.py --out /tmp/webui-release-closure
```

长正文测试在首组收集后单独运行，故首组为 83 项；目前该文件包含 52 个参数展开用例。使用系统 Chromium，没有重复浏览器下载。安装服务使用 managed `venv/bin/python -I`、cwd `/tmp`、无 PYTHONPATH，断言 site-packages、sys.path 无 checkout，并核对服务静态字节。

release：`3baf6caa060d-c531f410af0f`；完整 wheel/sdist SHA 见包回执。版本保留 `1.0.0rc5`，未预占 RC6。临时 prefix `/tmp/webui-managed-closure` 真实激活 PR127 包、新包，再 rollback，均 `register_host=False`；结束时该临时 prefix 指向 PR127。现代稿/旧稿/历史版本/无 manifest Task 均可读，legacy 输入写入与 future-writer 写入拒绝，业务对象/current/revision hash 不变。未知 writer 的写入因历史无法验证保持 unknown，未作为允许重放。

安装截图：[1280](evidence/closure-actual-host-1280.png)、[1440](evidence/closure-actual-host-1440.png)、[390](evidence/closure-actual-host-390.png)、[方法](evidence/closure-methods-1440.png)。三视口无页面横溢；键盘/modal 焦点、长正文和选字有自动化证据。代理查看截图不是用户认可。

## 实际 Host 与认可分层

当前云端代理使用 [deck-content Skill](../../../skills/deck-content/SKILL.md)，读取冻结方法后，对经营诊断 M04、方案权衡 M05、教学 M09 三类公开合成材料执行真实 create/continue/task start/accept、决定及采用，分别返回 framing、argument 与两页正文/Plan。数字和事实均明确是合成工程场景，不是客户材料。没有将测试 helper 的固定输出冒充 Host，也不冒称另一模型或独立审阅者。

首次向已冻结任务再次传资源选择被 Runtime 拒绝；核对后读取原 Task 清单，没有补卡。内容原项目保留在 `/workspace/webui-evidence/scenarios/{diagnosis,options,lesson}/project`。三类浏览器均读取主线、原句、来源；Review 定位与交接采用**独立复制项目中的显式 synthetic Review**，原始 Host 项目不变。该 Review 只验证工程路径，不能证明成稿专业通过。原零 Page 教学 plan_only 实际 Host 证据继续保留。

| 层 | 当前状态 |
|---|---|
| 规格结构 | 历史 PASS；不替代产品 |
| 工程/浏览器 | 上述限定组 PASS |
| 安装/回退 | 精确 SHA PASS，真实 HOME 未改 |
| 实际 Host | 三类 content_full 正文 Runtime 链路 PASS，当前代理执行 |
| 独立专业审阅 | NOT_RUN |
| 人类体验/认可 | NOT_RUN |
| 最终 head CI / 独立 Draft PR | PENDING 父线程 |

## 远端边界与接续

[逐 AC 账本](../../specs/deck-master-webui-content-methods-20261020/execution-ledger.json) 为唯一状态来源；[WU08 映射与余项](WU08-FOLLOWUP.md) 指向具体新增测试。

原 `gh pr create --draft` 和同通道只读查询均实际执行后 exit 1，`Post "https://api.github.com/graphql": Forbidden`。这是 API_ACCESS_ERROR，不是工具审批 DENIED。本任务未重试或换通道。父线程后来独立核对当时无 PR，前次分支 CI `39415132380` 对应 6ee00b9b，不能用于最终 head。最终 Draft 创建与 required CI 由父线程通过其已授权连接完成；这里不虚构 URL/编号。只推送同一独立分支，不合并或发布。
