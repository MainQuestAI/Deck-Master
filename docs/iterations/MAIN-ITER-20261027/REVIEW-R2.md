# PR #215 复审修复

本次在 `6e9e7d64e7b1963f415c2a4d06de9f2b89881091` 上修复三项 P2，并补充文档工具范围说明。远端 main 在修复开始时仍为固定基线 `62dfcfc5637f0bee2358074c4458047689dd5299`。独立工作树起始干净；原工作树和旧交付 ZIP 保留。此前合同、DOCX、历史原件归档与运行链修改保持，F13 不实施。

| 问题 | 修复与边界 | 提交 |
| --- | --- | --- |
| 双稿恢复文件可下载却不能导入 | 普通请求 2,000,000 字节、单稿 1,998,976 字节不变；恢复文件 4,000,000 字节；仅 import/recovery 两通道请求 4,001,024 字节。project 可选 recovery_limits 协商，缺失按旧限额。仅恢复下载使用紧凑 JSON，按 UTF-8 实际字节核验完整双稿；不截断或移除 pending_save。 | `4126259b` |
| 路由切换后弹窗引用失效编辑器 | 关闭和 Escape 绑定容器 owner；同容器 replacement 更新 owner；全部离开保护通过、路由提交后才释放自己的弹窗。手动关闭保留仍在当前工作面的编辑器。 | `3662f42c` |
| 模块加载失败无法通过普通重试恢复 | 普通读取保留“重试读取”；模块失败提供“重新加载工作台”。检查全部草稿 owner，按捕获的项目、工作面、版本和参数整页重载；导航代次或项目改变使旧入口失效，不重发写请求。 | `2fd3a454` |
| 文档样例 PASS 范围容易误读 | 保留 pass，增加 validation_scope 和 final_candidate_status: not_evaluated；命令输出明确说明中间样例范围。 | `a3d1629a` |

修复前，后端反例为 5 失败／7 通过；旧 wheel 对弹窗后退场景的两个新断言均失败。证据保留在新版交付 evidence/current。初次容量测试的长参数名和断开连接输出、初次画廊选择器未命中实际页面，均保留为诊断记录；后续用有界参数名、声明超限请求头及实际 `.gallery-view` 选择器复核，没有删除行为断言或扩大门禁豁免。

针对性后端／工具回归 52 项通过；浏览器与普通读取恢复 21 项通过。新增用例覆盖两份各 110 万 ASCII 字符、单稿上限、中文／emoji、结构化内容、文件及请求限额前后 1 字节、产品下载后导入、摘要和原请求保留、持续 quota、修改后确认失效、owner 替换、关闭／Escape、历史导航、readonly、404／断网／依赖模块失败、失败入口过期。测试位于既有 main_iteration_browser/recovery 文件，正式安装回归入口已包含它们；最终完整门禁还必须重跑这些断言。

```bash
python -m pytest -q tests/rebuild/test_main_iteration_recovery.py tests/rebuild/test_ui_journal.py tests/rebuild/test_main_iteration_doc_safety.py
python -m pytest -q tests/rebuild/test_main_iteration_browser.py tests/rebuild/test_control_read_recovery_browser.py --require-browser
python -m ruff check src/deck_master tests/rebuild
python -m pytest -q tests/rebuild -m 'not render and not browser'
python -m pytest -q tests/rebuild -m render
python -m pytest -q tests/rebuild -m browser --require-browser
python -m build --no-isolation
python examples/workbench/w12_installed_regressions.py --out <仓库外证据目录>/installed-regressions.json
```

本地 Python 3.12.12、Node 26.12.0、Chromium、LibreOffice、SVG/PDF 工具可用，render doctor 为 ready。Node 22/24 与 Python 3.11/3.12 四组矩阵由新提交 CI 执行。最终 wheel/sdist、仓库外安装、真实渲染、完整 browser、精确 CI 对象、候选清单和 SHA 以新版交付冻结证据为准；本文件中的定向通过不替代它们。

首次完整 browser 为 797 通过／1 失败：旧交接用例立即 abort 请求，却断言仍停在瞬时 loading 状态。原用例在复审前版本重复 10 次通过，当前版本 5 次通过／5 次失败；在断言前强制等待 100 ms 后，两版均进入正确的读取失败状态并触发原断言。测试现按阶段持有真实请求，保留全部 loading、旧组身份、复制禁用、剪贴板、本机标记断言，再用真实服务响应完成请求；修订后两版各 10 次全部通过。该用例未改生产行为、未删除断言或扩大超时，修订后重跑完整门禁。

预算同时计算固定基线和 `6e9e7d64` 到最终候选的运行源码、合同、测试、docs 展开文本、工作树字节及归档成本。12 项历史来源缺口、Frozen A、实际 Host、客户与专业验收仍保留。原旧文档整脚本的基线失败不升级为通过；文档中间样例 PASS 也不代表最终候选验收。PR 保持 Draft，不合并、不发布、不运行客户生产或新付费模型批次。
