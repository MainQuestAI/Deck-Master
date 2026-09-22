# QA Test Plan

## 1. 测试层级

1. Unit
2. JSON Schema / Contract
3. Adapter
4. Integration
5. Fixture E2E
6. Production failure E2E
7. Browser smoke
8. Clean install
9. Upgrade / rollback
10. Real benchmark

## 2. 必跑命令

最终命令以实际实现为准，但至少包括：

```bash
python3 -m compileall scripts tests
python3 -m unittest discover -s tests
git diff --check HEAD
```

新增：

```bash
deck-master contract-validate --all
deck-master release-build --output /tmp/deck-master-release
deck-master release-smoke --release /tmp/deck-master-release --temp-home
deck-master benchmark-rc-report --real-only
```

## 3. Failure Matrix

必须自动生成下列坏产物：

- fake.pptx（普通文本）
- corrupt.pptx（坏 ZIP）
- missing-content-types.pptx
- fake.png
- truncated.png
- fake.pdf
- empty.html
- page-count-mismatch.html
- stale artifact manifest
- checksum mismatch
- absolute path result
- traversal path result
- wrong run_id
- wrong session_id
- fixture source in production

每项都必须有明确 finding 和 next action。

## 4. Browser Smoke

桌面 1600 / 1440 / 1280：

- awaiting Agent；
- generation partial；
- build blocked；
- artifact invalid；
- artifact stale；
- needs quality；
- needs approval；
- ready for export；
- delivered。

动作：

- 查看 artifact 详情；
- 跳转 blocker；
- 批准页面；
- 提交审批；
- 重新计算 readiness；
- 确认交付。

## 5. 真实案例 QA

每个真实案例保存：

- command log；
- timestamps；
- run-state snapshots；
- artifact validation report；
- quality reports；
- review decisions；
- final readiness；
- delivery package hash；
- benchmark metrics；
- 人工结论。

## 6. QA 裁决

- P0：阻断合并或 RC。
- P1：默认阻断 Stack Exit；只有明确归属下一 Stack 且不影响本 Stack 业务目标时可延期。
- P2：可进入 backlog，但必须记录。
