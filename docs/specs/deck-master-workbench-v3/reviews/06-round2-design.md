# Review 2 — 视觉、操作与键盘设计

日期：2026-09-26。这是 AutoPlan 后第二轮，输入为 R1 修复后的原型。分类 OPERATE；遵守已锁定 DESIGN.md，不按营销页评判。当前状态：9 组发现已修复，并通过两个桌面视口的实际浏览器回归。

## 实际方法与覆盖

GStack design-review 主审使用本地 Chromium；独立原生审阅使用隔离 Python Playwright context，两个桌面视口均实际操作七个工作面及材料输入。主审目视总览、画廊、单页和固定 SVG 比较；原生审阅额外目视候选、材料、键盘、P19 等截图。完整证据见 [原生报告](06-round2-design-native.md) 与 [证据目录](round2-native-evidence/)。

Claude Code 独立源码设计审阅完成，实际模型为 claude-opus-5-5，session `fe7dac1a-d619-4f60-8940-6fbc44e79563`；完整输出见 [外部报告](06-round2-outside.md)、[原始结果及用量](06-round2-outside-result.json)。结束标记通过 GStack outside-review-result 校验。外部没有浏览器，其像素估计不冒充实测；原生随后实测 1280 下候选画布为 320/319px。输入哈希见 [冻结清单](06-round2-input.json)。

原生独立发现 3 项，外部 8 项；其中焦点连续性、矩阵键盘为 2 项明确共同关注。后续对外部条目的浏览器核验不能反计为独立共识。规范是目标，合成原型有披露的实现范围，不能据此宣称生产可用。

GStack detector 探测结果 `IMPECCABLE_NOT_CACHED`，未安装或运行自动规则扫描；detector.mode=none。无需增加依赖也可完成本轮实际浏览器及源码评审。评分采用主观设计判断，不是 WCAG 认证或真实性能测试。

## 归并与处理

| 归并项 | 来源 | 接受的修订 | 复核要求 |
|---|---|---|---|
| R2-01 用户材料要求丢失 · P1 | N01 | 请求和复制文本保留用户输入，空值明确反馈 | 自定义句子在请求/刷新/复制中逐字存在 |
| R2-02 局部操作焦点丢失 · P2 | N02、E03 | 局部重绘保持稳定控件焦点；路由进入标题；选中态语义与dialog标题 | 键盘切层后可继续操作，不跳回侧栏 |
| R2-03 矩阵与区域键盘路径 · P2 | N03、E06 | 单Tab矩阵、方向键和完整页/层标签；百分比区域字段 | 不是144个停靠点；键盘区域绑定当前产物 |
| R2-04 缺图缺少下一动作 · P2 | E01 | 单页首次生成入口与缺图批量请求，文案不说不存在的当前图仍可看 | P21–24直接保存明确范围；首次/重做文案有区别 |
| R2-05 候选细节不足 · P2 | E02 | 比较全宽，请求事实下移；参考可放大；画廊列数可调 | 1280画幅扩大，放大保留固定参考身份 |
| R2-06 首屏动作竞争 · P2 | E04 | 总览陈述可看事实；恢复入口次级；待办用动词和对象，小缩略图帮助定位 | 首屏只有一个高权重主动作 |
| R2-07 提示词重复 · P2 | E05 | 提示词层右侧用于草稿/意见；缺失历史只有一份说明 | P19不再出现两份缺口与相同主按钮 |
| R2-08 阅读与主要命中 · P2 | E07、补测 | 主动作至少44px；必要元信息12px；prompt正文16px | 两视口computed style与实际操作 |
| R2-09 状态语义与视觉token · P3 | E08 | 完成/失败/处理中分开颜色，边线按锁定token | 状态仍有文字，不靠颜色判断 |

外部建议的范围修正：原生dialog圈焦/Esc回焦已实测通过，不接受“所有dialog都失效”的泛化；补标题语义和会重绘的返回路径即可。品牌D标记沿用已锁定品牌，不因为琥珀色而移除。矩阵紧凑单元格允许小视觉按钮，主要操作保持44px，通过单入口键盘规约保障可达，不把每个状态格强行扩成大按钮。章节折叠和任意参考选页仍属已说明的正式前端范围，不因此把旧卡关闭。

## 修复结果

9 组均为 **verified**；best-effort / reverted / deferred 均为 0。这里的 verified 只指下表限定的合成原型行为。字体打包、任意参考页与真实服务等既有范围说明仍然保留，不被计为本轮已实现能力。

| 项目 | 实际复核结果 | 修订位置与证据 |
|---|---|---|
| R2-01 | 自定义材料要求写入请求，刷新和复制后逐字保留；空白拒绝 | app.js，82fbaab；[修订后](../prototype/validation/round2-after-material-kept-1280.png) |
| R2-02 | 切层/布局后焦点仍在相应控件，路由进入工作区；dialog有名称且Esc回焦 | app.js，82fbaab；[键盘路径](../prototype/validation/round2-after-keyboard-region-1280.png) |
| R2-03 | 矩阵仅一个Tab入口，方向键移动且带页/层身份；百分比选区可提交并保留产物身份 | app.js，82fbaab；专项脚本断言 |
| R2-04 | P21首次生成与P21–24批量请求可走通；采用后原图出现，缺图文案准确 | app.js，82fbaab；[首次生成采用](../prototype/validation/round2-after-first-image-adopted-1280.png) |
| R2-05 | 1280下比较画布从320/319px扩大到480/479px，1440下560/559px；参考放大超过900px | style.css dfcaac8 / app.js 82fbaab；[全宽候选](../prototype/validation/round2-after-candidate-wide-1280.png)、[参考放大](../prototype/validation/round2-after-reference-enlarged-1280.png) |
| R2-06 | 总览只保留一个高权重主动作；矩阵补缩略图，待办动词对应明确对象；画廊2/3/4列可切 | style.css 8342bf1 / app.js 82fbaab；[总览](../prototype/validation/round2-after-overview-matrix-1440.png) |
| R2-07 | P19未知执行提示词只有一份说明和一个建立草稿动作 | app.js，82fbaab；[P19](../prototype/validation/round2-after-prompt19-single-1280.png) |
| R2-08 | 两视口主要按钮实测44px，必要元信息12px、prompt正文16px | style.css，dfcaac8、8342bf1；computed style专项断言 |
| R2-09 | 完成/失败/处理中各有颜色与文字，细线token一致 | style.css，dfcaac8；[状态](../prototype/validation/round2-after-semantic-states-1280.png) |

运行 [round2-fixes.py](../prototype/validation/round2-fixes.py) 得到 [完整结果](../prototype/validation/round2-fixes-result.json)：1280×800与1440×900均通过，0 pageerror；同时重跑smoke、revision-smoke与R1专项。主审亲自查看修订后的总览、画廊、单页、SVG候选与采用后画面、参考放大，确认状态和图片对应。其后仅把合成流程图连接线限定到节点间空隙，避免穿过标签；最终重跑同一专项仍通过，app.js SHA-256为 `178643f1370b0086c18a9f665dcbb32fa50e064c32ee72cc6929f5b3eda33abb`。

修订前截图保留在本轮原生证据目录；R1闭环截图另存 [r1-frozen-evidence](r1-frozen-evidence/)，不把后来重跑覆盖的同名文件冒充原轮次取证。最终源码与提交记录以交付manifest及Git为准。

主观设计评分 **B → B**，AI套路评分 **A → A**：输入信任、键盘连续性与比较细节已改善，保守维持整体等级；本轮不是陌生用户盲测、VoiceOver或完整可访问性认证。十类别及权重沿用原生报告，修订后各类均无本轮已知阻断；[机器可读基线](design-baseline.json)明确detector未运行，不能把缺少自动扫描写成零缺陷。

可用于变更描述的一句话：设计评审归并9组问题，9组已修复并经双视口验证；设计评分B→B，AI套路评分A→A。所有结果仅证明合成原型；真实 Host、模型、服务端保存未知故障注入、最终安装与导出不在本轮验证范围。
