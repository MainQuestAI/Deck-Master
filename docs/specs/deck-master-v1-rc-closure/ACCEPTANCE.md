# 验收与证据

实际修复 PR：[PR #102](https://github.com/MainQuestAI/Deck-Master/pull/102)，base 为 PR99。
产品代码闭合提交为 `802f29d`；后续补充下载/乱序回归与此证据索引。最终源码、包摘要和模块路径以
仓库外 `release.json` 与验证记录为准，不能从版本号推断安装来源。

当前结论：本轮修复及工程、安装包、真实单页组合验证完成；**RC 放行仅待用户视觉确认**。
2026-10-05 解锁后补测：有界面 Chromium 中经原生点击进入全屏、系统 Esc 退出，焦点恢复、路由及候选保持不变。此前锁屏阻碍保留为历史记录，没有用网页模拟键盘替代本次原生验证。
已准备实际工作台和目标页 PPT 样例，Host 自审没有记作用户认可。

## 问题到修复及证据

| 评审 | 修复提交 | 正常入口/回归证据 |
|---|---|---|
| P1-01 | `8e9526e` | service 四个拒绝、CLI 拒绝/有效/精确重放；原请求、取消迟到、调用事实顺序保留。实际 HTTP 创建分析及 CLI/service Host 接手采用完成。既有服务没有新增 Host 接收 HTTP 端点。 |
| P1-02 | `001d3f2`、`64b667e`、`802f29d` | 要求逐字恢复/取消选择/跨端口、精确依据与只读；缓冲已出现但项目尚未读完仍只读；冻结 A 与后写 B 并存，冲突显示分开，原 UUID 核实/重放沿用既有机制。 |
| P2-02 | `001d3f2` | 旧稿保留，新稿复制文字，page 范围、无旧章节/区域/选择/计划，要求重新选意见。 |
| P2-03 | `001d3f2` | 两份预备稿首次选择及反复切换只有一个恢复面板；实际下载的恢复 JSON 绑定当前选择的原文摘要。 |
| P2-01 | `ba2a280` | 旧快照查询显式 revision，无未来候选；导航沿用固定版本，与中央入口一致。 |
| P2-04 | `001d3f2` | 真实本地服务器列表乱序成功及错误回包均不能覆盖最新意见或提示；校验代次/查询版本/生命周期。 |
| P2-05 | `64b667e` | 正文候选只读一次固定 lineage；快速切候选/切页并销毁旧组件后，旧成功/失败不改正文、路由或错误提示。 |

`test_visual_styles_web.py` 与 `test_rc_closure_browser.py` 保存定向回归。
前者在 PR99 基线 5 个反例失败、修后相关分析/HTTP/CLI组23项通过；后者旧源码捕获9项缺陷，
缓冲恢复反例旧源码再次失败。保存前后日志，不以测试摘要替代实际业务。

## 分层验收

| 层次 | 状态与实际证明 |
|---|---|
| 工程 | Ruff 通过；1231项非 browser/render 测试通过；52项真实渲染通过。初次直接 pytest 启动遗漏仓库根目录的2项安装导入失败，按 CI 的 python -m pytest 复核通过。 |
| 浏览器 | 117项完整组合通过，包含三视口1440×900、1280×800、390×844；随后增加实际下载及4项快速切换保护，最新15项定向回归通过；完整最新浏览器应为121项，最终CI对应最新测试树。仅控制延迟/失败，业务读取来自真实本地服务。 |
| CI | 源码 `ebf32ec` 的 push/PR 工作流均成功；[PR 工作流](https://github.com/MainQuestAI/Deck-Master/actions/runs/37299277637) 含 Python3.11/3.12×Node22/24、render、必需 browser/installed UI、Group report。该工作流包含1231项单元、52项render及121项browser。原生补测后的文档提交按最终HEAD重新跑同一门禁，状态见PR检查；本次没有产品代码或运行资源变化。 |
| 包 | wheel及sdist构建；sdist再构建wheel的205份运行文件与直接wheel逐字一致。独立非 editable环境的 doctor确认site-packages来源；7组离线UI/固定导出/资源检查及11项恢复回归通过。最终源码包继续核对同一运行文件摘要。 |
| 安装器 | 仓库外隔离prefix安装两份实际包、切换及回退通过；register_host=False，真实HOME current未改变。保留manifest、源码SHA、wheel/sdist摘要及模块路径。 |
| 真实 Host | 既有30页的新副本完成截图七维分析/规则确认→原生ImageGen试作→固定比较采用→SVG重构；连续A/B意见、改写要求、刷新与重启换端口恢复→SVG trial候选→比较采用→正常continue编译、渲染、回读、适用审阅及三种导出。 |
| 真实产物 | 最终revision `223f7b06fa784c37bd9b7eb52083e12b`，readback/check均pass。目标页33个原生shape、0张picture；其Page未变，其它29页Page/原图/SVG引用和实际PPT预览摘要均未变。 |
| 交付检查 | 安装包CLI final-readiness=ready；对实际导出deck.pptx执行delivery handoff-check=verified，记录为sanitized_copy，不能声称原PPT文件字节相同。 |
| 原生全屏 | **通过**：源码 `ebf32ec`、真实工程固定候选。有界面 Chromium 两次原生点击/系统 Esc，DOM full screen 进入及退出、按钮焦点恢复、路由和候选不变、零 pageerror；第二次桌面 AX 同时确认焦点在“全屏比较”。三视口无横向溢出。 |
| 用户确认 | **待用户确认最终UI及实际风格样例**；已提交查看入口，没有推断认可。 |

真实失败保留：最终编译曾报告标准atom身份不匹配；经正常repair只纠正data-atom-id，
SVG预览摘要保持，重新独立审图与回读通过。旧图标/断行发现按原review_id/finding_id及replaces关闭，
不删除或改写历史。最终repair任务沿用原体系的整稿审阅scope，但本轮仅提交目标页SVG，未重派其它页制作。

## 仓库外证据索引

受管理worktree相邻 `evidence/`：`r01-before.log`、`r01-after.log`、`browser-before-final.log`、
`buffered-before.log`、`rc-complete-final.log`、`prepared-download.log`、`unit-final.log`、
`browser-complete.log`、`render.log`、`install-recheck.log`、`installed-recovery.log`、
`installed-ui-802f29d/checks.json`、`isolated-install.json`、`sdist-parity.json`及最终包/manifest。
记录带本机路径的私有证据只保存在仓库外；此处不提交客户内容、恢复文件或导出原件。

原生补测证据在私有本轮目录：`headed-fullscreen.json`、`headed-fullscreen-entered.png`、
`headed-fullscreen-exited.png`及三视口比较截图；记录原生输入、源码SHA和候选身份。

真实工程证据在私有本轮目录：baseline、analysis工作单/结果、固定generation输入/真实调用结算、
两次候选/采用、requirement-browser、不可变失败/repair回执、当前readback、native形状检查、
unaffected-pages、host_self reviews、三种导出、installed-final-readiness及handoff-check。

版本保持 `1.0.0.dev2`。本轮不合并、不真实HOME安装/激活、不创建tag或Release。
放行必须全部必需项通过且取得用户视觉确认；后续合并顺序仍为PR98→PR99→修复PR，核对最终组合CI。
