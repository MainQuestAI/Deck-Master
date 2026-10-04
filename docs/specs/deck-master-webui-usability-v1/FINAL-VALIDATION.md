# 最终验证记录

2026-10-04。PR #98，base `main@6996a29b1792e39199cf0ae968deaaaba381d9e1`，分支 `codex/webui-usability-closure`。最终产品源码冻结为 `05b0d875d2cc890966ab10d730bf62d072ae871b`；后续验收文档及补充测试提交不改变产品字节。

## 已完成的工程验证

| 验证 | 结果及证据 |
| --- | --- |
| 六项 UX 修复 | 三视口实际浏览器、键盘/焦点/意见/固定历史/候选比较检查通过；[设计 QA](DESIGN-QA.md)、[Design Review / QA-only](DESIGN-REVIEW-QA.md) |
| 完整核心及实际渲染 | `88da633` 完整核心 1273 passed、86 deselected、22 warnings，356.13 秒；未吞掉警告。最终产品的 Python/JavaScript/schema/方法/核心资源均与该提交相同，仅历史比较 CSS 一行变化 |
| 最终必需浏览器 | `05b0d875` 90 passed、1273 deselected，191.02 秒；含新增 4 个 SVG/PPT 两侧同行断言，保留修前失败 |
| 真实 Host | 独立 30 页副本实际截图分析、四次真实 imagegen 调用、两页合格候选及明确扩展、第二轮正文/SVG修改；失败、取消及重做记录保留，非 fixture |
| 最终安装后制作 | 最终 wheel、新端口/新浏览器恢复后重新编译 30 页 PPT、LibreOffice 渲染和正文回读通过；六维 Host 自审、正常续跑及三个用途导出；[真实业务报告](REAL-BUSINESS-VALIDATION.md) |
| 原生对象与导出 | 第 2/3 页 33/43 个原生 shape、0 picture；三用途各 153 个目录文件和 ZIP 内文件摘要核验通过 |
| wheel/sdist 与隔离安装 | 干净官方源码包、两种隔离安装、资源身份、离线 UI、私有安装器激活/回退通过；[包验收](PACKAGE-VALIDATION.md) |
| macOS 本机入口 | 用户真实完成成功/取消；路径保留、按钮恢复及项目打开通过；最终包相关三文件与该实测 wheel 字节一致，入口回归通过 |
| 独立复审 | 核心复审 CR-01/CR-02、设计 DQ-01–03 和历史 DR-03 已关闭；未发现本次复审范围内未关闭 P1/P2，独立性和未测范围逐份说明 |
| 截图边界直接补验 | 实际 HTTP 拒绝超 64 MiB Content-Length、有效 32,008,000 像素 PNG，项目指针不变；真实浏览器丢失二进制上传响应后核实同一操作回执，只发布一个参考；新增两项 2 passed（2.40 秒），所在两个模块完整 10 passed（15.37 秒） |
| 性能与完整长跑 | 合成 300 页 × 5 候选 × 3 Attempt；100 次暖摘要 p95 62.759 ms；实际 30 页首屏 909.55 ms；完整 1200.003 秒、120 样本，中段/末段各 30 样本 heap 中位 19.444→19.849 MiB，增长 2.083%；池峰 6/2/60/3，错误为空；新增比较/历史分页/截图分析/拆解各 10 轮；[性能报告](PERFORMANCE-VALIDATION.md) |
| CI | 产品冻结 `05b0d875` 的 14 项检查成功；最终验收文档/补充测试提交的当前 head 检查以 PR #98 的 checks 为权威，收尾归档在 PR 和私有证据，不以旧 head 的成功替代当前 head |

真实业务输入与私有截图、调用原始记录、导出不入库。原验收稿保留，原本其它工作台服务未改动。没有执行真实 HOME 安装。

## 发布待完成项

- 用户对新版 UI 与第 2/3 页风格样例的实际视觉确认；已给出可查看的最终工作台与实际 PPT 预览，尚未将工程确认记为人类认可。
- 合并前当前 PR head 的全部 CI 必须成功。产品 head 与最终验收提交分别核验，CI 归档通过 PR 自动记录，不为写入自身提交摘要而循环改源码。

以上必需项全部闭合前不合并或发布 RC，版本仍为 `1.0.0.dev2`。本轮授权的 RC 目标仍为包 `1.0.0rc1`、tag `v1.0.0-rc.1`、GitHub prerelease；此文档不是发布记录。

## 私有证据索引

仓库外本轮 evidence 目录保留 `core-88da633.log/xml`、`browser-05b0d87.log/xml`、核心原始反例与独立修后探针、Design QA 前后截图、最终 `post-history-layout-fix/` 官方包/离线/安装/回退/真实工程 UI 记录、`installed-after-final-recovery/` 实际编译/回读/审阅/三用途导出完整性，以及 `final-native-entry/` 原生窗口响应。操作记录中的拒绝和失败保留，不覆盖历史绿色报告。

最终压力原始记录保留在 `pressure-usability-qualifying-05b0d87/`，含 HAR、采样、四项新浏览路径及截图；新增直接边界回归记录为 `upload-boundaries.log/xml` 和完整模块 `upload-boundaries-full.log/xml`。前三次因产品修复而中断的长跑标记 `source_superseded`，未计入最终通过；140 秒烟测也未计为 20 分钟。长跑没有强制 GC、清空缓存、提高阈值或生图调用。
