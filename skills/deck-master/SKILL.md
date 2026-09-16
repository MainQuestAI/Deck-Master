---
name: deck-master
description: Operate the Codex Desktop edition of the rebuilt Deck Master core; Codex writes complete copy and uses its built-in image tool, while the code owns files, storage, and truth.
---

# Deck Master（重建核心）

当前 v1.1 候选是 **Codex Desktop 专用版本**。需要生图时使用当前 Codex 会话内置
ImageGen，不配置 Provider 或 API Key；其他宿主兼容暂不进入验收范围。

## 使用场景

用户给出任务或修改意见时操作 Deck Master。主流程通过 create / continue / task accept 完成，不要求用户按阶段手动执行命令。

| 任务 | 入口 | 方法 |
| --- | --- | --- |
| 新 Deck（普通材料目录） | `deck-master create --brief … --source … --out …` | [source-reading](references/source-reading.md)、[content-methods](references/content-methods.md)、[content-examples](references/content-examples.md) |
| 已有完整稿 | `create --draft draft.json` 或 `import-draft` | [content-examples](references/content-examples.md) |
| 继续推进 / 领取下一批任务 | `deck-master continue --project …` | 返回稳定 pending_tasks，不重复提问 |
| 提交宿主结果 | `deck-master task accept --project … --task-id … --operation-id … --produced-against … --result result.json` | 信封形状见 CLI 输出与 [result-envelope 例](../../docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/README.md) |
| 生成蓝图 | `continue` 返回 `kind=blueprint` | [Codex 蓝图执行方法](references/blueprint-svg.md) |
| 修改页 | `task accept`（repair 信封，仅 scope_pages 内） | [content-methods](references/content-methods.md) |
| 查看与交付 | `view`、`continue` 自动检查、`export` | 工作台与导出规则见 spec 09/07 |

## 自动工作台（必守）

create --draft / import draft / compose 结果**第一次形成至少一页后，主 Skill 必须立即自动调用 `deck-master view --open`**，再继续逐页制作；service 响应的 `next_action=auto_view_then_production` 就是该动作。不需要用户手动执行 view。同项目复用同一服务与 URL；服务失效才重启并更新实际地址。

## 真实性规则

- 任务输入里只装真实读取的资料与已确认决定；不调用规则 Planner、不循环 claim、不从数组取模配论点、不用固定痛点/风险/CTA 补页。
- `task accept` 前文件已写入本次 operation 的 staging；`produced_against` 与任务派发 hash 一致，否则先重读新输入。
- 外部图像调用先按额度事务 begin，完成后 settle；未执行不报 consumed。
- 蓝图任务只调用当前 Codex 会话的内置 ImageGen；不请求 Provider/API Key。实际提交 prompt、原始图片和可得 invocation ref 一并保存。
- 没有实际阅图/渲染/人类检查的项目保持未验证标注；工程通过不升级为内容专业。
- 普通取舍按 spec 决定，不把每一步交回用户；缺工具、缺授权、真实用户决定是停止条件。

## 连续制作与返修

`task accept` 后继续执行 `continue`，直至 `ready_for_export`、用户停止或具体输入/工具缺口。
`awaiting_host` 是交接请求，不是已执行；先 `task start` 再做 Host 工作。CLI 返回 3 时读取 stdout JSON 并处理其中任务，不能把它当成执行失败直接终止。

- `reconstruct`：实际读取原图、完整 Page 和允许资产，以任务reference_images给出的实际图片hash读取原图，先写原图模块/关系期待，再输出单份原生 SVG；SVG根写data-blueprint-sha256为该原始图片字节哈希，不能复用同正文另一张图的SVG充当还原。若纠正文案或补标签，同一信封提交更新后的 Page 和理由。不得改写原图，不能仅改 SVG 隐藏正文错误。
- `continue` 本地执行编译、SVG/PPT 渲染和真实文件回读；不需要手写外部编译脚本。失败回到明确的 Page/SVG/编译层处理，不通过重新生图掩盖。
- `review`：实际看 Page、原图、SVG 和 PPT 渲染。分别提交 content、blueprint_content、blueprint_fidelity、conversion、readability、privacy 记录，subjects 固定当前文件；有问题保留 findings 并返修。Host 自审写 host_self，不能写独立或专业验收。
- `edit --page … --base-revision … --page-hash … --operation-id …` 修改正文后继续重建受影响页；原图保留。`history list/restore` 恢复产生新 revision。
- `export --purpose working` 包含可继续编辑项目；`--purpose delivery` 要求当前工程审阅通过。导出完成不等于专业或桌面验收完成。

候选尚未切换全局入口时，使用候选环境的 `python -m deck_master` 执行上述子命令，不能误调用旧全局 `deck-master`。

## 旧体系说明

旧 v0.9.x 预览链（`python3 scripts/deck_master.py`，route-skill/next-step/run-dir）仍存在但只服务历史 demo；新工作一律走本文件命令，不在同一 run 里混用两套写入者。旧命令退役按 spec 12/02 排期。

## 停止与安全

缺输入或工具、需要真实用户决定、用户叫停时停止并说明。保留无关页与已确认设计；私密/内部材料不进客户可见产物；不伪造证据或绕过当前门禁；无授权不导出交付。
