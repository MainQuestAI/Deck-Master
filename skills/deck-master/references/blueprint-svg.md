# Codex 蓝图执行方法

当前版本以 **Codex Desktop** 为唯一已验收宿主。蓝图通过当前会话内置
ImageGen 工具生成；Deck Master 本地包不连接 Provider API、不读取 API Key，
也不声明 Claude、OpenCode 或其他宿主兼容。

收到 `kind=blueprint` 的任务后：

1. 读取 `production_request.prompt`、完整 Page、解析后的设计配置和允许资产。
2. 用 `task start` 领取任务，再用 `task call begin` 消耗本任务的 reserved allowance。
3. 将实际提交给内置 ImageGen 的 prompt 原样保存。不能用后来重建的 prompt 代替。
4. 保存工具返回的原始图片；记录可得的 invocation ref。工具未报告费用或 token 时写
   `not_reported`，不能估算。
5. 实际查看图片，核对页面模块、数值、方向关系和明显文字偏差。原图文字不作为正文来源；
   SVG 重构始终从 Page atoms 恢复精确文案。
6. 用 `task call settle` 记录 consumed / not_sent / unknown，再用 blueprint 信封提交图片、
   实际 prompt、来源和限制。调用已经发送但图片采用失败时仍为 consumed。

当前会话没有图像工具时保持任务 `awaiting_host/needs_tool`。不得改走 fixture、本地占位图、
Provider 配置或向用户索取 API Key。
