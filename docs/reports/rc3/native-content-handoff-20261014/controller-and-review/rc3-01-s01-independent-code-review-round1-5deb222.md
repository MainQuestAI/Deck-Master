# RC3-01-S01 独立核心审查

## 第一轮：REQUEST_CHANGES

- 审查者：`/root/rc3_01_code_review`，独立于 S01 实现 owner。
- UTC 日期：2026-10-14。
- 固定候选：`5deb222c77cadbdb835c695b17224d4e312d2395`。
- 方法候选基线：`1fb3ddacbb75a2d891b5a14d955cf23db9460931`。
- 审查范围：三 core 文件、`test_rc3_01_gate_repair.py` 和 `RC3-01-S01-GATE-REPAIR.md` 的纯 S01 提交。并行 dirty METHODS/ledger/anchor 文档未计入固定核心审查。
- 不改实现、不运行实际模型、不替主控安装/merge，不回写旧 A/B 方法候选及首轮真实运行。

### F-S01-01（P1）：旧稿依赖变化使仍相关的开放 finding 被跳过

位置：`content_review.preproduction_status` 和 `_applicable_reviews`。新增 closure 只遍历 `applicable` 记录；修改另一页时，整体 Plan/正文依赖漂移将旧 finding owner 先排除。新的 pass 即使没有 `replaces`，也能使未修的当前 P1 finding 消失于门禁。

独立重现使用正式 synthetic L1 API 链（临时项目在 reviews 目录，退出时删除）：

1. `_deck` 创建完整两页稿；`_initial_judgment(..., impact='must_fix')` 正式接纳 P1 开放 finding `f0`。
2. 读取两页，只给 **P2** 的首个正文 block 增加一句；通过 `open_phase_task(..., phase='page_copy')` 和 `_submit` 的完整两页/current Plan input 正式接纳。
3. `_publish` 接纳新前审 pass，不提交任何 `replaces` 或 `f0` 关闭。
4. `preproduction_status` 返回 `status='pass'`、`blocking_findings=[]`；旧 P1 finding 原字节仍保存，P1 未修。

这个缺口在 `1fb3` 已存在，并非 S01 新回归；主控明确将它归入本 S01 必须修复的门禁完整链，不能以旧缺陷为由放行。

修复建议：当前 pass 单元的适用性仍检查当前完整依赖；历史仍相关 finding 应另行遍历，使用同一个中央 `finding_closed` 及显式同逻辑 review/finding/page 的 closure。不得让 P2 或仅 notes 变化清除 P1 的正文缺陷；实际退役页/范围外对象也不能永久阻塞当前范围。增加正式 API 的页外修改→无 replaces pass 阻塞、合法同页修复→显式关闭通过，以及退役页/限定范围的必要正反例。

### 第一轮其他检查

逐字任务允许 honestly cue、拒绝 all-cue/空白 verbatim；段范围、已知 Narrative node、估时、固定 Page Ref 和写范围校验未移除。此结构最低要求不代表语义完整或真实计时。普通 cues Task 仍拒绝混入 verbatim。

中央 `finding_closed` 的 PPTX 例外仅新增 `preproduction` 阶段；最终审查仍要求当前输出变化，page_visual 仍要求当前同页 preview。固定稿件未变不能仅贴 `fixed` 标签；variance 仅关闭 needs_judgment，需要实际 observations/evidence/reason/current subjects/dependencies。既有 reviewer 认证和 independent receipt 验证未更改。

独立针对性测试：

```text
/workspace/work/rc3/cards/env-01/bin/python -m pytest \
  tests/rebuild/test_rc3_01_gate_repair.py \
  tests/rebuild/test_t03_review_fixes.py \
  tests/rebuild/test_content_preproduction_review.py \
  tests/rebuild/test_review.py \
  tests/rebuild/test_compose_v2_phases.py -q
118 passed in 6.07s

Ruff（3 core + 新 tests）：All checks passed!
git diff --check 1fb3ddac..5deb222c：exit 0
```

这些测试未覆盖 F-S01-01，故通过不抵消该独立复现。第一轮不签 merge PASS；等待 owner 修复后按新精确 SHA 再 review。

上述证据仅为代码/L1，不代替新安装实际生成、独立模型审阅/返修、完整计时、Owner/受众和桌面文件验收；人类项仍按安排 NOT_RUN。
