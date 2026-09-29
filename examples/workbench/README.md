# Workbench examples

## W04 gallery and image cache

```sh
PYTHONPATH=src python examples/workbench/w04_core.py --out /tmp/w04-core
PYTHONPATH=src python examples/workbench/w04_gallery.py --out /tmp/w04-gallery
```

Use new output directories. The browser script runs real Chromium against local
synthetic 30/80-page projects: fixed layers, filters, comparison, keyboard and
position recovery, CAS conflicts, lost ACKs, offline reading, two-viewport warm
timings, and bounded image caches. Share checks.json and screenshots; raw traces
remain local because they can contain session headers. The 80-page cache walk
does not replace the pending 300×5×3 Candidate/Attempt pressure fixture or the
W10 20-minute heap test. No model calls, real HOME changes or user acceptance.

## W02 task accept recovery

The generation protocol now has a separate two-phase real Host example:

```sh
PYTHONPATH=src python examples/workbench/w02_host_roundtrip.py prepare --out /tmp/w02-host --thread-id ACTUAL_THREAD --turn-id ACTUAL_TURN
# Execute the actual built-in image tool using the frozen input between phases.
PYTHONPATH=src python examples/workbench/w02_host_roundtrip.py complete --out /tmp/w02-host --item-id ACTUAL_NATIVE_ITEM
```

Replace the identity labels with real runtime IDs. The script makes no model
call itself. Its temporary synthetic project survives between phases; it saves
machine responses and verifies one request/attempt/call ledger against native
PNG bytes. Read the generation.v1 section of the public blueprint-svg method
for the observed-field coverage and restricted literal-call shape. Ordinary
variable-based calls retain unknown attachment coverage; provider model/seed
remain unknown. Nonempty reference-image observation is not claimed.

`w02_observation_probe.py` can independently collect one real native image
completion by thread/turn/item identities; it does not accept arbitrary logs.

```sh
PYTHONPATH=src python examples/workbench/w02_recovery.py --out /tmp/w02-recovery
```

This creates a temporary synthetic project, crashes a child process immediately
after task adoption and before receipt publication, makes a later independent
commit, and retries through the public CLI. It records the real request IDs,
stable receipt, CLI response, rebuilt cache and pointer hash. The original
adoption is recovered without moving current backward. No Host/model call is
made; this is not W02's real tool-observation acceptance.

## W01 read model

Run from a source checkout with the project's Python dependencies installed:

```sh
PYTHONPATH=src python examples/workbench/w01_lineage.py --out /tmp/w01-example
PYTHONPATH=src python examples/workbench/w01_lineage.py --out /tmp/w01-base-300 --pages 300
PYTHONPATH=src python examples/workbench/w01_lineage.py --out /tmp/w01-browser --serve
```

The output directory must be new. The script creates a temporary **synthetic**
project through the core, stores mixed-stage test artifacts and a saved request,
then takes project/revision/page/ref IDs from actual responses. It checks pinned
history after a later core edit, prompt separation, read-only behavior and a
missing-version error. The project is removed on exit; inputs, raw responses,
manifest and 100 latency samples remain in the output directory.

`--serve` keeps the temporary service alive for browser checks until Ctrl-C.
Its first title contains inert attack text and its SVG contains an intentionally
blocked script. These fixtures are not suitable for a production deck. No
Host/model, renderer, install or customer-delivery claim comes from this script.

The 300-page sample has **zero Candidates and Attempts**, with no concurrent
updates during sampling. It cannot close W01-AC01's 300×5×3 pressure requirement.

## CLI and HTTP

| CLI | HTTP |
| --- | --- |
| `view --project <dir> --summary [--revision <id>] --json` | `/api/view/summary?revision=<id>` (alias `/api/workbench`) |
| `view --project <dir> --revision <id> --json` | `/api/view?revision=<id>` |
| `view --project <dir> --page-id <id> [--revision <id>] --json` | `/api/pages/<id>?revision=<id>` |
| `view --project <dir> --page-id <id> --lineage [--revision <id>] --json` | `/api/pages/<id>/lineage?revision=<id>` |
| Existing `view --project <dir> --json` | Service status (unchanged) |

`/api/tasks` and `/api/reviews` also honor revision. All routes retain the bound
project and loopback Host restrictions. Reads require no token; write safety is
unchanged. Every explicit version must be a committed ancestor of the captured
current pointer. Invalid versions do not fall back to current. The two new
schemas are read projections, not additional persistent object types.

The summary omits page bodies, prompt text and candidate/attempt detail. It
reprojects the selected Document with a bounded immutable JSON-object cache;
keys include project root, object path/hash and inode/size/mtime/ctime. Path and
symlink checks run even on cache hits. Reads validate object bytes and contracts;
binary files are hash-checked by `/api/file`, not repeatedly during polling.
Detail reads stored request/submitted text and never rerun prompt projection.
Legacy actual text is only `host_reported`; result linkage without a saved
binding is `unknown`. A PPT preview co-recorded with an output has a `derived`
snapshot relationship, not a proven compiler parent.

## W02 ContentPlan 合成流程

```sh
PYTHONPATH=src python examples/workbench/w02_content_plan.py --out /tmp/w02-content-plan-example
```

输出目录必须不存在。脚本从 CLI 新建项目回包取任务和真实材料版本，声明 compose.v1 能力，采用两页合成正文及计划，再通过公开 CLI 重放并读取固定版本和按页链路。首次采用使用共享 Service，避免为隔离验证打开浏览器；全过程不调用模型，属于 core/CLI 工程证据。保留 checks、schema 输入和读取回包；项目运行目录不提交到仓库。

### W05 单页链路、提示词与固定比较

```
PYTHONPATH=src python examples/workbench/w05_page_chain.py --out /tmp/workbench-w05-proof-new
```

脚本启动真实本机服务和 Chromium，读取来源、逐页正文、预备/实际提示词、制作摘要与固定版本图件，验证 Unicode 码点选段、差异、草稿基准隔离、ACK 跨端口恢复及未同步内容显式导入。后台更新与比较读取失败都必须保留固定双方；比较侧链接与来源返回保留自身版本。

输入全部是明确标注的合成夹具。为验证观察来源的呈现，脚本只在独立临时目录重放人工构造的 native event，绝不读取真实会话或调用模型；这不替代 W02 真实 Host 证明。制作计数与 PPT 预览也是合成记录，不证明实际 Office 编辑或渲染质量。仅可分享 `checks.json` 与截图；`local-only-trace.zip`、`local-only-prompt-recovery.json` 和临时会话记录保留本机。

### W06 标注、变更计划与操作恢复

```sh
PYTHONPATH=src python examples/workbench/w06_change_handoff.py --out /tmp/workbench-w06-proof-new
```

输出目录必须不存在。脚本使用明确标注的合成项目，从 CLI 摘要回包取得真实 project/revision/Page refs，发送前保存 UUIDv4 和完整请求，再执行意见保存、计划、提交、operations 核实和 handoff 读取。真实 Chromium 中的同源 fetch 例子沿用 session/Origin 防线；这属于 HTTP 工程示例，不是产品标注 UI 或真实 Host 接手证明。

原始回包位于本机 `local-only-requests/`：`base-conflict.json` 对应 CLI 5，须刷新版本重新预览；`operation-payload-conflict.json` 对应 CLI 5，原 ID 只能重放原 payload；`operation-not-found.json` 对应 CLI 2，脚本随后用已保存的同一 ID 和 payload 重放。响应丢失由客户端主动忽略第一次回包模拟，查询以已提交历史为准。另有单测对新操作与旧 task accept 分别执行四个位置的真实子进程退出；这不证明任意硬件断电恢复。

任务保留 `awaiting_host`，脚本不编造执行身份或调用模型。可分享 `checks.json`；完整请求、交接块和项目运行目录保留本机，不提交仓库。

## W06 opinions, plans and durable handoff UI

```sh
PYTHONPATH=src python examples/workbench/w06_annotations_browser.py --out /tmp/w06-browser
PYTHONPATH=src python examples/workbench/w06_annotations_edges.py --out /tmp/w06-edges
```

These scripts drive the actual UI against a real loopback service with synthetic
pages. Network and clipboard faults are explicitly injected. They check fixed
version points/rectangles, Unicode code-point ranges, conditional opinion scopes,
read-only impact preview, changed-input invalidation, persistent handoff, original
operation replay, late-draft isolation, SVG letterboxing, tiny-coordinate digest
parity, and recovery after a service restart on a different port.

Add `--wait-for-host` to the first script to pause after the UI has saved, planned,
committed and copied the handoff. It prints a local-only handoff file. A real Host
must read that generated plan and invoke the official CLI with its own execution
reference and the required protocol/capabilities; the script never impersonates
that Host. It waits for the actual running state, records it, then confirms
cancellation through the browser. This proves claim/status/cancellation only, not
model generation, result quality or delivery readiness. Requests, recovery files
and full local handoffs stay in `local-only/`; only curated checks/screenshots
belong in the repository report.

## W07 trial and candidate adoption

`w07_trial_adopt.py` operates an existing workbench.v3 project through the public
CLI. `trial --page-id ACTUAL_PAGE --stage blueprint --instruction '…'` previews a
trial, optionally with `--reference-page-id` and a fixed `--reference-revision`.
`adopt --candidate-id ACTUAL_ID` previews a length-one adoption; repeat the ID
flag for a batch. Both require `--project` and a **new** `--out` directory.
`--commit` submits the selected plan; without it the script only previews.
It saves the exact payload and operation ID before writing and retains unknown
responses for `operations show` recovery. It never starts a Host or calls a
model. Obtain candidate IDs from actual task returns or candidates list/show.

Core fault and renderer cases are in `tests/rebuild/test_candidates.py`.
These synthetic tests do not close W07-AC07's real fixed-reference/Host/browser
acceptance; the W07 execution report records that separately.

### W08 风格校准浏览器

`w08_browser.py --out <new-dir>` 验证简单/高级要求、单页试作、比较采用、明确扩展和画廊/单页入口；`w08_browser_edges.py --out <new-dir>` 验证原文选段、逐项冲突、未知确认恢复及并发目标变动。两者只用显式合成 Host，实际模型调用为 0；真实图像评价见 W08-UI 报告。

### W09 内容与来源核心

`w09_content_inputs.py --out <new-dir>` 通过公开 CLI 验证材料替换、局部更新、来源读取、重排与移除。该脚本使用明确的合成 Host 结果，模型调用为 0；实际 Codex Host 阅读和影响判断证据见 W09-CORE。

### W09 内容编辑浏览器

`w09_browser.py` 验证正文、页序、输入与保存恢复；`w09_browser_edges.py` 验证模拟 Host 的合并/拆分/改写、来源与冲突；`w09_source_browser.py` 验证材料用途、替换、移除及历史版本定位。均使用 `--out <new-dir>`，真实本地服务 + Chromium，显式合成材料/Host，模型调用为 0。真实 Host 材料判断另见 W09-CORE。
