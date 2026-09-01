# Acceptance Matrix

日期：2026-09-01  
主 Spec：[`../00-master-spec.md`](../00-master-spec.md)

| ID | Requirement | Priority | Evidence |
|---|---|---|---|
| ODG-AC-001 | 高密度 run 的 final readiness 识别 `builder_profile=high_density`，不被标准 preview/page review 误阻断 | P0 | targeted final readiness test |
| ODG-AC-002 | 默认客户可见黑名单不包含 `制作`、`投标`、`评审`、`评分`、`内部`、`Brief`、`讲标` | P0 | `tests/test_customer_visible_safety.py` |
| ODG-AC-003 | 最小 clean PPTX 不因 slide layout/master/presentation 内置 `Placeholder` 被 P0 拦截 | P0 | python-pptx probe test |
| ODG-AC-004 | PPTX audit 仍能拦截真实 slide 文本中的 `TODO`、`TBD`、`placeholder`、`manual_placeholder` | P0 | negative customer-visible test |
| ODG-AC-005 | 高密度 completed 且当前 quality gate 已通过时，`next-step` 不再返回同一条 render gate | P0 | `tests/test_high_density_builder_v2.py` |
| ODG-AC-006 | 无 `DECK_MASTER_REVIEW_ATTESTATION_KEY` 时，默认生产链可用本地 review receipt 继续 | P1 | high-density visual review test |
| ODG-AC-007 | 显式开启 external main review 时，缺签名 key 仍会阻断并给出可执行说明 | P1 | high-density negative test |
| ODG-AC-008 | 风格选择有公开 CLI，`next-step` 返回真实命令 | P1 | CLI help + style lock test |
| ODG-AC-009 | 蓝图批准有公开 CLI 或明确自动批准条件，状态不要求手写内部 JSON | P1 | blueprint approval test |
| ODG-AC-010 | Provider 蓝图可从用户指定本地路径导入并记录 hash，不强绑 `~/.codex/generated_images` | P1 | provider receipt import test |
| ODG-AC-011 | 视觉审阅默认只要求 producer review + measured metrics pass，main review 可配置 | P1 | visual review policy test |
| ODG-AC-012 | 64 页高密度构建按阶段批量 handoff，失败页进入 rework 队列 | P1 | batch handoff test |
| ODG-AC-013 | 封面、章节页、目录页、视觉页不会因低文本或少于 3 个正文信息区被误杀 | P1 | role-aware content lock test |
| ODG-AC-014 | 正文页仍会阻断 unsupported numeric facts 和无 evidence 的业务判断 | P1 | negative evidence test |
| ODG-AC-015 | 图片面积策略按页面角色执行，正文页仍禁止图片覆盖 P0/P1 文本 | P1 | role-aware SVG image policy test |
| ODG-AC-016 | `structural_label` 不要求业务 evidence，带事实含义的判断和数字仍要求 evidence | P1 | content lock schema/content test |
| ODG-AC-017 | 过期 gate report 不能阻断当前 artifact，只能输出 warning 或 stale 状态 | P1 | final readiness freshness test |
| ODG-AC-018 | P1 override 在 delivery validation、export queue、final readiness 三处一致生效 | P1 | override integration tests |
| ODG-AC-019 | P0 finding 不能被 override | P0 | override negative test |
| ODG-AC-020 | `build status --watch` 在可行动状态立即返回，不默认空等 30 秒 | P2 | watch behavior test |
| ODG-AC-021 | `output_profile=production_pptx` 不强制 HTML/PDF/PNG 全套输出 | P2 | build manifest/render request test |
| ODG-AC-022 | Review Workbench 支持批量批准所有无阻断页，阻断页保留逐页原因 | P2 | review workbench batch test |
| ODG-AC-023 | 旧 `DECK_MASTER_USER_ATTESTATION_KEY` 不出现在用户可见 next-step 或 high-density skill 指引中 | P2 | `rg` scan |
| ODG-AC-024 | 整包 targeted regression 通过，且 `git diff --check` 通过 | P0 | command output |

