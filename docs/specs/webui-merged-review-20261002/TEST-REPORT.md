# 本轮优化工程验收

基线 `bed476090e2a49b4c679906da2ce762753789d96`；功能候选 `6685553c13b643d609b35b34aa1dfa19558db7e2`。F01 → F04 分别提交 [PR92](https://github.com/MainQuestAI/Deck-Master/pull/92)、[PR93](https://github.com/MainQuestAI/Deck-Master/pull/93)、[PR94](https://github.com/MainQuestAI/Deck-Master/pull/94)、[PR95](https://github.com/MainQuestAI/Deck-Master/pull/95)。后续包以此前包为 base，尚未合并。

## 工程结果

| 验证 | 结果与边界 |
|---|---|
| 完整核心 | 1068 项通过；最终核心/编译器摘要与该测试版本一致 |
| 必跑浏览器 | 最终 wheel：39 项通过，无 skip；覆盖 CSP、已读重开/目标一致、三尺寸、样例失效、局部键盘、缺栏焦点 |
| 真实渲染 | 33 项通过；24 标准图标 + 3 笔触变体在 Python/Node 两出口各 27 页实际 PPT，源声明校验原生 DrawingML |
| wheel/sdist/隔离安装 | 两包资源一致、sdist 重建一致；最终包隔离验收 24 步通过；三用途导出、恢复及回退在隔离合成工程验证 |
| 真实 30 页副本 | 安装版整稿编译、实际渲染及 30 页原生回读 report=pass；3 个图标候选实际检查 ready/native pass；Page/原图/SVG 未改变 |
| 真实浏览器 | 副本在 1280×800、1440×900、390×844 无整页溢出；实际候选 PPT 局部对照与键盘保持对象，通过。截图不记为视觉认可 |
| 300×5×3 摘要 | 默认独立服务，100 次 + 5 次暖身 + 实际后台领取/取消；p95 121.63 ms，250 ms 门通过 |
| 六次暖首屏 | 最终 wheel 全部通过，最大 0.6303 秒；两桌面尺寸、6 张可见图卡、图像池边界通过 |
| 20 分钟压力 | 最终包完成 1200 秒活跃采样，30+30 样本，内存中位数增长 1.63%，6/2/60/4 通过；记录一次合盖休眠导致的网络中断，整体未通过，连续门槛保持 open |
| 当前功能 head CI | 6685553 七种检查均成功；Python 3.11/3.12 × Node 22/24、实际渲染、必跑浏览器/安装、汇总 |

附加同进程嵌入 p95 344.63 / 271.83 ms 未通过，失败保留，不扩展独立服务的性能结论。旧界面长跑通过（中位数增长 1.80%）；最终界面变更后重新跑，不能用旧跑替代。

最终包两次长跑均记录了 `ERR_NETWORK_IO_SUSPENDED`，整体失败，不能以局部指标代替通过。后一次虽启用进程期防空闲休眠，系统仍于 00:04:34 因 Clamshell Sleep 合盖休眠；该机制不阻止合盖休眠，也未更改系统长期设置。连续压力验收需要在保持电脑唤醒的条件下补跑。

## 安装包与版本对应

本轮测试使用独立安装环境，功能源版本为 `6685553c13b643d609b35b34aa1dfa19558db7e2`，构建时工作区干净。

- wheel SHA-256：`69175030399cd9ba683b307de0c56c71ee4d19b6026c7c45c074bdf4c62f2690`
- sdist SHA-256：`f396c9424f9b1b5a20e9a7f9b2dab6a660f64f2b7c41c1b942ed30d0dac18d05`
- wheel 包含 191 个运行文件、46 个 v2 静态资源；sdist 解包及重建 wheel 的运行文件逐项一致。
- 完整核心和渲染回归基于 `4fb5002`；后续运行文件只变动 `icon-workbench.js`，已在最终 wheel 重跑全部 39 项浏览器与 24 步安装验收。最终附加焦点切换断言单独通过。
- Python/Node 图标目录的各 27 页证据来自 F01 轮次；最终完整渲染回归覆盖编译器当前实现，不将早期目录记录描述为最终 head 新跑。

## 缺陷关闭依据

R01：笔触继承/覆盖与两出口原生回读。R02：新 check_id 优先、服务中断、显式重试、缺失报告降级、旧报告保留。R03：拒绝有效透明/无描画、退化线段、共线/重走/反向抵消填充；精确交点避免浮点空隙，保留横竖描边与空辅助树。R04：局部方向键、正常尺寸/缩放、按列恢复焦点，轮询仅显示数据变化时重绘。R05：候选 ID+图标序号稳定恢复，全部失效不改变 reuse 意图，损伤依赖明确不可读。R06：共享个人已读投影、结果变化重新待读、CAS/清理备份/空计划后新增冲突、损伤记录隔离与保留。R07：大纲 CSS 类、CSP 不放宽、浏览器捕获错误。

外部报告中的横竖线误拒未复现（包围框含描边边距），独立横竖线回归仍已补齐。只读列表的 ETag 冲突是固定阅读快照保护，提供重读入口；空清理计划后新增已读的整批冲突已有回归。

原审查文件保留为基线事实。native review 共三轮修复，并参考两份外部报告；最后数值缺陷已以回归修复验证。最后修复轮未生成新的独立收敛证书，review 日志保持 converged=false，不宣称额外审计或用户视觉通过。

## 保留事项与原始证据

- 连续压力测试保持 open：最终两次均有系统休眠引起的请求中断，已保留 HAR、错误与系统事件；不删除错误或下调门槛。
- 原生目录选择两次本机实测超时；桌面控制接口补验也超时，真实成功/取消未核实。超时、失败、并发、手动路径恢复有核心与浏览器验证。
- 第 6/29 页候选采用或保留、30 秒真人理解观察、图标视觉认可等待真实反馈。
- 真实副本审阅包/内部工程包已导出；delivery 按未完成专业审阅门槛拒绝。工程通过不改变原验收稿的交付结论。
- 两个原工程 revision 与 Document 摘要保持不变；不切换 HOME 安装，不提交客户图稿、HAR、原始操作和本机路径。

私密证据留在仓库外：unit-source-exact.log、render-source-exact.log、f01-python/checks.json、f01-node/checks.json、final-build-focus/dist/release.json、final-build-focus/sdist-rebuild-verification.json、installed-verification-resumed/checks.json、real-assembly-installed-final.json、real-checks-installed.json、real-browser-installed-ready/checks.json、latency-focus/measurements.json、warm-focus/checks.json、pressure-final-20min/checks.json、pressure-awake-20min/checks.json、preservation-proof.json、pressure-awake-system-sleep.log、ci-focus.json。初次 setup/超时/探针失败保留，不计为通过。

去除客户内容和本机路径的结构化结果及私密文件摘要见 [工程证据索引](evidence/implementation-checks.json)。交付提交仅补充测试断言和证据，运行源码保持上述功能版本；最终提交的 CI 以 [PR95 检查](https://github.com/MainQuestAI/Deck-Master/pull/95/checks) 为准。
