# RC3-02 独立 limited-impact regression review — round 5

**结论：PASS（固定 65d82 的两个 example 修复范围）。** 本人使用真实 wheel 安装独立执行了修改后的 fixture、实际 native compile/render/readback、正式 review/delivery/engineering export/download 及正反字节检查。notes 正文错配仍失败，公开与工程包边界成立；没有发现本轮新缺陷。此结论不等于远端当前全部 CI、完整 installed UI/recovery、真人或完整 RC3 已验。

Reviewer：`/root/rc3_02_regression_reviewer`，未参与实现。日期：2026-10-14 UTC。

## 固定代码、安装与执行归属

- HEAD `65d8203ec099b0460dbf031b24cf2ea5a02fd0f2`，tree `e4e94f7acc9d9156beeb77fa8ede06cb0a954480`，parent `53f4ab335d4bacb0862d810cf8acf55eeba7e744`。
- Snapshot `/workspace/work/rc3/reviews/rc3-02-code-snapshot-65d82`；完整读取两个 example delta 和其 fixture/下载验证路径。相对 parent：仅 `w11_browser.py/w12_offline_browser.py`，59+/9-；`src`、`skills`、`tests`、`pyproject.toml` 零 delta。相对本人 ca035：产品 `src`、`skills`、`pyproject.toml` 也零 delta。
- 真正执行使用 `/workspace/work/rc3/reviews/rc3-02-installed-fixture-65d82-validation/venv/bin/python -I -B`，module 来自该 venv 的 `lib/python3.12/site-packages/deck_master/__init__.py`。wheel sha256 **`b13629f0f67c17883bcc0a610b7fc2fd0951a1c714b4b3b3f90b616b664265a0`**，本人重新计算吻合。
- 本人只从固定 snapshot 显式加载修改后的 example fixture；没有向 sys.path 添加 product src。实际加载的 **45 个核心 module origins** 均在安装 prefix，**246 个 installed package members** 逐字节与真实 wheel 对齐；不是 editable/source env 冒充 installed。
- 本人独占 wrapper、输出与 raw：`/workspace/work/rc3/reviews/rc3-02-regression-round5-65d82-scratch/`。没有调用 Owner 的运行 wrapper/输出目录、安装依赖、修改共享 env/source/原件或 push/merge。结束时 snapshot head/tree 与 tracked source 不变；同时观察到 untracked `output/playwright/pr103-complete/` 浏览器测试产物（22:24–22:26 UTC），未由本人的 native/export wrapper 运行产生，本人未删改，已告 Root；不宣称此时全工作树 clean。

## 本人实际正反结果

入口为独占 `installed_native_export_probe.py`，实际结果与完整 module/包/文件 hash 证据在 `installed-native-export-probe.log/json`，实际文件在 `installed-native-run/`。JSON sha256 `bacc934af12c14bdb30d315de2489409c91876e388aeae8d02f5da4f5e8efda2`。

| 实际路径 / 条件 | 本轮实际观察 |
|---|---|
| 源 Page notes → SvgInput → native compile/manifest → readback | Page 的完整合法 notes 与 compile-input speaker_notes、notes_sha256、实际 PPTX body 逐字一致，包含连续空行与末段换行；正常 readback PASS。稳定 ID 为 p1。 |
| 当前 output 与 writer | 输出存在准确 `page_notes:p1` 内容依赖/hash，`output_matches_current_svg=True`，current floor 为 rc3.v1；没有仅写 Page、绕过 notes 消费或靠空 XML。 |
| 元数据 canary | 原 PPTX author 与 notes hidden metadata 保留 `/Users/synthetic/PRIVATE-CANARY`，实际 body 为合法源 notes。对正文/hidden metadata 分开读取，未把 canary 从原件全部删掉。 |
| 原错配负例 | `notes-body-mismatch-canary.pptx` 实际 body 为 private canary。本人重新实际 readback 为 FAIL，具体 speaker_notes_mismatch；正原件字节不改。 |
| formal review 与 delivery export → actual ZIP/PPTX download | 两种用途下载的完整 Page notes/stable ID 相同；所有 manifest file hash 验证，整包非 PPTX 项及嵌套 PPTX 每个 member 均无 private canary；不含 project/内部工程目录。 |
| none 与明确 pure-reading 对照 | 默认 manifest speech_mode=none，仍完整保留既有 Page notes。明确 pure_reading 最终 PPTX notes 为空，ID 保持 p1；内部 Page 与原 PPTX 的完整 notes/bytes 不改。 |
| formal engineering export → actual ZIP download | 从 project/ 下取实际原件 Ref，PPTX bytes 与原件完全相同，author/notes metadata canary 都仍存在；body notes/stable ID 仍完整，未把内部恢复包误当公开净化副本。 |
| 隔离负例项目的正式公共 export | 在本人独占复制项目中显式 seed 上述坏正文实际文件，保留原声明依赖/合成 gate records 后调用正式 exports.create(review)：**export_privacy_blocked**，无客户半包，current 不变；不能靠合成 pass 记录或不一致 bytes 通过最终生产文件检查。 |

正常项目的全部 export/download 与 pure-reading 对照前后，current Document、Page 原注和原始 PPTX hash 保持不变。实际调用均来自安装的正式 runtime，未 mock compiler、readback、exports、policy 或结果。

fixture 的 slots/六维质量 Review 仍是明确合成 L1 gate 输入，`host_self/synthetic-test` 不变，说明没有客户事实或专业认可；本人不把这种 seed 写成正常 full-deck 生产或真实专业审批。此次修复先让 Page/compile/body 真源一致，并在保存正常产物前执行真实 readback；独立坏正文的正式出口拒绝证明检查没有被弱化。公开/工程字节检验属于实际 L6 文件工程，不替代 L2–L5。

## 两个 example 的影响与旧证据

新 `verify_download_notes` 由本人在真实三种用途 ZIP 上实际调用，同时另行检查全包/原件字节。w12 的变化只是引用同一 helper 并对真实下载调用、记录检查结果；本人**未独立运行完整 w11 browser main 或 w12 offline UI/recovery**，不借 Owner 的 w12/recovery 日志冒称自跑。其安装完整 UI、外网阻断、资源与恢复结果由 Owner/Root 分列。

原 53f4 CI `38642260224`：403 browser PASS、wheel build/install 成功，但旧 fixture Page 没有 notes 而实际 body 写 private canary，严格 readback FAIL，installed recovery NOT_RUN。旧失败目录 `reviews/rc3-02-final-head-ci/53f4ab335d4bacb0862d810cf8acf55eeba7e744/`（report.json SHA256 `517259dde97c5bc929d3acd00023b4d3462c837696f4ea003aff4e905374ff52`）与 actual installed 重现 `reviews/rc3-02-installed-fixture-53f4-reproduction/` 没有改动，旧失败不重写 PASS。这些历史 CI 事实来自 Root 原件，非本人重跑远端 CI。

产品/skill 实现精确零 delta，按相应影响复用本人的前轮 notes、scope/权限、旧 A 成本、源门禁与 CI 分类证据；没有重复 77 项或全树，也未把本轮未执行的旧 A 26 入口写成重新运行。

真人 Owner/听众、目标桌面 notes/保存重开、完整彩排、完整 RC3/最终发布仍 **NOT_RUN**。本轮 PASS 支持固定 65d82 的有限 example/实际文件修复，最终文档/current head 与新全部 CI 由 Root 再核；未合并。
