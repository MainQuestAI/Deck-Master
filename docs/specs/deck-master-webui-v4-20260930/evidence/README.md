# 核验与证据层级

本轮核验代码为 main `66da345c84de48933a76de577114f08dcebf4f0e`，没有改生产代码。

- `a01-verification.md` / `a01-browser-verification.json` / `output/playwright/a01/*.png`：**A01 实施后新增**。在 `codex/webui-a-implementation` 分支完成设计基础落地与 PR66 有限移植后的分层验证（核心 905 项通过 + 真实服务双视口浏览器证据）；head/base 与缺项见该文件。基线核验（下述其余条目）仍对应 `66da345` 未实施状态。
- `current-core-tests.log` / XML：本轮运行9个相关测试文件，**148 passed / 24.94秒**；这是定向核心回归，不是完整905项回归，也不是新版浏览器验收。
- `probe_gaps.py` / `gap-probes.json`：本轮在临时合成项目运行5项源码行为核验，无模型调用，临时项目已清理。覆盖正文trial拒绝、attention/prompt摘要缺项、candidate summary/schema不一致、固定revision HTTP已实现、旧项目能力广告与实际可执行性不符。
- `inherited-execution-state.json`：旧执行线程台账快照，不等同本轮验收。
- `inherited-*.json`：按 `inherited-evidence-manifest.json` 收回旧证据；不修改源文件、不把旧时间/旧SHA改成新结果。W12安装摘要属于PR66 head93c76a1；可证明该候选记录过23步成功，不能证明新基线的最终安装。压力记录明确失败，不能计20分钟通过。
- `governance-before.json` / `governance-after.json`：本次本地分支归档事务与前后状态；没有远端删除、旧工作树清理或PR写操作。
- `source-anchors.json`：当前主线源码位置，用于复核差距判断。
- `spec-validation.json`：仅证明本Spec的文件/编号/依赖/引用/收讫hash完整性。

复现探针：在仓库安装dev依赖后，`PYTHONPATH=src python docs/specs/deck-master-webui-v4-20260930/evidence/probe_gaps.py /tmp/deck-master-gap-probes.json`。脚本借用既有测试fixture创建候选，不能用于生产项目。
