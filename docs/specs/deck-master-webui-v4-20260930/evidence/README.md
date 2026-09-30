# 核验与证据层级

本轮核验代码为 main `66da345c84de48933a76de577114f08dcebf4f0e`，没有改生产代码。

- `current-core-tests.log` / XML：本轮运行9个相关测试文件，**148 passed / 24.94秒**；这是定向核心回归，不是完整905项回归，也不是新版浏览器验收。
- `probe_gaps.py` / `gap-probes.json`：本轮在临时合成项目运行5项源码行为核验，无模型调用，临时项目已清理。覆盖正文trial拒绝、attention/prompt摘要缺项、candidate summary/schema不一致、固定revision HTTP已实现、旧项目能力广告与实际可执行性不符。
- `inherited-execution-state.json`：旧执行线程台账快照，不等同本轮验收。
- `inherited-*.json`：按 `inherited-evidence-manifest.json` 收回旧证据；不修改源文件、不把旧时间/旧SHA改成新结果。W12安装摘要属于PR66 head93c76a1；可证明该候选记录过23步成功，不能证明新基线的最终安装。压力记录明确失败，不能计20分钟通过。
- `governance-before.json` / `governance-after.json`：本次本地分支归档事务与前后状态；没有远端删除、旧工作树清理或PR写操作。
- `source-anchors.json`：当前主线源码位置，用于复核差距判断。
- `spec-validation.json`：仅证明本Spec的文件/编号/依赖/收讫hash完整性。

## B01 工程切片证据（webui-b 线）

B01 在 `codex/webui-b-capabilities` 分支实施后新增：

- `b01_pressure.py` / `b01-pressure.json`：300页×5候选×3Attempt合成压力样本（6304个元数据对象，无模型调用），warm 120次 `workbench_summary`，**p50 72ms / p95 84ms / max 89ms**，低于250ms门槛；冷读首访675ms不作为门槛项。仅为读模型合成证据，不是生产运行或真实Host验收。复现：`PYTHONPATH=src python docs/specs/deck-master-webui-v4-20260930/evidence/b01_pressure.py /tmp/b01-pressure.json`（或用已装dev依赖的解释器直接运行）。
- gap-probes 的 P02（attention恒not_recorded、无prompt摘要）与 P03（candidate summary违反活动schema）已由 B01 产品实现关闭，回归见 `tests/rebuild/test_workbench_actions.py`（11项）及既有 `tests/rebuild/test_workbench_reads.py`；`probe_gaps.py` 的对应断言针对基线 `66da345` 的缺口，在新代码上会按预期失败，保留为基线记录不作修改。P05 属 B02 范围，本轮未处理。

复现探针：在仓库安装dev依赖后，`PYTHONPATH=src python docs/specs/deck-master-webui-v4-20260930/evidence/probe_gaps.py /tmp/deck-master-gap-probes.json`。脚本借用既有测试fixture创建候选，不能用于生产项目。
