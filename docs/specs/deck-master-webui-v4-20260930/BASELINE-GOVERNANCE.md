# 基线与分支治理

本次操作日期2026-09-30。新的A/B称谓仅适用于本轮，旧A=Flow Quality、旧B=webui-rebuild、W01–W12仍按历史名称保留。

## 代码和设计基线

- 已fetch并核对远端 `origin/main = 66da345c84de48933a76de577114f08dcebf4f0e`（PR65合并）。PR39以及W01–W11相关工程切片已在该主线，不能再以9月26日“仅文档”作为当前事实。
- 新共同基线标记：`baseline/webui-v4-20260930`。该tag对应本次收讫设计、Spec和治理文档的提交；生产代码相对上述main无改动。用 `git rev-parse baseline/webui-v4-20260930` 取得准确SHA。
- 新A：`codex/webui-a-implementation`，工作树 `/Users/dingcheng/.codex/worktrees/webui-a/Deck-Master`。
- 新B：`codex/webui-b-capabilities`，工作树 `/Users/dingcheng/.codex/worktrees/webui-b/Deck-Master`。
- 两条分支初始共享同一文档基线提交；原仓库、旧W12工作树与OpenDesign原件不切换、不覆盖。

## 已执行的清理

25个 `codex/workbench-w*` 本地分支同时满足：SHA未变化、是main祖先、没有工作树占用。已用单次 `git update-ref` 事务转存 `refs/archive/webui-20260930/<原分支名>`，再移除对应本地heads。本地main从旧祖先快进到66da345。前后清单及每个SHA见 [before](evidence/governance-before.json) / [after](evidence/governance-after.json)。归档引用持续保留提交，可用 `git branch <恢复名> refs/archive/webui-20260930/<原分支名>` 恢复。

未删除远端分支、未归档/移除有占用的旧工作树、未clean/reset、未删除用户运行材料。未合入且旧工作树占用的分支保留；本轮仅治理新的开发目标，不将未知用途目录当垃圾。

## 未合并变更处理

| 项目 | 当前事实 | 本轮处理 |
|---|---|---|
| PR66 / codex/workbench-w12-final | OPEN，head93c76a152394a50ad0bc226597992c5a4357b7a3，8条CI成功；旧执行工作树仍在 | 不纳入共同代码基线。A01先独立评审并复用适用的run-desk状态水合/offset修复；B07接安装/压力遗留。不得把其W12报告当最终通过。 |
| PR40 / codex/webui-b1-1 | 旧B1-1文档草稿、目标旧webui-rebuild | 历史参考，不合入新A/B，不在本轮自动关闭 |
| PR34 / codex/shared-skill-sync | 旧共享Skill同步分支 | 保留，实施前若需同步由B02逐项核对，不整支合入 |
| codex/generation-workbench-spec及旧webui-* | 已有历史设计/验证记录 | 保留来源，收讫新版规范优先 |

没有执行merge/close/comment/push。共享基线是本地准备完毕的交付；后续发布PR前重新核对remote main及归属，不把本地tag误称已发布。

## 同步与冲突归属

B只交共享核心/契约/CLI/Skill和包；A只交UI与浏览器验证。每张卡独立评审，B接口先进入main，A再同步接入。初次共享Spec提交可先经单独docs PR进入main；在此之前两线可从共同tag开工。不得为了合一个卡整条合入对方未来未审代码。

修改web.py/cli.py/contracts由B负责；A发现缺字段回填差距，由对应B卡修补。UI缺陷由A负责，B集成测试不顺手重写前端。共同Spec变化需附两侧影响和明确新依赖；每条线一次一个活动卡。
