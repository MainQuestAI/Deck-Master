# 内容质量轮 v7 设计 · 执行口径（2026-11-21）

结论：架构师设计 `content-quality-v7-design-20261121.md`（SHA-256 70d1588b81a1cd28b70f52363e2f299d6830ba461e4d9a41431730394bf71dc8）照常执行，只有第 10 节假设 3 改口：出稿审稿后，框架字段变了也算 stale。本文覆盖设计第 7.2 节表格第 354 行和第 10 节第 3 条，其余不变。

依据：产品经理 2026-11-21 08:59（北京时间）对四条假设的答复。假设 1、2、4 按设计默认执行。

## 1. 假设 1、2、4（不变）

1. 证据项同时带 `ref` 和 `gap`，按输入错误拒绝。
2. 在 v6 库上做出稿审稿，先要求用 `deck put` 升级；`review add --record content_review` 不自动写回。
4. 从未审过时 `status=unreviewed`，`unreviewed_pages=[]`，不把全部页列进去。

## 2. 假设 3 改口：框架字段变化也判 stale（PR-E 落地）

框架字段固定为以下五项，不多不少：

| 含义 | 字段 |
|---|---|
| 读者 | `brief.audience` |
| 待决事项 | `brief.decision` |
| 关注点 | `brief.concerns` |
| 讲述人 | `brief.narrator`（含 `role`、`tone`） |
| 主线 | `framing.storyline` |

写快照：`review add --record content_review` 时，程序把这五项的**原文**写进 `snapshot_json` 的 `framing` 键（如 `{"framing": {"audience": "...", "decision": "...", "concerns": [...], "narrator": {...}, "storyline": [...]}}`），同时可另记一个规范化 JSON 的 sha256 作 `framing_sha256`。Host 不传这些值。

计算 `content_review.status`：

| 情形 | status | unreviewed_pages |
|---|---|---|
| 没有出稿审稿记录 | `unreviewed` | `[]` |
| 修订号全一致，且五项框架字段与快照一致 | `reviewed` | `[]` |
| 至少一页修订号不一致 | `stale` | 修订号不一致的 `page_id`（稳定排序） |
| 页修订号全一致，但框架字段有变 | `stale` | `[]`（靠 status 区分，不把全部页填进去） |

比较方式：按规范化 JSON（键排序、数组保持顺序）逐项比较。旧快照里没有 `framing` 键时，按「框架未知」处理，只看修订号，不判 stale。

不要用 `version_id` 是否变化来判 stale：采用候选（adopt）、只改产物也会换 `version_id`，会误判。`version_id` 仍只作记录。

可选：返回里可加 `stale_reasons`（如 `["pages","framing"]`）帮助读懂原因；不加也行，不作为验收项。

## 3. 对各 PR 的影响

- PR-B：不扩大。`snapshot_json` 仍是一个 TEXT 存 JSON 的列，设计第 6 节迁移不变。
- PR-E：按本文第 2 节写快照和计算 status，补两条回归：只改 `framing.storyline` 后导出得到 `stale` 且 `unreviewed_pages=[]`；只采用候选（换 version_id、修订号和框架都不变）后仍为 `reviewed`。
- PR-C、PR-D：无影响。
