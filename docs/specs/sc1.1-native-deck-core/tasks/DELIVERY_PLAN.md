# 开发组织｜三个工作包、五个增量PR

## 分支策略

本次在线基线中PR30尚未合并。优先从`4977f89`或其已核验最新后继建立新worktree/修订分支，以PR30 HEAD为增量评审基线；若PR30未合并，采用stacked PR，说明依赖，不把base-to-main的全部SC-1代码再次当成本轮新增。若PR30已合并，从包含其成果的main开发。

不得因需要新baseline强制合并PR30；不得自动push/merge、force push、清理旧分支或删除未提交工作。用户要求的是本轮Spec，不是已授权修改仓库。实际开发时按仓库贡献流程提交。

## 五个建议PR

| 交付段 | 任务 | 依赖 | 必须有的合并证据 |
|---|---|---|---|
| N1 内核提取与契约 | ND-01 | Q0 | compiler不读HOME/不调用PPT Master；七类差分；状态与契约映射 |
| N2 默认路由与独立安装 | ND-02 | N1 | native默认；manifest/doctor/next-step一致；none真实CLI；无外部目录/绑定的安装真编译 |
| N3 公共内容到图片/SVG主链 | ND-03 | N1+N2 | public narrative/Package→lock→图片→SVG，不重复MBB；真实宿主两页；已批准SVG不再问图工具 |
| N4 门禁、修订和审批 | ND-04 | N3；部分测试可并行 | 精确语义门、实际内容指纹、缺门路由；多文件原子、迟到/取消、预算、最终批准 |
| N5 迁移与整轮验收 | ND-05 | N1—N4 | 8—12页实际Solution流程、七类页、原生编辑、旧Run/数据回滚；SC-1验收映射 |

五段是执行建议，不是必须创建五个远端PR；若并为一个PR，仍需独立可审查提交和上述证据。每个PR展示已经完成/待验证/未实现，不因单元测试绿灯提前宣布整轮完成。

## Q0（开工检查，不单独扩成长期项目）

核对HEAD差异、用户修改、PR30真实测试基线；绘出新默认入口到实际函数的调用图；盘点高密度纯编译依赖；确认schemas与ready状态冲突；记录宿主/renderer/字体/真实素材可用性；登记全部旧约束替换位置。先加反例测试（无binding、none parser、语义误匹配、第二文件中断），再实施修复。

## Agent分工

Compiler Agent只改native core与兼容adapter；Workflow Agent负责CLI、route、questions、actions和state；Quality Agent负责readback/gates/approval联动；集成负责人单点收口共享manifest、stage-contracts、CLI、final-readiness与release。不得并行各写一套registry或编译器。

并行工作基于稳定编译contract，业务事实/主线contract不复制。每段交付source SHA、文件、入口调用、测试、差异、已知未闭环与验收ID。真实工具缺失要列实际依赖，不允许以PPT Master绑定作为native替代条件。
