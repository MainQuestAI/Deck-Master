# PR91 验证记录

功能代码冻结于 `cc1f16b5bd1f05c385324fbdb72c7f8ebd27371a`。[PR91](https://github.com/MainQuestAI/Deck-Master/pull/91) 的 base 为 `codex/webui-u06-final-validation`，起点为 PR90 `de1dc3e5bc4368416b34215b115419ea37f8b953`。PR90 合并后仍需同步 main、改 base 并复核增量。本轮没有合并 PR 或修改真实 HOME 安装。

## 回归与安装

最终完整回归通过：核心 1039 项、必需浏览器 34 项、真实渲染 33 项；隔离安装断网浏览器 7 项检查通过。Ruff、JS 语法及 diff 检查通过。[本地回归](evidence/local-regression.json)、[安装包](evidence/package-checks.json)。

Python 3.12 隔离安装运行 wheel，未从源码 checkout 借用运行资源。wheel/sdist 的 24 图标摘要、完整许可及 UI 组件检查通过。在安装环境重新读取真实 3 个候选的实际 PPT 与范围检查，Document 未变。断网浏览器覆盖两种宽度、键盘焦点、字体、固定版本下载和公共元数据。

```sh
python -m ruff check src/deck_master tests/rebuild
python -m pytest -q tests/rebuild -m "not render and not browser"
python -m pytest -q tests/rebuild -m browser --require-browser
python -m pytest -q tests/rebuild -m render
python examples/workbench/w12_offline_browser.py --require-installed --out <new-evidence-directory>
```

首次依赖下载遇到 SSL EOF；正常 TLS 下载后准备本地 wheelhouse，最终安装无需网络。验证脚本早期的许可文件名、URL 和像素取整断言已按真实接口与图像解码行为修正；失败日志保留，不计入最终通过证据。

## 范围、候选与事务

覆盖无/重复 ID、多路径、嵌套变换、本地 use、共享几何引用、正文尾部空格、正文/定义/未选对象越界、标准几何篡改、旧提议、Host 能力、取消迟到、重复提交/回执恢复、单页冲突导致整批拒绝及重新预览采用。忠实重绘不能清空整组图标；多对象合并可留下空的辅助位置，但组合必须保留可见原生几何。

采用强制检查范围、实际单页 PPT、回读和原生对象。缓存缺失、失败、损坏、工具缺失、基准变化不误关联，失败可重试。大区域放大达到 2048 画布上限时保持比例，浏览器验证尺寸和图像池边界。

工程导出曾误把 XML 定位的 `path/sha256` 当成文件引用，现已修复并补入真实渲染回归。真实工程包恢复后，3 个采用检查及内容寻址的 SVG/PNG/PPT/回读记录完整，无需原机器候选缓存。旧 PR90 隔离安装明确拒绝 `icon-quality.v1` 边界。

## 标准图标

24 个 Lucide 1.49.0 图标及 butt/miter、round/round、square/bevel 三个变体，在 Python 与 Node 出口各实际编译渲染 27 页。全部为原生矢量，线宽、端点、连接检查通过。完整 Lucide ISC/适用 Feather MIT 声明随包、SVG 与 PPT 保留。来源与 SHA 固定，运行时离线。

证据：[Python](evidence/catalog-python.json)、[Node](evidence/catalog-node.json)。工程结果不生成未经校准的视觉评分。

## 真实工程副本

p04 的显示器、购物车及双轮、医院及十字窗细节、数据库，以及 p16/p28 的重复数据库位置覆盖简单、复合、业务专用、跨页重复四类。Agent 构造完整 SVG，通过真实 Host 领取与结果接收，图像调用为 0。先采用 p04，再生成 p16/p28 各页候选并整批原子采用。

仅 p04/p16/p28 的 SVG 改变，全部 30 页的 Page 与原图引用一致；候选检查未提前推进当前稿及输出。完成这 3 页的现有页面审查链更新，以及 30 页整稿实际 PPT 编译、渲染和回读。Agent 打开全部 30 页实际 PPT 联系表和修改页局部图，正常接收六维最终审阅：内容、蓝图内容、转换、阅读、披露检查为 Host 自检通过；图标语义/视觉取舍为 needs_review，3 个修改页明确登记 needs_judgment。独立性为 false，不替代真人专业或图标视觉认可。

仓库外保存 6 处原图/基准实际 PPT/候选实际 PPT 局部图、3 个单页 PPT、完整 SVG、范围/对象检查、操作记录、整稿及可恢复工程包。原 PR90 revision `966609eb7430412e8427db7d821965fd` 核验未变。公开摘要：[真实制作与恢复](evidence/real-engineering-checks.json)；私人图像和客户材料不入 Git。

## 性能与长跑

明确合成工厂为 300 页、1500 候选、4500 尝试，零模型调用。最终隔离安装独立快照的 100 次暖摘要 P95 为 95.70 ms，门槛 250 ms；1280×800 与 1440×900 各 3 次暖首屏为 0.390–0.425 s，均低于 2 s。证据：[摘要与首屏](evidence/latency-and-first-screen.json)。

正式 1200.00 s 长跑通过，包含画廊/阅读/候选切换、60 次后台领取/取消，以及图标局部对照的正常尺寸/4 倍放大/关闭释放。不强制 GC、不刷新、不清缓存。`[300,600)` 与 `[900,1200]` 各 30 个采样的 heap 中位数从 19,829,060 B 到 20,278,216 B，增长 **2.27%**，低于 20% 门槛；图像池峰值为 **6/2/60/4**，无页面错误。仅 UI gallery/ui-state POST，没有生成、业务提交或采用写操作。[长跑结果](evidence/pressure-long.json)、[全部采样](evidence/pressure-samples.jsonl)。跨代码修改的中断采样不计为正式证据。

功能冻结提交的 [CI](https://github.com/MainQuestAI/Deck-Master/actions/runs/36994757558) 全部通过：Python 3.11/3.12 × Node 22/24 四组核心、真实渲染、必需浏览器与隔离安装，以及汇总 gate。[归档](evidence/ci-functional-head.json)。最终文档提交仍以 PR 最新 head checks 为准。

## 卡与验收映射

| 卡 / AC | 验证依据 | 状态 |
|---|---|---|
| I01 / AC04、09 | 活动契约、接口、writer/Host capability、事务 | 工程通过 |
| I02 / AC02、03 | XML 定位、范围负测、组合非空、共享对象保护 | 工程通过 |
| I03 / AC01、04 | 意见、提议、范围高亮、确认、选页、真实 Host | 工程通过；独立工程验证授权内确认 |
| I04 / AC05、06、09、10 | 实际 PPT、回读、缓存、浏览器、恢复 | 工程通过 |
| I05 / AC07、08 | 24 图标两出口、采用样例、显式选页、原子采用 | 工程通过 |
| I06 / AC11、12 | 真实 30 页副本、回归、安装、性能长跑、功能 head CI | 工程通过；最终文档 head CI 复核、真人视觉认可分报 |

图标视觉验收为 **待用户确认**。工程检查、Agent 观察和工程副本采用均不能记为真人视觉验收通过。PR90 的内容认可与 U06 事实继续独立保留。
