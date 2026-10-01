# U01：固定版本待办对象与精确导航

基准 `de9dcd6a03cd9fb5fd8252478befbe04bf22a91f`（PR83 最终合并）；工程提交 `7807fc5c812c4d6e578153cd0470cb13d0b801b6`。U00 托管 run 36889969387 四组合单元、渲染、浏览器/安装及汇总全部成功，PR84 合入设计分支后文件树与绿色候选一致，PR83 已合入主线。

## 实现与验收

| AC | 实现与证据 |
|---|---|
| U01-1 | 同一 summary 事实组装过程在内部保留成员；顶层聚合与逐页 action 都可解析。业务对象去重，损坏成员仍计入结果；响应分页，不把目标列表塞进轮询摘要 |
| U01-2 | 单任务/单候选直接打开；多对象先显示固定版本列表，点击指定成员进入指定任务或候选。正文整稿变更集单独进入 content + candidate 比较，没有伪造 page_id；可按映射展开基准和候选全文 |
| U01-3 | 测试同标题页、未知/跨项目/旧 action、损坏候选和 review、缺失候选业务身份；可读对象继续展示，不从 hash 推断 ID。跨项目 URL 保留已显示工作面并给原因 |
| U01-4 | URL 保留 project/revision/page/layer/task/candidate，新增受验证的 action/review；对象比较绑定 revision。历史候选列表与详情不再读当前版本，采用控件禁用；个人 position schema 保持原有字段 |
| U01-5 | 300 页核心样本解析只返回指定分页，不调用完整 history view；调用前后 summary 完全相同。此项是工程读取检查，不是 300×5×3 长跑 |

接口先在 [INTERFACES](INTERFACES.md) 定义，再交付活动 schema、镜像、服务、HTTP 与消费者。旧核心明确显示“通用入口”，聚合事项不选择第一页冒充全体。当前时钟超时动作可在所选 snapshot 仍为 current 时解析；一旦成为历史，若缺少固定事实则明确拒绝，不补造历史时间判断。

## 实测

- 完整 Python 3.12 / Node 24 单元组：981 通过、0 skip（[日志](evidence/u01/unit.log)）。
- 新增核心/HTTP 17 项与真实浏览器 6 项：23 通过（[日志](evidence/u01/new-tests.log)）。
- 最终 JS 模块检查与 6 项浏览器：7 通过、0 skip（[日志](evidence/u01/browser.log)）；包含最后的整稿交付焦点路由修改。
- 原有相关读/候选/HTTP/打包边界定向集合 116 项通过；更早无 rsvg PATH 的尝试有 2 项环境 skip，补齐 PATH 后完整重跑通过。Ruff 和 diff check 通过。

[多任务列表](evidence/u01/grouped-tasks.png) · [390px 变更集比较](evidence/u01/changeset-mobile.png) · [机器记录](evidence/u01/validation.json)。新增样本、任务返回和检查记录均明确为合成输入，无模型调用，不是专业制作证据。

本包未改渲染链，继承 U00 真实渲染证据；U01 托管 CI 结果单独读取。最终完整单元执行后仅调整整稿目标的阅读焦点路由，已由最终 JS/浏览器命令补验。批量选择、总览偏好、风格与内容收敛、全工作面异常及最终候选验收仍按 U02–U06 推进。
