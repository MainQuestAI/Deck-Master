# PR130 正式审查修复回执

2026-10-20。产品与回归源码：`50ef4d2e64e2b732bcd7ade7758a9eb86ac2cf6e`，从干净工作树构建。起点 `33b2f5223646e8e0751f26d7653732cd62127fc0`，base PR127 `3217a65630023244eac5a09b3e7570954cce9188`。范围为正式审查五项 P2 与同处 P3；不修改 PR127–129，不合并、不发布，不改真实 HOME。

## 问题与修复

| 项 | 原问题 | 修复与验证目标 |
|---|---|---|
| P2-1 | plan_only 的 argument 预览用默认三层 targets，误判不能派发 | 从真实阶段派发抽出纯 `phase_dispatch_targets`，读取与锁内写门禁共用 layers/page IDs；不扩大范围。用仅 narrative/plan 的请求完成 framing 后读取 M04，并与真实 continue 成功交叉核对，读取前后文件相同。 |
| P2-2 | verified_user 关闭新决定渠道时同时关闭已有合法决定采用 | 渠道阻断只作用于新决定；已存决定仍逐项调用共享真实采用检查。provider 验证的合成 request/decision，在原 adoption HTTP 200 accepted 时 UI 可采用；新决定仍阻断，没有覆盖决定时不可采用。身份由真实 Runtime provider 合同校验，夹具非真实人类。 |
| P2-3 | 成功/失败替换状态区时删除重新评估按钮 | 恢复控件从状态文本容器分离，忙碌禁用、完成采用后隐藏。同一弹窗记录决定→并发 revision→采用冲突→显式重评→新请求成功，旧 UUID/base/payload 保留；原刷新恢复分支保留。 |
| P2-4 | 同一 preview 中迟到资源正文/错误覆盖最新选择并抢焦点 | 独立正文请求序号，成功/失败均检查当前 preview、最新序号、组件存活；重新预览和销毁使旧请求失效。真实 Chromium 保留 M04 回包，让 E04-after 先返回，再释放 M04 成功或失败，正文、状态、焦点保持最新；另测重新预览和离开工作面。 |
| P2-5 | 全页 gaps 污染下一原子，且自身来源错误晚于 mapping_status | 每原子检查完成后计算状态；全页只累积诊断，来源检查缓存保留失败并归属每个引用它的原子。b1损坏/b2完好/b3共享损坏来源的整页与单原子投影逐项相等。 |
| P3 | 无关损坏 Narrative 被计作 Plan 损坏 | 从正式指针与 compose.v2 framing/argument 固定产物合同识别对象类型；未知对象保留 unknown/object 诊断，不伪造 Plan。A无Plan、B Narrative损坏时A仍为absent，坏Ref归narrative。 |

## 复现与定向验证

所有问题先在旧产品上补回归。首次夹具存在 framing variant、M04选择和初始化待办设置错误，原始日志保留，不当作对应产品失败证据；纠正后 P2-1 单独复现为真实 continue 成功而 preview=cannot_dispatch，其余六例分别在预期业务断言失败（含迟到成功/失败）。日志：`formal-review-phase-reproduction.log`、`formal-review-reproduction-valid.log`。

首次产品修复后8项通过。扩展受影响组132项通过、2项新增夹具失败：内容标签页只隐藏而不销毁，不能期待 DOM 消失；改为真正切换工作面后10项新回归全部通过。完整套件再次覆盖最终测试定义，最终统计见下。

## 最终验证与包

完整 unit：**3510 passed、2 skipped、689 deselected / 706.32s**。完整 render：**133 passed、1 skipped、4067 deselected / 234.54s**。三项跳过均为原测试声明的外部 Frozen A 安装资源，未代填验证。源码最终定向 **12 passed / 26.54s**。完整 browser：**555 passed, 3646 deselected in 1864.10s (0:31:04)**；安装恢复完整组：**244 passed in 866.95s (0:14:26)**，两组均无失败或跳过。历史工程/Host/专业效果证据保持各自源码绑定；本轮实际 Host、专业效果审阅、人类认可均 NOT_RUN。

本轮临时安装 `candidate_ready`、`activated=false`，不注册 Host。安装验证使用独立测试副本、`python -I`、无 checkout 产品资源；模块与静态文件字节对照 wheel manifest。隔离测试副本初次缺少 w07 合成辅助脚本，恢复脚本收集失败；补齐测试辅助文件后重跑，保留原失败日志，不修改产品或放宽断言。

上轮 33b2f522 的 push CI39440424298 与 PR CI39440435031 全绿是原提交历史证据；本轮最终 head 必须独立核对。PR130 始终保持原 Draft 和依赖 base。

包 release：`50ef4d2e64e2-ad5e446ec8b1`，版本仍 `1.0.0rc5`。wheel SHA256 `ad5e446ec8b1c843118a0eba752e3478e981dd4a1bea4a3b4efae1ba2f5541eb`；sdist SHA256 `7d95f083d3c7e7290e6b5b6024bffc1e3bc0fbfdf6081ee497f7f0600c80e5e7`。详见 [包与安装审计](evidence/formal-review-package.json)。

安装版使用 pytest9.1.1/Playwright1.64.0，源码环境 Playwright1.63.0；两例 `.check()` 在点击触发目录重绘后等待旧节点，未进入正文乱序断言。测试改为真实 click 后断言新目录中准确 checkbox 已选，未减少业务断言；测试同步提交 `bd6702fcd3117217116c96254ac9d855acfc7995` 无产品字节变化。安装版最终 **12 passed / 24.88s**，离线安装脚本 **9 checks verified**。原失败日志保留。

render 初次运行未传 wheelhouse，隔离 pip 的 DNS 失败导致1 failed/1 error；其余131 passed、1 skipped。以预取声明依赖、`PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/webui-browser-wheelhouse` 重跑完整组后得到上述133 passed，不改变产品或测试。

安装恢复首轮收集失败补齐辅助脚本后，又发现 Playwright1.64 的默认浏览器 revision1248 未映射（原1.63环境为1243）。默认启动用例实际未执行；终止该无效环境运行，保留日志，补同一系统 Chromium 的临时映射后重新完整运行。显式 executable 的12项安装定向与离线脚本不受该路径问题影响。

## 可复核命令与执行边界

源码组使用 `/tmp/webui-unit-venv/bin/python`（Python3.12.14，Node24.19.0）；渲染 PATH 增加已安装的 rsvg-convert，浏览器统一系统 Chromium。其它 Python/Node 矩阵由推送后的 required CI 确认。

```bash
python -B -m pytest -q tests/rebuild/test_webui_formal_review.py \
  tests/rebuild/test_webui_content_insight_browser.py::test_adoption_concurrent_revision_keeps_payload_until_explicit_new_request --require-browser
python -B -m pytest -q tests/rebuild -m 'not render and not browser'
python -B -m pytest -q -rs tests/rebuild -m render
python -B -m pytest -q tests/rebuild -m browser --require-browser
python tools/build_release.py --out /tmp/webui-release-formal-review
```

测试进程统一为隔离 pip 提供 `PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/webui-browser-wheelhouse`；浏览器为 `PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser`。wheelhouse 只含正常下载的声明依赖，没有伪造包或绕过门禁。

安装组通过 `deck_master.install.install_candidate` 安装到新临时 prefix，未 activate。复制测试和 `examples/workbench` 辅助脚本到 `/tmp/webui-formal-installed-check`，不复制产品 src。安装解释器以 `-I` 运行同一12项定向用例、`w12_offline_browser.py --require-installed --font 'DejaVu Sans'` 和完整 `w12_installed_regressions.py`。模块/静态文件必须解析为该 release 的 site-packages；安装恢复脚本还逐一审计已加载产品模块路径。

完整组启动时的产品/测试提交为50ef4d2e；bd6702fc只同步重绘后的测试点击，产品字节未变，最终源码/安装定向12项使用bd6702fc测试定义。组间重叠不相加。新head远端CI使用最终提交完整测试树。

[原工作树哈希核对](evidence/formal-review-original-worktree.json)六项全部未变。报告、日志和PR正文不含私人对话链接、用户消息标识或授权原文。

## 最终结果与证据

| 执行组 | 结果 | 日志 |
|---|---|---|
| unit | 3510 passed, 2 skipped, 689 deselected in 706.32s (0:11:46) | [日志](evidence/formal-review-full-unit.log) |
| render | 133 passed, 1 skipped, 4067 deselected, 22 warnings in 234.54s (0:03:54) | [日志](evidence/formal-review-full-render-final.log) |
| browser | 555 passed, 3646 deselected in 1864.10s (0:31:04) | [日志](evidence/formal-review-full-browser.log) |
| source_targeted | 12 passed in 26.54s | [日志](evidence/formal-review-focused-source-final.log) |
| installed_targeted | 12 passed in 24.88s | [日志](evidence/formal-review-installed-focused-final.log) |
| installed_recovery | 244 passed in 866.95s (0:14:26) | [日志](evidence/formal-review-installed-recovery-verified.log) |

安装离线脚本9项通过；全仓Ruff和最终diff-check通过。所有初始失败、修复与最终日志按[清单](evidence/formal-review-log-manifest.json)保留，入库仅清除行尾空格，原字节SHA同时记录。新head CI在推送后由原PR正文和最终回执给出准确URL/状态，不用重复纯状态提交制造新的构包SHA。
