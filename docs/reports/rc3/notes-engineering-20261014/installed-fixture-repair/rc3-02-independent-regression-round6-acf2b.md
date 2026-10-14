# RC3-02 独立 limited-impact regression review — round 6

**结论：PASS（固定 acf2b 的单个浏览器用例等待条件修复范围）。** 本人实际运行原三个 viewport 用例，均通过；独立受控真实 SVG 请求捕获 ready 但未 fit 的溢出阶段，以及真实 fit 后合格的尺寸。新增等待针对现有控制器完成状态，没有改产品、fixture、几何阈值或增加 sleep。旧 65d82 整套 recovery 的 FAIL 与本人的 harness 错误原件均保留，不改写为整套 PASS。

Reviewer：`/root/rc3_02_regression_reviewer`，未参与实现。日期：2026-10-14 UTC。

## 固定代码与真实安装来源

- HEAD `acf2b2edd4a88f74e8b671a18e32eb74b780eb84`，tree `0d3ce4982e24a081cbf964259ea85891cd713aed`，snapshot `/workspace/work/rc3/reviews/rc3-02-code-snapshot-acf2b`。
- 相对 65d82 全部 delta 只有 `tests/rebuild/test_workbench_usability_browser.py` +3 行；mobile 量 bounding box 前新增现有 `data-reading-mode=fit` 的 Playwright expect 和两行说明。三个参数、`box.y + box.height < height`、图层/页面 revision/横向无溢出断言均不变。`src`、`skills`、`examples`、`pyproject.toml`、icon/workbench fixture 与 conftest 零 delta。实际固定测试文件 SHA256 `59ad0bb7ac7bef66339a27c490ad15114af47f72846cda4cf52f42aae7bc2420`。
- 真实执行：`/workspace/work/rc3/reviews/rc3-02-installed-fixture-65d82-validation/venv/bin/python -I -B`；runtime 是 **65d82 wheel 安装**，不是把它称为 acf2b 新 wheel。wheel SHA256 `b13629f0f67c17883bcc0a610b7fc2fd0951a1c714b4b3b3f90b616b664265a0`，本人重新核实。246 个 package members 的 acf2b source、原 wheel、site-packages 安装逐字相同；46/47 个实际加载核心 module origins 全在安装 prefix。
- pytest 的测试与 helper 仅取固定 acf2b。runtime 在测试加载前从 site-packages 导入；独占 wrapper 在 collection 后移除 conftest 加入的 snapshot/src 路径，实际执行时其不在 sys.path，全部核心 origins 再核实，无 product source borrowing。未安装或改依赖、共享 env/cache、source、原件、assert/fixture/runtime。
- 独占 wrapper/raw/output：`/workspace/work/rc3/reviews/rc3-02-regression-round6-acf2b-scratch/`；短 TMP `/workspace/work/rc3/t6rr/`；独占 XDG 路径。真实 Chromium `151.0.7922.173`，正式 WorkbenchServer。结束时 snapshot head/tree 与 tracked 文件不变，`git status --short` 为空。没有 push/merge。

## 本人实际验证与原始结果

| 固定正式用例 / 独立对照 | 本人实际结果 |
|---|---|
| 原 node `test_reading_prioritizes_artwork_and_preserves_fixed_layers[390-844]` | PASS。实际执行新增 fit 等待、原 strict bottom 断言、制作图层切换、page-copy 可见、固定 revision 与横向无溢出断言。用例完成后已切 content 层，post-call 图像 viewport 不存在是正常路径；未编造其 final geometry。 |
| 同一原 node `[1280-800]` | PASS，原 chain 与横向无溢出检查不变。post-call 实际 fit/ready，bottom `779.990966796875 < 800`。 |
| 同一原 node `[1440-900]` | PASS，原 chain 与横向无溢出检查不变。post-call 实际 fit/ready，bottom `879.7855834960938 < 900`。 |
| 独立 held 实际 SVG / fit 负对照 | SVG 请求被 held 时实际 image=loading、无 canvas、mode=null，字体 loaded。`expect(data-reading-mode=fit, timeout=200)` 真实超时，作为预期负对照保存在 JSON；不是 sleep，也没有改正式测试 timeout。placeholder 可见不代表 fit 已完成。 |
| 同一真实请求 continue 后的 MutationObserver 轨迹 | 未替换响应、未改 RAF/时钟/CSS/viewport。actual image=ready/canvas=true 且 mode=null：height `209`、bottom `848.375 >= 844`、fonts loaded。`2.4ms` 后现有控制器实际 mode=fit，height `184.625`、bottom `824 < 844`。两阶段是真实 DOM 观察，不借 Owner 轨迹。 |
| 实际 SVG 文件/HTTP 一致性 | routed browser 请求原样 `continue_()`，200、Content-Length=628，实际图像解码/canvas 创建成立。独立真实 HTTP GET 同一个不可变 URL 得 628 bytes，与项目 SVG 文件及 URL SHA256 `557276c02680634ab6c0a8169e397fc70e792e5308a6e41b66ff184340d003ae` 相同。浏览器 Response.body 取证接口返回 0 bytes，未冒称直接读取该浏览器响应正文；见下方错误边界。 |

现有 runtime `page-reading.js` 的 redraw 先写实际 viewport/holder/canvas 尺寸，再发布 `data-reading-mode`；图片节点出现通过 MutationObserver 调度 requestAnimationFrame。新增 expect 等待这个实际完成信号，随后保留原严格几何判断。独立轨迹证实 ready 与 fit 存在不同阶段，且既有字体已 loaded；没有靠阈值放宽、固定延时、伪造 pending 或 skip 得到通过。

本人执行分为三次，原件全部保留：

1. `installed_fit_probe.py` / `installed-fit-probe.log` / `execution.json`：exit 3 **INTERNALERROR**。本人 post-call 观察 hook 对 mobile 切 content 后已不存在的 image viewport 读取 geometry，未记录可认定的正式 PASS。未将该次标绿。
2. `installed_fit_probe_r2.py` / `installed-fit-probe-r2.log` / `run2/execution.json`：**3 正式用例 PASS，1 独立 probe FAIL**，6.81s；新增 null guard 仅修本人观察 hook。独立 probe 已达到真实 fit 且尺寸合格，但额外 browser Response.body 与源 bytes 的取证断言失败：接口返回 `b''`。该失败原件保留；不能仅凭空 body 的取证接口推定未解码图像。run2 JSON SHA256 `ed952ada08dbd20b23074152475c74add610e12e5233bbf1e0c6d7e73c875161`。
3. `installed_fit_probe_r3.py` / `installed-fit-probe-r3.log` / `run3/execution.json`：仅重跑独立 probe，**1 PASS / 3 deselected**，1.98s。使用独立真实 HTTP GET 审计同一不可变 URL，仍保留 browser body API 空值、真实 DOM 与 headers。没有假称解决该接口空 body 的原因，也没有把这个独立 HTTP body 称为直接取得浏览器 body。run3 execution SHA256 `a6b91a653e3ec94d8335238baff672ec551f9c5bdd5e2242969c49ab7caa33ae`；完整 `run3/controlled-lifecycle.json` SHA256 **`a5f52f5d3a977f7a55051074e5cff7f2058e2c211f6f9e62ac33146044afb258`**，含负对照失败、actual loading/ready/fit、真实请求/字节 hash、原始 MutationObserver 记录及截图。

以上三次是本人 scratch harness 取证修正，不改固定测试或产品。正式三个用例的 PASS 来自第 2 次各 node 原报告；独立控制对照的 PASS 来自第 3 次。未将三次拼成一次全绿 suite。

## 旧失败、复用与未验范围

Root/Owner 的原 65d82 完整 installed recovery 保持 **238 PASS / 1 FAIL，797.48s**，sole mobile viewport bottom 原观察 `848.8`。本人读取核对其原 `installed-recovery-r2.log/json`，不是自跑那 239 项；log SHA256 `ff8c97a0ccae850696bc45f5f1cbeb86d5c8cba246dddc641e66069f04c4e1cf`，JSON `f196e461ddbb5e0b45e9c403a191bb217e181e77e892e925d2805d639d04ad9b`。本轮不把旧完整失败重写 PASS，也不把其余 238 项写成本人重新执行。新最终 required CI/full installed recovery 由 Root 在最终 head 完整核验。

R5 两个 examples 的本人安装/native/export 正反 PASS 仍保留在其原固定 65d82 报告，不混成新 acf2b 原件。runtime/skills/examples 精确零 delta，按影响复用本人既有 notes、权限、旧 A 成本与实际文件边界证据；本轮没有重新跑这些生产轨迹。Owner 的独立三 viewport/controlled 结果不借为本人执行。

本轮未跑 broad/full 239、当前全部远端 CI、完整 RC3 综合链。真人 Owner/听众、目标桌面 notes/保存重开、完整彩排、完整 RC3/最终发布仍 **NOT_RUN**。PASS 仅支持固定 acf2b 这三行等待条件的工程修复；合并资格与最终 current/docs/全部 CI 由 Root 另核。
