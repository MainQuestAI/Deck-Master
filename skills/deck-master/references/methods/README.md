# SC-1 内置方法索引（按需加载）

本目录收录 SC-1 公共方案内容内核的五份专业方法。它们是既有 `deck-*` Skill 的按需
references，不新增公开入口（D03）；宿主 Agent 在对应阶段按需读取，不在每次会话默认展开。

| 方法 | 服务的阶段（deck-* skill） | 关键产出 |
|---|---|---|
| `brief-and-research.md` | deck-brief（材料全文抽取、缺口研究） | 事实/约束/冲突清单、研究任务与结论 |
| `solution-design.md` | deck-planner（方案模型与备选） | solution_model 组件、能力机制、取舍 |
| `storyline-and-pages.md` | deck-planner（叙事主线与页计划） | narrative_plan 候选与选择、page_tasks |
| `architecture-views.md` | deck-producer（架构视图与图形表达） | diagram_views 四类视图、可编辑图形 |
| `semantic-review-and-repair.md` | deck-quality（语义审查与定向返修） | 六维审查观察、具体返修任务 |

使用规则：

1. 方法只定义“怎么做”的专业判断框架；所有事实必须回指 `context_manifest` 引用的原始
   来源（D07），不得把生成页面当作事实证据。
2. 方法产出进入既有契约对象（solution_model / narrative_plan / page_packages /
   diagram_views），不建立第二套状态（D08）。
3. Fixture/dev 模式允许确定性规则降级生成同类产出；production 模式必须由宿主 Agent
   依据方法真实产出，规则输出不得冒充（D10、D11）。
