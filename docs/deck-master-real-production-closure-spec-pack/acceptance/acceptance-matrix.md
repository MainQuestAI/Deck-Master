# Acceptance Matrix

## 1. Stack A

| Case | 预期 |
|---|---|
| Production 无执行器 | `awaiting_agent_execution`，不产出假文件 |
| PPT Deck Pro Max bridge 3 页 | 3 个 v2 result，真实 artifact |
| run_id mismatch | reject + P0 event |
| Agent partial result | partial，不冒充全量完成 |
| Build HTML | 可打开、页数正确 |
| Build PDF | `%PDF-`，页数正确 |
| Build PNG | 每页真实 PNG |
| Build PPTX | 可被 python-pptx / LibreOffice 打开 |
| page order | 与 manifest 完全一致 |
| source change | old build stale |

## 2. Stack B

| Case | 预期 |
|---|---|
| 文本改名 `.pptx` | P0 blocked |
| 文本改名 `.png` | P0 blocked |
| 损坏 PDF | P0 blocked |
| 0 byte artifact | P0 blocked |
| checksum mismatch | P0 blocked |
| stale render | P0 blocked |
| missing required format | P0 blocked |
| flat-image + native required | P1 blocked，需修复或授权 |
| all ready | final readiness ready |
| Export 与 readiness 不一致 | 测试失败 |

## 3. Stack C

| Case | 预期 |
|---|---|
| Release build outside repo | 成功 |
| 删除原 repo 后运行 | 成功 |
| Clean temp HOME install | full_suite_ready=true |
| Upgrade 0.9.13 → 0.9.16 | 成功 |
| Broken staged release | current 不受影响 |
| Rollback | 恢复 previous |
| 3 real cases | 完整报告 |
| Private source scan | 无客户原文提交 |
| RC 缺 benchmark evidence | blocked |
| RC 全部达标 | candidate ready |

## 4. 不可豁免项

以下不允许 override：

- Production placeholder；
- run/session mismatch；
- invalid format；
- path traversal；
- checksum mismatch；
- stale final artifact；
- missing required final artifact；
- 客户可见 P0；
- final page count mismatch。

P1 可按既有 override governance 处理，但必须绑定 finding_id、approver、reason 和有效期。
