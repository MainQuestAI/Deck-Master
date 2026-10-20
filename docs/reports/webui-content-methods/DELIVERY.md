# PR127 后续独立 WebUI：实现与验证回执

2026-10-20。本轮在云端独立分支 `codex/webui-content-methods-impl-20261020` 实现完整 A/B 产品范围；WU08 验证仍有明确欠项，交付形式为 Draft，不是全部 50 AC 收口或正式发布。未改 PR127/128/129、未访问用户本机、未激活真实 HOME。

## 基线与准确身份

- 最终适用 PR127 基线：`3217a65630023244eac5a09b3e7570954cce9188`。父线程确认 CI `39401753812` completed/success；只作为依赖基线证据，不冒充本 PR 检查。
- main 最后观察 `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8`。PR127 未合并，本 Draft 明确依赖 `codex/rc5-content-methods-20261020`，不自动合并它。
- 本轮准确实现与包源码：`3c6d4a4160041cfa11ce88a0e9bea2ae46f872c3`，构建时工作树干净。后续回执提交仅文档/证据，产品代码与此 SHA 相同。
- 原规格 15 文件文本已保留在 `4f7f2a3b`，14 个 manifest entries 的 SHA/bytes 全匹配；六项修订见 [REVISION-NOTES](../../specs/deck-master-webui-content-methods-20261020/REVISION-NOTES.md)。附带验证脚本只读，未执行。原 ZIP 无法物化的历史限制没有通过改 URL/执行环境绕过。
- 原 `/workspace/Deck-Master` 的六份未提交草稿及其备份保留；实施目录 `/workspace/Deck-Master-webui`，另有独立规格工作树。

## 已实现范围

| 卡 | 实现与边界 | 验证状态 |
|---|---|---|
| WU00 | 最终基线、接口漂移、原包校验、独立工作树 | 基线通过；元信息读取拒绝以父线程确认补齐 |
| WU01 | 六类固定 revision GET；合法引用链；七份读投影 schema；共享纯采用/决定检查；HTTP 严格查询 | 核心/HTTP/无写入/损坏分支检查通过，详见逐 AC 欠项 |
| WU02 | Task 冻结 manifest 顺序/hash、当前可用性单列；旧记录退回 ID/未记录 | 有实际 Host 任务回读；旧安装 UI 专项矩阵尚不完整 |
| WU03 | Narrative/真实 Plan/零 Page 职责、固定两份 Ref 比较；独立决定及采用 UUID/lookup 恢复 | 实际两步采用、决定回执丢失后刷新恢复、不同 Plan 关联通过 |
| WU04 | Page 原子→原绑定 Narrative/限定/来源；旧主线、局部损坏、返回深链 | 段落与旧绑定通过；表格/条目全键盘矩阵待补 |
| WU05 | v1/v2 原值、Ref/revision/finding/index 定位；独立问题草稿；有界交接原编辑流程 | 深链刷新、无默认首项、草稿隔离通过；完整修改提交专项待补 |
| WU06 | 中性用途文案；同 Page 的冻结/推导内容要求；多冻结任务不任意代选 | 相关既有设计要求回归通过；新投影多任务专项待补 |
| WU07 | 服务 resolver/DAG、M04+E04、独立/项目上下文、只读正文、个人准备稿、重新核对后复制 | 无新阶段 200、指纹409、无全库正文扫描、三视口预览通过 |
| WU08 | 准确 SHA wheel/sdist、managed 候选安装、安装版三视口与采用、实际 Host 教学链路、分层账本 | 验证部分完成；下列限制不能隐去 |

所有读取和方法准备均不派发、不消耗调用账本、不提高 writer floor；脚本只展示正文。原四个公开 Skill、旧冻结 Task、CAS、事务锁及原写入准入保留。设计/口播/来源问题不统一改正文。资源可读、复制、Host 返回、采用、专业通过、人类认可分别表达。

## 可复核工程证据

解释器为云端 Python 3.12；浏览器为现有 `/usr/bin/chromium`。默认 Playwright 缓存缺失后使用已安装系统浏览器；未重复已拒绝的浏览器下载。

| 运行 | 实际结果 | 证据 |
|---|---|---|
| 新 reader/browser + RC3 design requirements + personal recovery | 79 passed / 22.16s | [原日志](evidence/targeted-79.log) |
| 最终准确提交：reader、compose phases、collaboration adapters、review policy、content ops、operation recovery、package boundary、Studio content/navigation/page、新 WebUI browser | 182 passed / 142.23s | [原日志](evidence/regression-final.log) |
| ruff：本轮 Python 模块/新增测试；git diff --check | PASS | 命令记录于下；未声称全仓 lint |
| wheel/sdist + managed install + 安装服务浏览器 | candidate_ready；activated=false；三视口及两步采用 PASS | [包与安装回执](evidence/package-verification.json)、[浏览器日志](evidence/installed-browser.log) |

79 与 182 存在重叠，不相加。前期真实失败包括 schema 镜像漏登记、方法准备草稿重复挂载影响旧定位、窄屏导航挤出首个编辑控件、旧 revision 隐藏原方向操作恢复入口；均保留历史日志并由最终相关组覆盖。没有降低原断言或放松 Runtime 准入。

最终回归命令：

```bash
PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild/test_webui_content_insight.py tests/rebuild/test_compose_v2_phases.py tests/rebuild/test_rc3_collaboration_adapters.py tests/rebuild/test_rc3_review_policy_workflow.py tests/rebuild/test_content_ops.py tests/rebuild/test_workbench_operations.py tests/rebuild/test_package_boundary.py tests/rebuild/test_studio_content_browser.py tests/rebuild/test_navigation_usability_browser.py tests/rebuild/test_studio_page_browser.py tests/rebuild/test_webui_content_insight_browser.py
PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -B tools/build_release.py --out /tmp/webui-release-final
```

构建 release `3c6d4a416004-43d1dc6b688b`；wheel SHA256 `43d1dc6b688b60340f1a9fa253d43c9d0ee961650088f9621b51d0dd95be3032`；sdist SHA256 `3267d603c77b477e4dac6ac199e09e353086de28f4399f36a444fc9d9179090b`。版本号保持仓库原值 `1.0.0rc5`，未预占 RC6。

隔离安装位于 `/tmp/webui-managed-final/.deck-master/releases/3c6d4a416004-43d1dc6b688b`。server 用该安装的 `venv/bin/python -I`，cwd `/tmp`，无 PYTHONPATH；断言模块来自 site-packages、sys.path 无 checkout，并核对 HTTP 静态文件 SHA。Playwright 客户端单独用既有测试解释器。系统缺 rsvg-convert 时，仅下载与本机 librsvg 对应的 Debian `librsvg2-bin_2.60.0+dfsg-1_amd64.deb` 到临时目录解包，未安装到系统；managed compile/render probe 均完成。

实际检查截图：[1280](evidence/actual-host-1280.png)、[1440](evidence/actual-host-1440.png)、[390](evidence/actual-host-390.png)、[方法预览](evidence/methods-1440.png)。三视口均无页面横向溢出；已人工查看本代理可见的窄屏主线与桌面方法截图，这不是用户人类认可。

## 实际 Host 与认可分层

本会话代理按 [deck-content Skill](../../../skills/deck-content/SKILL.md) 读取真实冻结五项方法与公开合成教学材料，执行真实 service/create/continue、task start/accept，手写 framing、argument Narrative 与四职责 planned Plan；没有导入测试 fixture 冒充 Host。方法准备选中 `content-m04`，后续真实任务 manifest 含它。结果为 **accepted proposal，尚未采用**；plan_only 任务完成不等于专业通过。准确 Task、Ref、材料/回执 hash 见 [Host 摘要](evidence/actual-host-summary.json)。完整工作目录保留在 `/workspace/webui-evidence/actual-host/`，未把生成 run 提交入仓库。

首次 argument 提交因 `speech_policy.source=derived` 不合法被拒绝；核实任务仍运行、无指针写入后改为真实合同的 `default`，保留失败信封再提交。未改 schema 迁就样例。Host 身份仅为当前云端代理，不冒称另一模型、Astra 或独立复审者。

| 层 | 结果 |
|---|---|
| 规格结构 | PASS，历史静态检查；不是产品通过 |
| 工程/浏览器 | 上表限定检查 PASS，完整 AC 仍有欠项 |
| 独立安装 | PASS，准确实现 SHA 的候选；未激活 HOME |
| 实际 Host | PARTIAL：教学 plan_only 链路；不是三类完整场景 |
| 独立专业阅读 | NOT_RUN |
| 人类体验/认可 | NOT_RUN |

## 尚未闭合与接续

唯一逐项结果见 [50 AC 执行账本](../../specs/deck-master-webui-content-methods-20261020/execution-ledger.json)。部分覆盖的 AC 保持 NOT_RUN，并在 coverage/limitations 写清已测部分，未批量打勾。重点待补：current+candidate/history 完整比较浏览器矩阵、采用第二步丢回执与并发、Review 草稿→原 plan/commit 全链、表格/条目与全键盘、旧 Task/hash 漂移 UI、剪贴板漂移、多冻结设计任务、新旧合同安装回退，以及经营诊断/方案选择/教学三套完整场景。人类认可和独立专业审阅需真实执行者，不能由工程代填。

GitHub PR 元信息读取曾返回 GraphQL Forbidden，已按新证据允许的一次重试后停止；未改 API/执行环境绕过。推送与 Draft 创建是父线程另行授权的操作，实际结果由后续提交/最终回执记录。新 PR 的 required CI 尚无本任务读到的结果，不能借用 PR127 的全绿。

回退可移除新 UI/capability；不重写 Document、Task、Narrative、Review，不降 writer floor。继续只在此独立云端任务修订同一 Draft，不自动合并、发布或启动浏览器派发。
