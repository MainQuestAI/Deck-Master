# PR120 本机修复记录

2026-10-17，基于 `229df7e07d63db99e30446a043b9c7097480760d`。
本轮从本机更新原 PR120，保持 Draft；不合并、不激活日用安装、不迁移真实项目。

## 修复与证据

| 问题 | 修复 | 定向证据 |
| --- | --- | --- |
| P1：规划父授权后设数字上限未约束既有子授权 | 历史数字根不变；新增调用同时受当前 authority 祖先数字上限约束，跨根派生消费按 identity 去重 | 新增旧规划父显式 0/1、中间父、已 held 调用、兄弟及跨根重试回归；预算组合 57 pass，最终祖先 14 pass |
| P2：列边界合法字形被空文本框误拒绝 | start 左闭右开、end 左开右闭，middle 严格内部；仅裁剪测量为空的余量 | 四个新增边界回归先 fail 后 pass；真实 native compile/readback/PDF 字形与锚点检查；表格/readback 组合 71 pass |
| P2：丢回包后重开预算窗口无法核实原请求 | 统一按钮状态；冻结原请求核实不依赖新预算预览；迟到响应仍服从冻结状态 | 桌面/窄屏、关闭重开、刷新、迟到预览及既有候选/政策 browser 组合 18 pass；重放字节和 operation ID 不变 |
| P2：feedback 接纳前后条件互斥 | 分离 scoped 观察与未接纳读取；反馈读取正式接纳事实，继续校验 raw/observation hash | 合成事件明确标注；controller/recorder 组合 93 pass，包含一次交付/必要返修及拒绝负例 |

只读复审发现首轮预算修复会把独立 candidate 数字根的消费扣到旧根，
已先补出公共 grant/dispatch 失败回归，再恢复旧 local accounting 的 chain 边界。
最终候选/内容候选/预算组合 97 pass；该新负例及跨根调用两个独立复核用例 2 pass。
本轮候选额度语义不变。

## 兼容与依赖

- 专用 Python 3.12 环境安装当前源码，保留共享旧安装；浏览器使用已验证的 Playwright 1.61 和对应 Chromium。
- 短写注入与交付等待测试直接观察真实文件描述符，不再读取 Linux 文件描述符虚拟目录；不替换实际锁、不跳过原子写入断言。
- 表格测试按可见字形而非尾部空格定位，保留源文字、原容差与 Runtime 越界拒绝断言。
- 四个 companion 严格同步修复后 recorder SHA256 `ce1b5a9f8deba92f7f2d468b2ddd977c9e2de1438d4bc32e2036eeb12da20cc0`，common controller 字节不变。组合 46 pass。
- 这属于新工具版本。旧正式注册/准入/运行/消耗/失败证据均不改写，不追溯宣布通过；旧工具重放使用原 Git 版本。
- 无公共 API、schema 或 writer boundary 变更，无历史对象迁移。

## 收尾验收口径

完整本机 unit/browser/render、最终提交对应的 7 项 GitHub CI、只读复审和
未激活候选安装验证分别收证。最终状态以 PR 当前 head 的检查与本机交付回执为准，
本报告中的定向通过不能代替这些完整终态。

候选从最终干净提交构建 wheel/sdist/release manifest，使用其自有解释器 `-I`
核对模块来源、四个 Skill 与方法资源哈希，执行隔离项目/Workbench/原生表格验证。
不修改真实 HOME/current、Host Skill 注册或用户项目。

所有输入与结果均为明确标注的中性工程验证；真实模型写作、图片生成、
PowerPoint 桌面编辑、专业审阅和客户验收不在本轮通过结论内。
