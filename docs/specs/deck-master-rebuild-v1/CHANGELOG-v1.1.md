# v1.1定向修订说明与Codex复核入口

日期：2026-09-16。依据：[用户转交的Codex v1.0审查](sources/codex-v1.0-review.md)。本次修订不重新研究或重写总体方案；没有访问本地产品仓库、修改产品、删除、安装、创建分支或实施新API。

## 裁决

R1–R6全部接受；对应补充集中到现有五对象、15章、25任务与75项拟建目标。没有新增永久对象、注册/预算平台或原生chart实现。规范与合同名称仍为预实施版本，包版本v1.1取代v1.0作为建议活动基线。

| 审查项 | v1.1明确动作 | 主要落点 | 验收/例 |
| --- | --- | --- | --- |
| R1 来源未知 | original_sha256可null/省略；已保存extract/媒体hash仍真实必填；全零拒绝；未知不能追认补来的候选原件 | 03.2/03.11、12.2–12.3、document schema | AC-L04；missing-source |
| R2 制作输入 | Document.design_context为唯一版本化画布/语言/字体/样式/资产；Page只能明确覆盖；asset角色保存字节；style_ref指ID；临时相对路径只在接收时解析 | 03.3a、05.1、06.1/06.4、08.8；Document/Page/Artifact | AC-K14/K15、AC-S13、AC-B01；design-context |
| R3 依赖/额度 | T20依赖T13，最终T25祖先覆盖T01–T24；T01用L07建立清单，T24完成L05引用归零；项目事务分配allowance与begin/settle | 08.6、09.2、14.2；Task与task-list | AC-L07、AC-S11/S12；call-allowance |
| R4 UI首次可见 | 主Skill首次正文页被接收就自动view --open；同项目复用；无浏览器与服务失败分别如实；不是等PPT全部完成 | 09.5、10.4/10.6、11.7、Host例 | AC-U03、T05/T14/T20 |
| R5 编辑边界 | 首版为可编辑形状与文字；不承诺Office Chart编辑数据/原生Table行列；PPT Artifact与UI/导出声明 | 00.5、06.7、07.7、10.2；Artifact | AC-K16、AC-K12 |
| R6 最早切片 | start_after/early_delivery允许先试做，depends_on仍为整项完成条件；T10.min真实三方对照与T12.min单页改先行，最终范围不缩水 | 01.8、06.8、14.2；任务/工作包/清单同步 | AC-V07；T10/T12 |
| 分支 | codex/rebuild-mainline-v1，仍未创建 | 01.1 | 仅方案命名 |
| 往返合同 | 稳定atom ID、fixed真实复查replaces链、唯一kind结果信封完整正反例 | 03.10、07.9、09.7、14.8 | AC-C03、AC-R06、AC-S14；roundtrips |

## 本轮额外收紧但不扩项

- 内容版本恢复不回滚已消耗/未知调用或取消事实，防止restore重新获得额度。
- 先实现T13.min再真实外部调用，避免把“提前试做”误解为先忽略用户限额。
- style默认在create时固化；中间模块不各取默认。单PPT物理页尺寸一致；Page样式覆盖不能改变整稿物理尺寸或扩大资产外发权限。
- 字体选择与实际字体文件指纹区分；Spec/公开发行不附字体二进制。
- Review示例和静态信封通过只证明文档格式/引用，未声称实际Host审阅或编译成功。

## 原范围与数量

仍为15章、5工作包、25任务、5类永久schema、177旧scripts、58旧contracts、122旧顶层tests、75项拟建目标。验收矩阵从83条增为90条，新增项用于上述定点缺口，不对应90份Deck。全部产品验收仍planned_not_executed。

## 使用方式

完整v1.1 ZIP替换活动Spec包；原v1.0留作历史，不混用旧合并手册/任务表。先读本文件与START_HERE_FOR_CODEX.md；复核优先看五Schema、08.6、14.2、任务图及roundtrips。

PACK_VALIDATION.json记录本次真正执行的文档检查及边界。它不代表产品测试、安装、字体匹配、自动UI、并发调用限额或专业可用已验证；这些需要Codex在实施后核验。
