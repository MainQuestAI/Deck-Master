# RC3-02 独立 code review：第五轮 65d8203（examples-only）

**结论：PASS（限定两处示例与其实际文件闭环修复）。** 新 fixture 声明真实 Page notes，经正常 SvgInput→native compile→完整 notes 回读；公开包保留完整合法讲稿并净化 canary，内部工程包保留原件。旧的私密 notes 正文反例依然拒绝，没有弱化生产 validator、privacy 或准入规则。本报告没有把旧 53f4 CI/安装示例失败改写为通过，也没有替 Owner 签当前完整 installed browser/recovery 或远程 CI。

Reviewer：`/root/rc3_02_code_review`，未参与实现。日期：2026-10-14 UTC。

## 固定对象与实际入口

- HEAD：`65d8203ec099b0460dbf031b24cf2ea5a02fd0f2`；tree：`e4e94f7acc9d9156beeb77fa8ede06cb0a954480`。
- 快照：`/workspace/work/rc3/reviews/rc3-02-code-snapshot-65d82`；实际 Python：`/workspace/work/rc3/reviews/env-02-snapshot-65d82/bin/python -I -B`。按 Root 的 bootstrap/module 校验完成后才开始执行，source `work/rc3/env.sh` 后始终使用绝对 Python。
- delta 相对 `53f4ab335d4bacb0862d810cf8acf55eeba7e744` 仅 `examples/workbench/w11_browser.py`、`w12_offline_browser.py`，59 additions/9 deletions。完整读取两处 delta 及示例上下文。
- 独占 scratch：`/workspace/work/rc3/reviews/rc3-02-code-round5-65d82-scratch`。独立 wrapper 仅加载固定快照的 examples/workbench；断言实际 example 与 rebuilt-core module 都来自该快照，不借 Owner/live/旧 namespace 源码。此入口是明确的隔离 editable core，不冒称我的执行是 wheel 安装入口。
- 未安装依赖、共享 bootstrap、改产品/Owner raw/docs/冻结原件，未 push/commit/merge。`git diff --check` 通过，source clean。

## 代码判断

旧 fixture 在 Page/编译输入没有 notes 时，把 private canary 写入实际 notes 正文；新的完整回读正确报告 speaker_notes_mismatch。修复不剥离或绕过这个检查：它为 Page 声明 `PUBLIC_NOTES` 并传给真实 SvgInput，将正例中的 canary 保留在 author 与 notes shape 的隐藏 descr，同时独立保存旧正文 tamper 文件并明确断言 readback fail/speaker_notes_mismatch。

fixture 的当前 outputs 添加实际 notes digest 和 rc3.v1 floor，避免仅有 SVG 依赖却承诺新 notes 文件消费。已有可见正文/SVG、六维 synthetic host_self Review、user_stop 与 UI 请求策略没有被修改。记录继续明示 synthetic、model_calls=0、无真实专业批准；它是人工 seed 的浏览器/文件工程 fixture，不声称正常 Host 制作或协作批准 E2E。

`verify_download_notes` 读取 manifest 指定 revision 的 Page 集，与实际 PPTX notes/稳定 page_id 全文逐项比较。公开 ZIP 保持 canary 净化；engineering 分支核对原始 bytes，并分别确认 author 与 notes 部件仍含 canary。历史 precompile review 没有 PPTX 时据实保留该状态。该 helper 用于示例当前三类默认容器与历史 review；没有更改 Runtime sanitizer 默认值或 UI notes_policy，不能把它当成任何任意导出选项的通用验证器。

## 我的实际独立探针

执行 `probe_fixture_exports.py`，调用固定新例子的 fixture（DejaVu Sans、真实 native compile/render/readback），然后正式 `exports.create/download`，没有 mock compiler/renderer/pending 或直接伪造最终导出文件。

| 正反对照 | 实际结果 |
|---|---|
| Page PUBLIC_NOTES→SvgInput→实际 native PPTX/readback | **PASS**；完整 notes、连续空行及末段换行与 Page 相等，stable ID=p1 |
| 旧 private notes 正文副本 | **正确 FAIL**；保留实际 speaker_notes_mismatch 报告；再次向公共 sanitizer 提交也以 export_privacy_blocked 拒绝 |
| 正式 review 下载 ZIP | **PASS**；manifest 全部 file hash/size 正确，公开 PPTX 全文 notes/ID 相符，所有部件无 PRIVATE-CANARY |
| 正式 delivery 下载 ZIP | **PASS（合成准入/文件工程 fixture）**；同上，不升级成真实专业交付认可 |
| 正式 engineering 下载 ZIP | **PASS**；归档 PPTX 与 Store 原件逐字节相等，author 与 notes XML 两处 canary 都存在，完整合法 notes/ID 保留 |
| 三类同 request/revision 精确 replay | **PASS**；manifest 不变，源 current 与原件 bytes 不变 |
| mode=none、无新 speech_policy 的既有 notes | **PASS**；公开 manifest 实际为 speech_mode=none/source=preserve_existing/selection=pptx_notes，原 notes 完整保留，没有另凑讲稿或删除原注 |
| 显式 pure_reading 对照 | **PASS**；实际导出副本 notes 为空、stable ID=p1，内部 Page notes 与原 PPTX bytes 保留 |
| 历史 precompile review | **PASS**；归档确实没有 deck.pptx，helper 没有声称此前已编译，current 不回退 |

原始输出与脚本：`probe_fixture_exports.py`、`probe_fixture_exports-final.log`，三类正式下载 ZIP 保存为 scratch 的 `actual-review.zip`、`actual-delivery.zip`、`actual-engineering.zip`。这些是我的执行，未转录 Owner/另一 reviewer 的 installed/w12 结果。

最初 wrapper 使用了错误的响应键 filename，Runtime 返回的正确键是 archive，因 reviewer harness KeyError 中止；`probe_fixture_exports.log` 原件保留。更正的仅为隔离 wrapper 与新输出目录，产品始终是同一个固定 65d82；不把此 harness 错误记作产品失败，也不隐藏历史记录。

## 旧失败、零差异复用与未运行层

Root 提供的旧 CI run `38642260224` 包含 403 browser PASS 与 wheel build/install 成功，但旧 w11 fixture 因 actual speaker_notes_mismatch 阻断后续 installed offline/recovery。原 report 和 `/workspace/work/rc3/reviews/rc3-02-installed-fixture-53f4-reproduction` 保留，不由本轮改写。本 reviewer 没有重跑旧远程 CI，也没有把“此前 403 browser 通过”当成旧 offline/recovery 通过。

实际 `git diff --quiet` 证明：`src/`、`skills/`、`pyproject.toml` 与已审 ca035 为零差异；同这些目录加 `tests/` 与已审 bc0b3 为零差异。因此精确复用 Round 3 产品工程 code review 与 Round 4 CI 分类审查的原限定结论，不重跑全套旧产品审查，不宣称新远程七项 CI 已绿。

Root 告知当前 fixed wheel 的 installed 入口与 wheel SHA，Owner/另一独立 reviewer 正执行安装后的 w12 和 recovery；这些属于其实际运行记录，不计为我的 PASS。本轮没有执行浏览器 UI、完整 offline installed assets、恢复 UI 或目标桌面保存重开。真实模型、Owner/听众、人类 professional evidence 与完整 RC3/最终 AC 继续各自 NOT_RUN 或原独立状态。

没有发现这两处示例 delta 引入新的实质问题；可继续既定完整 installed/browser/recovery/CI 流程，并以最终固定提交的实际结果签各 gate。
