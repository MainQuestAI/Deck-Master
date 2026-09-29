# W07 候选比较、阶段试作与集合采用前端

前端 PR：[ #54](https://github.com/MainQuestAI/Deck-Master/pull/54)。核心先行 PR #53 已合入 `8de4317c9843347b8075c937e04af54e43d0cbb9`；前端从该 main 独立实施。前端初始提交为 `10164ffaeb1342d2597c560555aa269db7ca8f88`，回包身份修复后的源提交为 `ac3a88a5851501e2e83c5f4f0d3448bfe7aad75c`。此交付为工程切片，`accepted=false`，W07-AC07 的真实交错验证已在 W10 前端验证期间补齐，见下方补证；用户验收仍未代签。

## 当前行为

原图、SVG 和 PPT 单页工作面可填写短要求，选择原图试作、SVG 重建或仅修 SVG。参考原图固定到已提交版本及文件引用，随个人草稿保存和恢复。先预览范围和图像调用上限，再提交原有 ChangeSet/Host 交接；浏览器不代替 Host 生成。历史只读页不能提交试作。

候选页保留“当前采用 / 所选候选”两栏，参考原图为辅助缩略图，可放大。SVG 候选的参考图来自其原始生成基准。切换候选会一起切换图像、请求、Attempt、返回时间和采用目标；读取失败保留旧比较。自动生产推进 current 时不会漂移比较画面，旧计划禁用；明确重新预览才绑定新采用目标。

单页与批量采用共用 `candidates.adopt` 集合事务及 W06 持久请求恢复。提交前冻结 UUID、完整请求与摘要；响应丢失后按原编号查询，不能另发一次采用。任一批量冲突零采用并保留选择，重新选择子集后建立新计划、新操作。采用不是质量通过；整稿按钮使用现有阶段服务，不绕过 SVG 预览和逐页审图。

导航中“查看当前版本”改为重新读取服务端 current，避免将缓存版本误当最新。候选异步读取不能覆盖已切换路由；草稿替换会撤销旧试作/采用预览，避免新输入对应旧计划。参考图弹窗关闭和页面离开均释放图像阅读位。

## 验证

- [15 项浏览器主流程](w07/ui/browser-checks.json)：候选身份联动、固定比较、auto 更新、显式重计划、响应丢失刷新恢复、零重复采用、批量冲突与子集采用、SVG 保留原图、窄屏、整稿前置拒绝。
- [11 项浏览器边界](w07/ui/edge-checks.json)：短要求和固定参考图跨刷新恢复、真实服务派发/返回、图片失败与重试、弹窗释放、待核实期间切换候选的回包归属、历史只读及无 JS 错误。
- [W06 主流程 23 项](w07/ui/w06-regression.json)、[W06 边界 14 项](w07/ui/w06-edges-regression.json)、[W05 15 项](w07/ui/w05-regression.json)回归。W06 的真实 Host 接手分支在本次无模型回归中未重复执行。
- [相关 pytest 62 项](w07/ui/pytest.txt)通过。JS 语法、Ruff、diff 空白检查通过。
- [wheel 资源核对](w07/ui/wheel-assets.json)：26 个前端文件与固定实现提交和当前源码逐字节一致；隔离构建，未安装到 HOME。
- 工厂 `examples/workbench/w07_synthetic.py` 用真实任务/冻结请求/Attempt/候选服务构造明确标记的合成图与本地合成工具事件；不调用模型，不修改实际 Codex session 或 HOME。上述浏览器并发和故障注入属于工程证明。

可复现：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w07_candidates_browser.py --out /tmp/new-w07-browser
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python examples/workbench/w07_candidates_edges.py --out /tmp/new-w07-edges
```

输出目录必须不存在；trace 和请求日志位于 `local-only/`，不提交仓库。

## 真实 Host 证据及限度

[真实检查与前后引用](w07/real-host/checks.json)使用 W02 的真实生成原图副本和一页合成业务事实，在当前 Codex Host 中完成固定参考图 + 中文短要求 → 冻结请求 → 原生 ImageGen → Candidate → 浏览器比较 → 显式采用。成功调用的参考图、提示词、输出绑定全部匹配，试作返回时当前内容引用不变；采用后保留 Page，替换原图，目标下游与整稿失效。

这次实际调用两次。首次 Host 验证脚本传入 macOS `/tmp` 别名，未满足严格规范对象路径校验，参考图覆盖保留为 unknown，结果接收被拒绝；保留调用消耗后取消该任务。第二次新任务使用规范路径，完整绑定通过。没有放宽采集器，也没有将第一次图片伪装为成功候选。

随后真实 Host 对已采用原图手工重建可编辑 SVG，经过正式 CLI 返回候选、浏览器查看与采用，再由原有 continue 生成 SVG PNG。实际读取 Page、原图及 PNG 后登记 Host 自查，记录平面填色和图标简化的差异。显式 assemble 通过真实 LibreOffice/Poppler 回读，生成 6 个文本段、42 个原生形状及按页 PPT 预览。最终审阅仍为 required；不声称独立审查、客户验收或 PowerPoint 桌面可编辑验收。

图像工具使用内置 imagegen；[成功冻结提示词](w07/real-host/original-request-input.json)、[原图比较](w07/real-host/original-real-comparison.png)、[SVG 比较](w07/real-host/svg-real-comparison.png)、[SVG 源文件](w07/real-host/svg-page.svg)、[SVG 预览](w07/real-host/svg_preview.png)、[PPT 预览](w07/real-host/ppt_preview.png)及 [SHA256](w07/real-host/sha256.json)已保留。

**仍未完成：**这个真实 Host 项目只有一页，未证明真实 auto/trial 交错和第二页原图/SVG 不变；对应场景目前只有明确标记的核心/浏览器合成覆盖。W07-AC07 保持部分验证，进入 W08 前必须补齐。W01 的 300×5×3 压力、W10 运行台、W12 安装/离线等仍按各自卡片执行。本轮不切换默认入口、不执行实际 HOME 迁移、不发布。

## 2026-09-30 真实交错补证

使用原真实单页项目的隔离副本，通过 `inputs update` 与真实 compose Host 增加第二页合成内容。第二页原图实际调用原生 ImageGen 一次，保留第一页原图作固定参考；冻结输入与真实原生观察比较为 match。未重复调用已成功的第一次原图生成。新图采用了冻结设计中的蓝色，并重排了三项文本，未宣称参考图风格完全复刻或专业视觉通过。

真实 Host 先领取第二页自动 reconstruct，再领取第一页 SVG trial；trial 先返回，页面当前稿保持不变。在浏览器固定候选比较打开时，第二页自动 SVG 经 CLI 返回。固定比较内容与版本保持不变。随后在浏览器明确预览并采用第一页候选，第二页完整 Page entry（含原图、SVG 和已有下游引用）逐字段相同；第一页的 Page/原图保留，SVG 更新且下游预览失效。

[交错检查与前后引用](w07/real-host-interleaving/interleaving-checks.json)、[原生绑定](w07/real-host-interleaving/image-checks.json)、[比较前](w07/real-host-interleaving/comparison-before.png)、[采用后](w07/real-host-interleaving/comparison-after.png)、[文件 SHA](w07/real-host-interleaving/manifest.json)。本轮实际 Host 的执行身份和接手时间同时用于 W10；另一个真实 SVG 任务明确取消后提交晚到结果，CLI 返回 5，页面/候选/输出均未改变，[检查](w07/real-host-interleaving/late-result-checks.json)。

这是当前 Host 和实际浏览器机制补证，业务文案仍为合成演示；不代表客户验收、独立专业审阅或发布。
