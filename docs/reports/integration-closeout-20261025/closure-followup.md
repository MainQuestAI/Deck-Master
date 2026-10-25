# 来源清理后的收口补充

本补丁接续 `9abdcb7b3af59c02f9991d7871c56d6a2e5b215f`。原候选的检查和下面的复现都有固定身份；补丁后必须以新的 PR HEAD 重跑工程门禁，不复用旧提交的通过结论。

## 祖先授权撤回后的任务门控

对照旧 Draft PR113 时发现一处后续主线未吸收的行为。使用原候选的真实本地 SDK、独立合成项目、零模型/外部调用复现：撤回父授权后，仍 active 的 child 授权被判 `parent_ineffective`，但绑定它的 review/repair Task 仍可启动；已经启动的 repair 仍能接收结果并改变当前 Page ref 和正文。该缺口在 main 也存在，不能因它不是本次 merge 引入就视为可收口。

原因是 `task.start` 和 `task.accept` 依赖冻结的 Task binding，通用 action catalog 不再寻找一份新的覆盖授权；旧 `task_binding_state` 没有核对绑定授权的递归祖先有效性。修复在共享门控处理，未修改原授权记录、Task 身份或历史结果，也未整枝合并旧 PR113：

- 明确传播实际祖先撤回的原因。绑定授权本身或祖先撤回后，新启动和接纳拒绝为 `authorization_revoked`；其他新 grant 不能接管已有 Task。
- 显式允许后台继续的旧 request 同样必须保留有效的绑定授权链。
- 当前祖先记录缺失/不可读、过期或其他无效事实不变成新权限；缺证不冒称用户撤回。既有 binding digest/basis 的 stale 判断优先保留，仍给出重新派发提示；无绑定授权的合法零调用审查不增加生产授权要求。
- 取消、真实消耗结算和已成功操作的精确重放保留。已经发生的调用可以先记真实消耗，但它的 production 结果仍不得在撤回后采用；改 payload 的重放仍冲突。

新增 `tests/rebuild/test_ancestor_authorization_boundary.py` 通过实际 SDK 检查父/祖父/直接撤回、review/repair 启动、正文采用、有效正例、background、替代授权、祖先记录损坏、事实通道与精确重放。该模块也纳入最终安装包 gate，避免只验证源码 checkout。

冻结前新增 22 个回归与 111 个既有 eligibility/resolver/binding/scope/budget 回归合计 **133 passed**；Ruff 与 diff 检查通过。这是补丁诊断，不替代下述最终候选的完整矩阵。

## 安装回归中的折叠标题定位

原候选安装回归为 **519 passed、1 failed**。失败发生在总览页：外层“其余事项与依据”中合法嵌套“产物、审查与下一步依据”，旧 `.todo-more summary` 同时匹配两层标题。仅将两次点击改为 `:scope > summary`，保留展开/收起、交互、几何和离线恢复断言及原时限。

修订后的同一个用例在新源码树及原 `9abdcb7b` 隔离安装包各通过一次；后者的 69 个模块和 static 均经来源审计属于已安装包。两次复跑不是两个不同用例，原完整 gate 的失败日志保持原样。本修正不修改产品 UI。

## 原候选证据与最终验证边界

`9abdcb7b` 的本地完整单元为 **4045 passed、2 skipped、853 deselected**；两个远端真实渲染 job 各为 **138 passed、1 skipped、4761 deselected**。其隔离安装离线检查 **9/9 通过**，三类固定版本下载均完成 manifest 与逐文件哈希核对；wheel 的 292 个产品源文件及 76 个 canonical Skill/方法资源与原候选一致。这些是旧版本证据，不能用来宣称本补丁已通过完整门禁。

最终结果绑定 PR189 的后续精确 HEAD、产品 tree、wheel hash 与 CI job；原始日志和本地报告保留失败与重试，不累加不同阶段的用例数。代码冻结后的完整矩阵、渲染、浏览器和安装验证结果更新到 PR 描述及本地收口记录。

Frozen A 仍有三条独立旧安装兼容用例缺外部资源：notes visual inputs 的 `page` / `content_update` 两个参数，以及 notes transactions 的真实旧 SDK 渲染入口。重复 CI 中的同一 skip 不重复计数。真实 Host/专业产物、S3 效果及用户视觉认可仍按对应卡保留；RP28 的完整工具链 CPU 收益另列工程计量。受限已结算图片复用和外部报告记录/返修接口已经存在，不再写作笼统的“未实现”。

本补丁不关闭源 PR、Issue 或原审查线程，不执行 main 合并、发布、真实 HOME 切换或客户项目写入。
