# PR188 两轮审查修复与重新验收

审查起点为 `e2bccee8`，父基准仍为 PR184 的 `7bbf204658dfc39f53fa34352543168e7eee1e65`。两轮审查共 8 项代码问题（2 P1、5 P2、1 P3），不以此前 28 项工程验收或旧 SHA 的 CI 成功推定这些反例通过。

修复仅涉及 UI 读取投影、接口兼容、轮询生命周期、控件表现和阅读上下文。未修改业务 schema、任务接收/采用权限、默认安装或客户项目；未合并 PR、修改目标分支或发布 GitHub Review。产品验证均使用隔离合成项目，没有调用制作或审阅模型。

## 反例、修复与回归

| 问题 | 修复前反例 | 修复位置与提交 | 重新验收入口 |
| --- | --- | --- | --- |
| R1 P1 正文刚采用即被判历史 | 正式 compose.v2 page_copy 接收成功，详情关系仍为 historical | `current_relationship.py`，`30b581c5`：从已提交操作回执定位采用快照，核对所有结果及对应位置、请求和内容依据；缺少可信回执显示 unknown | `test_pr188_completed_content.py`：总览/待关注/详情一致，输入更新、后续换稿、材料用途变化、请求更换、元数据不误判、部分引用残留与缺失回执；候选相邻回归 `test_ui_current_relationship.py` |
| R2 P1 分页文字消失 | v2 390px 按钮 font-size=0，实际 2×44px | `controls.css`、`studio/reading.css`，`927c451f`：保留文字，移除重复伪元素，窄屏允许换行；全量回归补出的画布下移通过标题与状态并排修正 | `test_pr188_controls_browser.py`：两个入口×4 宽度×2 指针模式，文字、44px 目标、溢出、首页/末页禁用态 |
| R3 P2 默认项目接口不兼容 | 默认响应没有 blocking_cards；新增轻量请求回归在修复前收到 400 | `web.py`、`project.js`，`a37e403a`：默认/details=1 完整；light=1 显式轻量；`project_control_light.v1` 能力协商 | `test_ui_journal.py`：真实 HTTP 完整与轻量响应、eligibility 调用计数、混用/重复/非法参数拒绝；轮询脚本验证旧核心回退；PR184 完整旧前端接当前核心的真实浏览器验证见 legacy-ui.json |
| R4 P2 旧异步回调覆盖新工作面 | 旧回调等待期间切到活跃新版本，恢复后把 3 秒间隔覆盖成 15 秒 | `summary-poll.js`、`project.js`，`a37e403a`：有效性贯穿异步回调和控制读取；写入前再次验证 | `test_summary_poll.py` → `w10_poll_lifecycle.mjs`：新版本保留、顶栏数量、提示、事件、间隔、单飞、隐藏/恢复、stop、错误 |
| R5 P2 切换选中态不可见 | 实际点击 reconstruct 后，四个动作背景/边框/文字/阴影相同 | `controls.css`，`927c451f`：共享 pressed 样式，hover、disabled-selected 保留区别 | `test_pr188_controls_browser.py`：实际批量动作点击，14 类保留容器的计算样式，hover 与禁用选中态 |
| R6 P2 逐页稿搜索丢失 | 输入 28 后 URL 无 content_q；跨工作面与刷新丢失 | `routes.js`、`content-sources.js`，本提交：独立 content_q，最大 200 字符，重复/非法参数拒绝；不调用 changed() | `test_pr188_reading_browser.py`：选第2/28页，进入/返回单页，前进/后退/刷新、中文编码、筛选外计数；搜索保留已有页序预览 |
| R7 P2 摘要刷新丢菜单焦点 | 阅读正文/核对来源持有焦点时刷新，菜单关闭且焦点丢失 | `overview.js`，本提交：稳定页面/动作/层/目标身份；同动作恢复，变化回行入口，行消失回标题 | `test_pr188_reading_browser.py`：阅读正文、核对来源、动作变化、行离开筛选；不把焦点交给新语义动作 |
| R8 P3 筛选移序丢焦点 | 28页匹配页码筛选，Alt+ArrowDown 移出结果，焦点未恢复 | `content-sources.js`，本提交：可见则回目标页；不可见则回搜索并播报结果 | `test_pr188_reading_browser.py`：焦点、状态区域、稳定选页集合与页序草稿 |

这些测试先在修复前复现失败，再实施对应修改。分页尺寸以布局尺寸核对；不因浏览器矩形小数精度产生的 43.999969px 改低 44px 标准。计算样式测试关闭动画以读取稳定端点，而非把过渡起点误判为选中态。

## 本地重新验证记录

产品最终指纹为 `a997dbbfdb217b711143a8e4f5bdc3b9ca471d841ecfd61eb912cdd5fb7a95c1`。最终调整仅为 Studio 窄屏页头布局；下面的完整套件记录早于这次 CSS 调整，不能称作最终 HEAD 全量通过。最终 SHA 的完整验证交由 push 与 PR CI 单列记录。

| 检查 | 实际结果与处理 |
| --- | --- |
| 最终定向回归 | 73 passed，见机器记录 `targeted-release`；覆盖 8 项修复、三个画布尺寸与真实轮询焦点 |
| 完整单元 | 3535 passed / 1 failed / 2 skipped。唯一失败为隔离子进程超过原有 180 秒限制；原限制未改，独立复核该文件 8 passed（含子进程 70 项）。首次超时不改写为通过 |
| 完整浏览器 | 597 passed / 5 failed。1 项旧测试仍期待焦点落到 body，已改为验证回到行入口且菜单关闭，独立自然轮询复核通过；1 项窄屏画布 y=602.8px 超过 580px，已修复布局，20 项关联回归通过；另外 3 项为原有 macOS 原生 select 键盘场景，保持失败记录，不删除断言 |
| 完整渲染 | 125 passed / 8 failed / 1 skipped。8 项与既有 PR184 本机字形/表格渲染差异一致；本轮未修改渲染实现，未降低阈值 |
| 最终独立安装 | 71 passed；76 个运行模块来自隔离 site-packages，72 份静态资源逐字节一致；两套 UI 均打包。最终 wheel 另完成 9 项离线检查 |
| 静态与一致性 | Ruff、Token 生成、schema 镜像一致性、JSON 解析、PNG 解码、工作区及完整 PR 差异空白检查通过 |

安装包、源码、完整套件和定向复核分别记账，不累加成一次全绿。最初临时目录触发路径防护、修改资源指纹期间的服务启动错误及中断运行也保留在机器记录中，不计通过。代码索引同步在导入 1772/2512 文件时达到工具超时，未声称索引健康；这不替代或影响代码测试门禁。

## 证据与边界

- [窄屏 v2 分页](evidence/pr188-repairs/pager-v2-390-False.png)、[桌面触屏 Studio 分页](evidence/pr188-repairs/pager-studio-1280-True.png)、[批量动作选中态](evidence/pr188-repairs/pressed-controls.png)。
- [修复后的窄屏画布](evidence/pr188-repairs/reading-390.png)：文字和 44px 命中区保留，画布起点满足原有 580px 上限。
- [旧 UI 兼容证据](evidence/pr188-repairs/legacy-ui.json)：PR184 完整前端连接当前核心，仅使用无参数项目接口，独立审阅入口真实可见；未执行专业审阅。
- 机器可读汇总见 [review-repairs.json](evidence/pr188-repairs/review-repairs.json)。完整回归、安装和当前提交 CI 分别记录，跳过不计通过，重跑不覆盖首次失败记录。
- 原生目录选择/用户取消的既有证据保留在 [NATIVE-ACCEPTANCE.md](NATIVE-ACCEPTANCE.md)，不重复无关人工验收。
- AC14 的真实 Host 专业判断、AC18/#186 的外部报告返修闭环继续 PARTIAL；合成工程验证不等于专业或用户批准。
- 四处文件末尾空行已清理；同时检查工作区差异和 PR184 base 到最终提交的完整差异。干净工作区不能替代 PR diff 检查。

## CI 发现的交接验收时序修正

`bfd76073` 的八组远端单元均为 3536 passed / 2 skipped，两组渲染通过；[PR 浏览器运行](https://github.com/MainQuestAI/Deck-Master/actions/runs/40061529093)为 601 passed / 1 failed，失败是连续任务验收在异步重新挂载后立即读取交接文本框，取得尚未加载的空串。它不是剪贴板写入失败。复制按钮在新说明未加载时仍按预期禁用。

追加一个测试修正提交，产品文件与安装包保持相同指纹。连续任务测试现在通过真实“核实原任务”触发重新挂载，暂缓真实交接响应并验证空文本框和禁用复制，再释放响应；在原有 5 秒等待上限内取得同时包含任务 ID 与 p01 的文本快照，保留原内容和 scope 断言。未增加睡眠、跳过或降低断言。

另用临时 300ms 响应延迟验证拦截器：先取响应再登记请求会造成测试自身竞态，已改为先登记请求并明确等待挂起，再读取和放行真实响应。延迟验证 1 passed；固定测试不包含人为睡眠。连续任务与批量交接回归 6 passed，独立安装运行该连续任务 1 passed；独立安装资源仍与源码逐字节一致。旧 SHA 的远端失败保留，修正提交自身的完整 push/PR 结果只在 PR 描述更新。

最终提交冻结后，只在 PR 描述更新该 SHA 的 push 与 PR CI 结果；本文件不会为了追加 CI 结果再产生一个新验收 SHA。
