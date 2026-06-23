# Development Review Protocol

## 1. 评审顺序

1. 确认实际 implementation spec。
2. 确认 baseline SHA。
3. 确认 Task 范围。
4. 检查 P0 业务目标。
5. 检查 contract / migration。
6. 检查测试证据。
7. 检查 spec deviation。
8. 再检查代码质量和 P2 优化。

## 2. P0 定义

以下任一项为 P0：

- Production 可产生 placeholder；
- invalid artifact 可被标记 ready；
- parse failure 被吞；
- run/session mismatch 未阻断；
- stale artifact 可 export；
- required artifact 缺失可 export；
- release 依赖源码仓但文档声称独立安装；
- final readiness 和 export 结论不一致；
- real benchmark 使用 fixture 充数；
- 用户可见产物或状态存在误导。

## 3. 无法确认

以下不能直接判缺陷，必须要求证据：

- 本机是否安装 Playwright / LibreOffice；
- 当前测试是否通过；
- 真实案例是否达标；
- release 在 clean HOME 是否通过；
- 外部 Agent 是否真实生成高质量页面。

## 4. 评审输出

```text
结论
P0 阻断项
P1 必修项
待核实项
可优化项
Spec deviation 裁决
测试证据裁决
是否允许进入下一 Stack
```

## 5. Merge Gate

- Stack A：真实 non-fixture smoke。
- Stack B：完整 failure matrix。
- Stack C：clean install + real benchmark + RC checklist。
