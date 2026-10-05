# PR100 · V1.0.0 RC 收口修复

工作代号 PR100；实际修复为 [PR #102](https://github.com/MainQuestAI/Deck-Master/pull/102)（#100 已被 Dependabot 使用）。
基于 PR99 `c01151a95065fcfcb3577b6a8fdc05b548118b3b`，其父增量 PR98 为
`7662a11d19b61ff9a4341cc67e8b01258b9e576d`。独立分支 `codex/v1-rc-closure`，
PR base 为 `codex/webui-usability-v1`。实施前两份 HEAD 已实时核对一致。

目标：关闭联合评审两组 P1、五组 P2，完成工程、浏览器、最终安装包与真实单页闭环。
RC 就绪还要求用户对最终 UI 和风格样例的视觉确认；工程和 Host 自审不能替代。
版本保持 `1.0.0.dev2`，本轮不合并、安装到真实 HOME、激活或发布。

入口：[开发卡](TASKS.md)、[验收与证据](ACCEPTANCE.md)。继承现行 AGENTS、DESIGN、
Web UI v4、usability-v1 与 iteration 规格；本轮不修改长期规则。
截图按活动规格：1–5 张、七维规范、安全综合示意、固定目标试作及显式采用。

## 最小数据增量

- `ui_draft.v1.content.requirement` 可选：`text`、`edited`、`annotation_refs`、`basis`。
  basis 为 `page_id/layer/revision_id/page_ref/artifact_ref`，沿用对象引用格式。
- 私人笔记 `content.text`、意见 `content.annotation` 与要求分别保留。精确依据恢复选择；
  不适用的原要求、意见引用仍保留，禁止提交并提示重新选择。取消全部选择不清空手工要求。
- 向当前版本复制只保留各用途文字，生成新 draft；范围重置 page、区域清空、章节和意见引用清空。
  要求 basis=null，需重新选择适用意见后生成计划；旧稿保留。
- 新待核实 payload 可选 `display_context`，冻结 instruction、annotation_refs、targets；
  纳入个人 `payload_digest`，不改变业务 request、request_digest 或重放身份。
  旧 payload 按真实原请求展示并说明缺少要求正文，不用当前输入猜测。
- 既有草稿 `content` 与 pending.payload 已允许上述可选数据；不新增端点、schema 版本或 writer 等级。

客户材料、草稿恢复文件、调用记录和导出原件留在仓库外。

## PR102 追加恢复修补 · 2026-10-05

复核基线 `9c21add928e15deef1a3fe8ebdc09eb6e69d94f9`。两份评审认可主体修复，
但 R02 重新打开以下两个 P2 与一个状态小项；编号以 `PR102-` 为前缀，与前轮编号区分。
继续追加到 PR102 原 worktree/分支/base，维持 Draft、`1.0.0.dev2` 和原发布边界。

- `PR102-P2-01`：保存的 requirement 引用和 basis 是权威，selected 只作意见解析投影。
  改文字不重写引用/依据；显式选入或取消才更新。列表读取中/失败不阻止可保存文字，
  但计划等待成功解析；失败可重试，真正缺失或不适用仍保留原记录、提示重选。
- `PR102-P2-02`：真实 ETag 冲突分别比较私人笔记、意见正文、修改要求及两侧固定依据。
  打开时冻结完整快照，下载与新 UUID 另存使用本机快照，项目原稿不被覆盖。
- `PR102-P3`：复制旧稿只含要求时也标 dirty，可通过已有保存入口落项目；旧范围仍清除。
- 小项：冻结请求/当前草稿标题准确区分；本页候选提示固定阅读版本及新结果入口；清理无用导入。

不新增端点、永久对象、schema 版本、writer 等级或请求摘要语义。复用既有 content 扩展，
旧字段缺省按空读取。代码修复分两组，证据索引随第二组补齐。
新增回归经真实本地服务，只有网络延迟/失败受控；最终 wheel/sdist 及独立安装回归记录来源。
既有真实单页制作、其它29页保持、原生Esc记录继续有效，本次不重做整稿或调用模型。
