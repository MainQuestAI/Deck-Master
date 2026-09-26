# Workbench examples

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
