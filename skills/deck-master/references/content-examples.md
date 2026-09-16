# Content Examples｜成稿与精修示例

对象：宿主 Agent 与后续验收。本文件登记可复用的内容样例入口；全部为合成材料，不冒充真实项目成绩。

## 成对样例（D1/D2，同源）

`tests/rebuild/fixtures/content_pair/`：

| 文件 | 内容 |
| --- | --- |
| `material.md` | 合成材料正文（含尾部只读约束） |
| `d1-task.json` | D1 现场交流版任务定义（受众/场景/篇幅） |
| `d2-task.json` | D2 独立阅读版任务定义（同源，不同受众场景） |

用法：同源材料按 D1/D2 分别推导完整正文；两份 Page 的结构、深度与结尾不同才算成对方法成立（AC-C02 的内容行为由实际 Host 运行验证，本表只保证样例可加载）。

## 制作能力样例（三页）

仓库外 `$DECK_REBUILD_EVIDENCE/inputs/`（登记表 `index.json`，含 hash）：

- `REBUILD-ARCH`：三层职责、嵌套模块、图标、建设状态、双向/单向关系、脚注。
- `REBUILD-CHART`：数值、单位、图例、标签、比较关系（占比除式可复算）。
- `REBUILD-SOLUTION`：方案理由、阶段/责任、辅助说明、四级视觉层级。

这些样本供 T06–T12 的完整 prompt、真实生图、SVG 还原与单页修改使用；原图 pending 时按登记表标注 `blueprint_pending`。

## 协议往返例

`docs/specs/deck-master-rebuild-v1/examples/roundtrips/`：

- `result-envelope/`：五种任务信封（compose/blueprint/reconstruct/review/repair）与预期响应。
- `atom-identity.json`：重排/改字/新增的稳定 ID 往返。
- `review-fixed/`：审阅返修的 replaces 链。

## 精修示例与默认成稿的边界

人工或 Host 精修产生的 Page 是能力示范：它证明"给定正文可以做出什么样"，
不证明"系统首次交流就能从原材料写出专业首稿"。默认成稿的质量判断按
AC-C09/C10 由实际人类/Host 运行记录关闭；两者分开保存、分开引用。
