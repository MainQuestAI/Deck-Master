---
name: deck-master
description: Operate the rebuilt Deck Master core for new decks, page edits, checks, and delivery; the Host writes complete copy and real results, the code owns files, storage, and truth.
---

# Deck Master（重建核心）

## 使用场景

用户给出任务或修改意见时操作 Deck Master。主流程通过 create / continue / task accept 完成，不要求用户按阶段手动执行命令。

| 任务 | 入口 | 方法 |
| --- | --- | --- |
| 新 Deck（普通材料目录） | `deck-master create --brief … --source … --out …` | [source-reading](references/source-reading.md)、[content-methods](references/content-methods.md)、[content-examples](references/content-examples.md) |
| 已有完整稿 | `create --draft draft.json` 或 `import-draft` | [content-examples](references/content-examples.md) |
| 继续推进 / 领取下一批任务 | `deck-master continue --project …` | 返回稳定 pending_tasks，不重复提问 |
| 提交宿主结果 | `deck-master task accept --project … --task-id … --operation-id … --produced-against … --result result.json` | 信封形状见 CLI 输出与 [result-envelope 例](../../docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/README.md) |
| 修改页 | `task accept`（repair 信封，仅 scope_pages 内） | [content-methods](references/content-methods.md) |
| 查看与交付 | `view`（T05 起可用）、`check`、`export` | 工作台与导出规则见 spec 09/07 |

## 自动工作台（必守）

create --draft / import draft / compose 结果**第一次形成至少一页后，主 Skill 必须立即自动调用 `deck-master view --open`**，再继续逐页制作；service 响应的 `next_action=auto_view_then_production` 就是该动作。不需要用户手动执行 view。同项目复用同一服务与 URL；服务失效才重启并更新实际地址。

## 真实性规则

- 任务输入里只装真实读取的资料与已确认决定；不调用规则 Planner、不循环 claim、不从数组取模配论点、不用固定痛点/风险/CTA 补页。
- `task accept` 前文件已写入本次 operation 的 staging；`produced_against` 与任务派发 hash 一致，否则先重读新输入。
- 外部图像调用先按额度事务 begin，完成后 settle；未执行不报 consumed。
- 没有实际阅图/渲染/人类检查的项目保持未验证标注；工程通过不升级为内容专业。
- 普通取舍按 spec 决定，不把每一步交回用户；缺工具、缺授权、真实用户决定是停止条件。

## 旧体系说明

旧 v0.9.x 预览链（`python3 scripts/deck_master.py`，route-skill/next-step/run-dir）仍存在但只服务历史 demo；新工作一律走本文件命令，不在同一 run 里混用两套写入者。旧命令退役按 spec 12/02 排期。

## 停止与安全

缺输入或工具、需要真实用户决定、用户叫停时停止并说明。保留无关页与已确认设计；私密/内部材料不进客户可见产物；不伪造证据或绕过当前门禁；无授权不导出交付。
