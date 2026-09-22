# WP-A｜单产品独立性任务卡

共同约束：只修改相关安装/运行时/Skill/测试；共享 CLI 与 manifest 经集成 owner 合入；路径/调用是否存在需要 Codex 核验。新增测试名由实现确定，必须映射验收 ID。

## Q0 基线与契约冻结（先决任务）

输入：固定 main、现有运行环境、本包、最近实际 Spec。
输出：baseline-audit、reuse-map、schema-migration-map、capability-migration-matrix 初稿与 UAT 可用条件。
工作：核对源码/本地 SHA；定位标准/HD 的实际 Page Package 调用；记录旧失败；检验源码路径/Schema；列出未决工程参数。
禁止：读完整源码前将旧问题当新 bug 重复实现；重置工作区；替用户删除旧依赖。
验收：所有后续任务有具体接入位置，不再仅凭“模块存在”推断能力。

## A1 托管组件锁和方法资产盘点

依赖：Q0。
涉及：`scripts/skills/installer.py`、产品 capability manifest、`product_capabilities/`、release/lock 相关模块。
实现：固定来源/包 hash/版本、契约、环境、许可证与所有权；对四项能力逐条做方法/代码/参考资料映射；扩展 release 分发。
验收：不能接受浮动 latest、开发机绝对路径或只复制 SKILL.md；同一 lock 可重复安装；公开报告脱敏；PPT-Deck-Pro-Max 第三方分支 SHA 桥接（`DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE`）退役后生产生成不再依赖该仓库分支存在。
测试：A-01、A-02、A-11。

## A2 PPT Master 标准后端托管

依赖：A1。
涉及：`scripts/runtime/builder_backend.py`、标准 build/render、安装器。
实现：从固定产物安装完整所需后端；用适配层承接上游；解析相对运行路径；真实 smoke 写入版本绑定的状态。
验收：旧后端目录不可用仍能生成两页含文字/业务图形的真实可编辑 PPTX并渲染；不经环境变量伪报 ready；标准仍是默认。
测试：A-03、A-04、P-01。

## A3 PPT Library 与套件方法托管

依赖：A1。
涉及：`scripts/tools/ppt_library_client.py`、`scripts/runtime/library_status.py`、相关 product_capabilities/Skill references。
实现：可执行程序与环境由产品管理；真实命令从 lock 解析；asset database 与 release 分离；对应旧专业方法纳入按需参考。
验收：PATH 无独立 ppt-lib 仍能真实搜索授权测试资产；旧库不被重建/删除；Skill 不再跳转到缺失外部方法。
测试：A-05、A-06、A-12。

## A4 按任务就绪与无历史库生产

依赖：A2、A3。
涉及：capability manifest、setup/suite status、agent-doctor、sourcing/runtime resolver。
实现：execution plan；旧 readiness 明示兼容；library none 的真实 generate 决策；真实检索故障与无命中分开；diagnosis 不受生产依赖阻断。
验收：none 不调用 Library、无 fixture selection、页面全覆盖；缺 ImageGen 不阻止 standard；所需组件缺失必须显式阻断。
测试：A-07、A-08、A-09、A-10、P-02。

## A5 问题 authority、路由和继续执行

依赖：Q0；与 B4 同 PR 接入。
涉及：`skills/stage-contracts.json`、`scripts/workflow/questions.py`、decisions/next-step、AGENTS 与相关 Skill。
实现：typed trigger/answer_schema；材料已答复自动引用；Agent 编写核心主张/反方疑问；精确决定依赖；统一等待 Agent 不等于等待用户。
验收：正文已给的信息不重问；“没有禁词”对对应问题有效；真实交付批准不能由 Agent 填；局部样式变化不重问业务目标。
测试：W-01—W-05。

## A6 安装、迁移与回滚集成

依赖：A1—A5、B/C 主链完成。
涉及：suite migration/install/uninstall、release verification、宿主安装文档。
实现：隔离旧目录、完整 fresh install；external real directory 保留；升级失败回退；用户数据分离；已支持宿主按实际能力验收。
验收：所有 A/M 用例有实际证据；软件回滚不删除新数据；未知宿主支持不虚报。
测试：M-01—M-06、A-01—A-12。
