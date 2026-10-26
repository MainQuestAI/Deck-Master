# PR #189 审查修复记录

基准：`c217d3423dec0b7400ec92249441438769d5136c`。本轮按已确认方案实施，未合并、发布或迁移实际 HOME。

## 实施与边界

| 项目 | 实现与验收入口 |
| --- | --- |
| 本地文件核验 | HTTP 拒绝 file_path；CLI/SDK 描述符核验普通文件、长度有界分块读取、前后身份检查、结构化错误。delivery 只匹配当前合法输出；review 诊断还允许已提交历史原件的长度，识别旧稿仍报告 blocked，不能升级为交付许可。`test_selected_file.py` 与旧稿重编译四参数回归。 |
| 原图升级兼容 | 历史上下文按其实际冻结字段投影，新任务保留显式 text_visibility。未知版本拒绝，正文/设计变化仍失效。`test_pr189_visibility_compat.py`，另有精确 base→当前源码公开重建派发对照。 |
| finding 生命周期 | 当前有效替代终点决定关闭；重新打开、分叉、循环、缺证保守处理，无关 finding 和失效分支不影响有效修复。`test_pr189_finding_endpoints.py` 与公开服务 reopening 测试。 |
| 授权与固定交付 | 正常完成可交付精确旧文件；来源/适用当前请求暂停、拒绝或撤回阻止新交付。撤授权不等于暂停整个 request。方法更新不复活旧授权，也不重签已替换请求的历史 Task。 |
| 正文职责 | 计划与重签共享真实零调用 context；input_revision 分为校验、推导、trial、proposal、adoption，保持原 CAS、回执、响应和校验。公共审查状态投影不持久化批准。 |
| 摘要读取 | 一次请求共享经过验证的祖先/操作索引，下一次请求重新验证；不缓存跨请求授权结论。历史损坏仍可检测。 |
| 安装事务 | 新增 status 和 recover resume/rollback/abandon；只可信 journal 可终止；冲突内容、备份及日志保留，健康状态仍提示 conflict。仅清理可证明归属的临时 inode。旧 v1 可读，abandon 使用 v2。 |
| 工作台维护 | 控制读失败显示未知，不伪装为 0。成功请求按 operation 清理副本，未知/未提交输入保留；支持恢复、下载、显式删除。 |
| 合同与 CI | 删除不可达 bullet_item 定义并同步镜像；补 style v3 内嵌 intent 描述与一致性回归；历史专项 workflow 改为手动触发。v1 保持加法兼容，不声称未修改。 |

#188 的已采用正文、异步轮询隔离和 content_q 阅读恢复保留为回归。RP-02 原有 trial/auto 正反对照继续执行，没有重新描述成未实现。

## 性能证据

[原始重复测量](summary-performance.json)：同一合成项目，增加 100 条已提交历史，当前摘要输出逐项相等；2 次预热后 8 对交替样本。仅切换基准 receipt/snapshot 读取实现，其余为当前实现。CPU 中位数约 24.214→19.571 ms，wall 24.279→19.592 ms，coverage validation 从 2→1。不是整条渲染、真实 Host 或用户体验收益结论。

## 验证记录

以下保留首次整合诊断，不代替最终候选验收。最终状态以 PR 当前提交的检查及本轮独立 QA 报告为准；失败记录不被重跑或不同环境结果覆盖。

- 首轮整合 unit：3973 passed、27 failed、142 errors、2 skipped。包含 macOS `/tmp` 解析为 `/private/tmp` 被安全防护拒绝、旧 editable 子进程身份，以及方法重签与 schema 镜像整合缺口。后两项已修，最终测试使用独立当前源码环境和不含 private 的临时根。
- 首轮 render：123 passed、15 failed、1 Frozen A skipped。其中本轮引入的旧稿 hash 诊断四参数已修并通过。
- 其余 11 个 render 失败在精确 c217d342 归档源码、相同本机工具下同样失败：3 个 preview 全白、2 个 native 正负例像素全白、6 个 glyph 边界。只证明不是本轮新增回归，尚未判定本机工具或既有跨平台根因，不能记通过。
- 安装批专项 260 passed、邻接及隔离 wheel/sdist 130 passed；前端维护专项 65 passed。各组有重复覆盖，不能累加为独立用例总数。
- CI 配置规定的 Ruff 范围 `src/deck_master tests/rebuild` 通过。额外全仓库扫描遇到两个既有 campaign 文件中 `; match(...)` 的 Ruff 解析问题，未修改无关代码。

本轮没有降低断言、尺寸阈值或超时；既有 missing-receipt mock 仅补接受新增可选 reader 关键字，原未知状态断言保持。真实 Host/专业产物、S3、Frozen A 外部资源、用户视觉认可及原生目录选择器取消验收继续单列。

## 实现提交

- `5f390ad8` / `f45b4a88`：有界文件核验、HTTP 边界与错误码。
- `6a3a9433`：旧冻结原图契约。
- `c577bee4`：finding 替代终点解释。
- `55cf88eb`：交付控制、授权重签及正文职责整理。
- `d810d82a`：请求内祖先索引。
- `ec37a3ce`：安装恢复与清理。
- `fa74a883`：未知状态、文字副本、schema 与专项 workflow。
- `df50fab7`：保留旧稿交接诊断。
- `d78f1a18`：历史任务隔离、合同镜像与界面边界说明。

这些提交保留原审查基准的祖先历史；没有改写旧提交或用户项目。
