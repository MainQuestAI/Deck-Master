# Web UI 审查后修复 · v1.1 实施

本轮接续已讨论的九项审查结果：八项产品整改，AUDIT-F06 只回归。沿用原生 JavaScript/CSS、当前 OpenDesign 产品覆盖、项目入口及五工作面，未重开旧 v4/W 系列工作包。

## 准确基线与来源

PR122 已由原执行线程在 2026-10-18T15:43:08Z 合并。该 PR head 为 `a16d5617e71dcdfa7590fca3502bd6bf5c9c3799`，两轮各七项 CI 全部成功。新开发基线为实际 merge/main `c2e6d7438a1b1270e2d1a72341c86166c0db5432`；分支 `codex/webui-audit-repair-20261018` 使用独立 checkout，原项目未提交修改保留。

以下是本机既有方案原件的路径与内容身份；原件未改写。第三份纠正前两份的技术细节，本目录记录其实施结果，未重新选择产品方向。

| 既有方案 | SHA-256 |
| --- | --- |
| `output/playwright/webui-audit-20261015/REPAIR-PLAN-v1.md` | `ec4cb0538a5d9e428c338874a0afedfe18ec6c160c8f9a6d1a24f80bee69bdfe` |
| `output/pr121-plan-review-20261018/PLAN-DELTA-v1.1.md` | `ccd41ed6c7a2b81f83afe19a44a40d3bdf8c37bcb29cb892344cb062f23db5ab` |
| `output/webui-plan-pr122-recheck-20261018/REVIEW.md` | `69ab5443f701bef4fad4c8c0f967467d5763f26e089d2b55e6f61e4ae332c8df` |

## 已定实现与边界

| 项 | 本轮行为 | 实施落点 |
| --- | --- | --- |
| AUDIT-F01 | 待办标题写明真实原图/SVG/PPT层、页数及页范围；补齐入口只导航；内容完成态保留 | `overview.js` |
| AUDIT-F02 | 精确识别 legacy initial/import_draft/缺 intent 模板；未知主层中性，原文在详情与搜索完整保留；现代精确摘要保留用户原因 | `run_desk.py`、`run-desk.js` |
| AUDIT-F03 | “添加材料”和“修改任务要求”显示各自字段；共同草稿提示另一类变更，确认前列全差异；协作请求仍独立 | `content-sources.js` |
| AUDIT-F04 | 2–4页条件及禁用原因可见并关联按钮；分段组仍直接包含按钮，完整选择不受筛选影响 | `gallery.js` |
| AUDIT-F05 | 消费既有 delivery-eligibility；核对中/受阻/失败/缺能力禁用正式生成，审阅/工程独立；具名缺项及中文下一步；绑定稿件、控制、口播与实际文件 | `delivery-desk.js`、`collaboration-desk.js`、共享工程判定 |
| AUDIT-F06 | 保留现有完整性详情，实际验证三用途ZIP下载哈希、历史版本及丢失回执恢复，不重复实施哈希移位 | 既有结果组件及回归测试 |
| AUDIT-F07 | 在同一画布/工具节点周围压缩工具行与窄屏翻页，不重建标注/草稿；面积、字号和触点同时满足 | `studio/reading.css` |
| AUDIT-F08 | 用户可见子区与空态改为“任务记录”；既有URL/恢复键/筛选/分页不变，定位测试同步 | `views.js`、`candidate-desk.js` |
| AUDIT-F09 | 新建表单专用类限定实际dialog与queued-modal；标题/操作区固定、表单内部滚动，九字段及条件必填保持 | `launcher-ui.js`、局部CSS |

### F05 中实际发现并关闭的核心反例

矩阵中确实复现：六项检查已有 pass，但 PPT 元数据绑定另一份 SVG 时，只读预检返回 ready，而真实导出的既有 `_gate` 因 `basis_changed` 拒绝。原因不是 `export.delivery` 与 `delivery.historical` 名称不同：两者保持原有同组授权。

`exports._engineering_ready()` 提取的是原导出门禁的现有条件。预检现在读取同一固定控制版本的 `_facts` 并复用该谓词，补回遗漏的产物依据检查；POST仍重新核验当前控制并串行发布。`delivery-eligibility.unresolved.gaps` 只增加已有事实的诊断投影，无存储合同/迁移/授权政策改变。没有新增 export-facts 门禁字段，也没有在前端重算准入。

`test_webui_delivery_parity.py` 用五种口播选择（含默认）×十种真实服务状态作50个同依据反例；实际公开 PPTX 字节和策略与预检对应。数据及工程检查是明确L1合成夹具，不能称为真实专业认可。

## 验证与状态

完整逐项清单见 [ACCEPTANCE.md](ACCEPTANCE.md)。清单将原方案与最新复核拆为50个实施核对条目；该数量不等于RC3的AC/CQ编号或唯一测试用例数。验证范围及可复跑入口见 [VALIDATION.md](VALIDATION.md)。

同一24页样例、p01原图、适应窗口、scrollY=0、保留示例横幅的实测：

| 视口 | 修复前画布top/height | 修复后top/height | 工具标签/触点 |
| --- | --- | --- | --- |
| 1440×900 | 517.875 / 362.125 | 417.781 / 462.219 | 13px / 44px |
| 1280×800 | 517.875 / 262.125 | 417.781 / 362.219 | 13px / 44px |
| 390×844 | 639.375 / 184.625 | 560.188 / 263.812 | 12px / 44px |

未以滚动、裁图、删除必要事实或缩字号满足面积；主要桌面意见编辑器与保存动作继续在首屏。真实长项目标题另测不溢出和协作控件可操作。

本轮只开发至独立Draft PR并跟进其准确head CI；不自动合并该PR、不发布、不激活真实HOME或日用安装、不迁移客户项目、不改权限、不调用付费生成API。历史效果实验与合并后bot的文档意见不新增为普通UI开发门槛；未虚构签署、哈希或人类认可。

新建弹窗也以相同九字段测量，未填字段或创建项目：

| 视口 | 原创建按钮 top/bottom | 修复后 top/bottom | 修复后表单 client/scroll 高度 |
| --- | --- | --- | --- |
| 1440×900 | 1243.391 / 1287.391 | 807 / 851 | 674 / 1003 |
| 1280×800 | 1243.391 / 1287.391 | 707 / 751 | 574 / 1003 |
| 390×844 | 1412.266 / 1456.266 | 751 / 795 | 618 / 1171 |
| 390×500 | 1412.266 / 1456.266 | 407 / 451 | 274 / 1171 |

前后测量JSON与三个标准视口及低高度截图在 [evidence/](evidence/)；均为本轮实际Chromium合成工程样例，未复用历史审查截图。
