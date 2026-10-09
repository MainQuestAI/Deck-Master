# PR103 复审 P2：明确拒绝的上传可重新开始

日期：2026-10-07。起点：`00be2428ec8f7f235b3d8096e0a232653ad1b6dd`；用户已授权将本轮修复提交并推送至 PR103 原分支，发布状态以远端记录为准。仅处理复审保留的截图上传错误分类，不重新打开材料编辑、候选卡片或阶段组织。

## 修复结论

服务端返回明确业务拒绝且 `operation_state=not_committed` 后，原上传进入持久的 `rejected` 状态，不再与结果未知混同。仅消费该上传端点已有的 422 `visual_reference_invalid`，以及 409 `visual_reference_conflict`／`base_revision` 合同；如回执提供 operation ID，必须与原请求一致。

- 图片拒绝：显示“结束失败上传，重新选图”。用户明确结束失败请求后，文件选择恢复可用并获得焦点；下一次上传创建新 UUID。
- 基准冲突：显示“读取当前版本并重新上传”。先读取并核对本项目当前版本，再进入该版本让用户重选文件。旧请求 UUID 的基准不被改写；不会自动上传。此读取出口不受历史只读限制，真正上传仍服从当前版本写权限。
- 当前版本读取失败、组件已销毁或项目身份不匹配：保留失败记录，不擅自清除或发送。
- 网络失败、5xx、普通 4xx、不含确认未提交语义的业务错误、错误 operation ID、不可读回包和成功回执身份不匹配：保留原 UUID、SHA、基准和摘要，继续核实。真正的 `operation_not_found` 仍只开放同文件、同 UUID 的精确重放。

没有新增业务端点、后端状态或合同，也没有清理项目对象。新状态仅是既有本机上传记录的可选元数据；旧 pending 记录仍按未知结果处理。

## 反例与回归

在修复前的正式 loopback 核心服务和 Chromium 上，坏图、超过 3200 万像素的有效 PNG、过期基准三个反例均失败：服务端拒绝且项目不变，但界面没有结束失败请求的出口。记录见本机 `output/playwright/pr103-upload-rejection-20261007/red-core.xml`。此前 `red.xml` 是 macOS 沙箱阻止浏览器启动的环境失败，不当作产品反例。

新增 13 个参数化浏览器 case，覆盖三种真实拒绝及刷新、新文件／新 UUID／当前基准、读取当前版本失败；九种非确定拒绝回包；提交已完成但回包丢失后刷新并核实。原重放回归仍检查不同文件拒绝发送、原文件完整 URL／UUID 一致及唯一参考对象。

最终运行资源 BUILD_ID：`76d5ef7b75137c2f2e4f6b860ea78239bff6da253362aaf442b4e86a50596950`。

| 本轮门禁 | 实际结果 | 本机证据 |
|---|---|---|
| 联合回归及整条截图风格 Chromium | 41 passed，0 skipped | `final-browser.xml`，84.66 秒 |
| 截图参考核心、HTTP 及操作恢复 | 45 passed，0 skipped | `final-core-v2.xml`，4.61 秒 |
| 静态检查 | Ruff、修改的 JS 语法与 diff whitespace 检查通过 | 本机命令结果 |

命令：

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests/rebuild/test_pr103_repair_browser.py tests/rebuild/test_visual_styles_browser.py --require-browser
PYTHONPATH=src .venv/bin/python -m pytest -q tests/rebuild/test_visual_styles.py tests/rebuild/test_visual_styles_web.py tests/rebuild/test_workbench_operations.py
```

逐文件 SHA-256：

- `visual-style.js`：`1171748d192af93230de3ae4184eeaca150887ef6b1c52d5b7b91a32e7f7c0c4`
- `test_pr103_repair_browser.py`：`9120cc47619513039f9d78f36f7bb6355d156a733bb06ed900d91716db9936c7`

`final/` 截图检查了明确拒绝提示与恢复出口。首轮修复暴露刷新后历史只读使基准恢复按钮禁用，已定点修复；其失败结果保留在 `green-targeted.xml`。丢回包刷新后的测试显式返回当前版本，再核实和保存，保留既有历史只读规则。最终通过数量不由中间轮拼接。

所有项目和图片为隔离合成数据，无模型调用、客户工程写入或 HOME 安装。测试服务和浏览器由 fixture 正常停止，截图和 XML 作为本机证据保留，不纳入产品资源。

## 远端与验收边界

本轮修复前核实 PR103 仍为 Open／Draft，远端 HEAD `00be242` 的 push／PR 检查均成功，包含必需浏览器及安装门禁。该条件已在旧 HEAD 满足，不再描述为“尚未执行”。发布后须单独核对新 HEAD 的 CI，不能用旧 HEAD 的结果为新增修复背书。

本轮完成功能恢复和正式入口的行为验证；没有重新执行全仓单元／渲染／安装矩阵，也没有新增全站视觉验收或真实 Host 制作。原 AC03 的分页故障组合、用户视觉和连续任务认可、真实交付及 HOME 激活仍单列。未合并、未提交 GitHub Review，不宣称整体产品整改正式通过。
