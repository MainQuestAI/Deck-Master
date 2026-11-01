# 表达自然度与保真｜M10 / Review 可选参考

## 来源与使用边界

适配自 [blader/humanizer](https://github.com/blader/humanizer/tree/8c307f367c91bd974002f10f2be2965d642c13df)，固定 commit `8c307f367c91bd974002f10f2be2965d642c13df`，SKILL version `3.1.0`，MIT。已对照该提交的 SKILL.md、README.md、LICENSE；原许可全文附后。它是英文散文编辑启发，不是中文 PPT 的验证结论。README 的 LLM 偏好实验不代表中文 PPT 真人效果，也不提供作者识别、“AI味”分数或检测器规避目标。

本参考用于新线的主页稿和出 PPT 前语言审改。`deck humanize --stage content --file <作者稿.json>` 返回规则与整理后的正文；Host 读材料和原稿，按下文审改后用 `deck put` 保存。出图、重建 SVG 前运行 `deck humanize --stage pptx`，复查全部上屏文字；改字后仍用 put 保存，再重建受影响 SVG。build 再整理空格并核对实际 PPT 文字，结果返回在 humanizer 中。语义判断由 Host 完成，命令不会按词表删除句子，也不产生语言质量分数。

## 按读者任务检查

先读实际范围的原稿与来源，再找具体损失；不能按词表或句式一律判错。

- 无信息增量的套话、重复收尾、空泛升华：指出它与哪句重复；有必要结论、导航、教学回顾或单页分发需要时保留。
- 夸大意义、模糊权威：把支持的事实与推论分开。无出处就标缺口，不能补造专家、研究、案例来源或经历态度；删除整项主张也须说明损失，不能掩盖待核事实。
- 主体、动作、条件、因果不清：只用材料能支持的关系写清谁做什么；相关性不能改成因果，缺主体不能猜。
- 聊天旁白与制作过程：去掉无关问候、讨好、继续服务邀请；保留影响使用的来源说明、限定和操作边界。
- 受众和文风：依据已知场景调整信息顺序与语气，保留真实个人表达。未知读者背景不能当成“读者已知道”删掉必要解释。

不照搬英文禁词，不硬禁标点，不机械删除对比或三项列表，不去掉承担层级的粗体、流程箭头和中文引号，不把 PPT 列表强改连续 prose。自然不等于口语化、缩短或稀疏。

## Review 输出与 Content 复查

只审阅时保持只读，不自动写回。每个发现返回：原句及页/atom/字段或文件行定位；问题；读者影响；建议改写（或保留/待核）；必须保护的事实与限定。用具体页和原句记录意见。没有问题的合理结构可以明确保留；不要为凑数量造问题。

Host 只改本次授权范围；只改讲稿时不改上屏正文，只做框架时不扩写全稿。改后逐项对照原稿与来源：事实、主体、动作、数字、分母、单位、时间、范围、否定、预计/条件/不确定性、引用和出处、因果强度、排序与并发关系。新增无依据或丢失必要限定均需纠正。再读整页与相邻页，确认必要解释、结论、行动和教学回顾仍成立。改写建议不等于事实已核验或用户已授权采纳。

## 固定中文校准材料（虚构，仅作方法边界对照）

| 原句 / 场景 | 可接受处理 | 必须拒绝的处理 / 保护项 |
| --- | --- | --- |
| 80份资料中32份缺型号，工时影响尚未验证。这标志着效率的全面飞跃。 | “80份资料中32份缺型号，工时影响尚未验证。”删无依据升华，保留分母与验证缺口。 | 改成“节省40%工时”；32/80是缺型号占比，不是工时收益。 |
| 预计下月试用，仅限A组，效果未验证；审查建议不自动写回。 | 原句信息完整，可保留或只调整顺序。 | 删除“预计”“仅限”“未验证”“不自动写回”，或改成已经上线/已验证。 |
| 系统不是替代人工，而是辅助人工核对型号。 | 合理对比说明职责边界，应保留。 | 仅因“不是…而是…”就删除人工责任。 |
| **选项**：维持现状、分组试点、全面部署。流程：提交→复核→批准。界面显示“待核”。 | 三个真实选项、粗体层级、流程箭头、中文引号均保留。 | 凑成两项、改成散文、删除流程方向或引号。 |
| 仅限A组试用，因此暂不推广。让我们共同开启辉煌新篇章。 | 删空泛尾句，保留“仅限A组试用，因此暂不推广”的必要结论。 | 连同结论一起删掉，或删培训中的必要回顾。 |
| 资料未给出成功案例与研究出处。 | 保留缺口；建议补充可核验材料。 | 编造客户案例、专家来源、“我亲测有效”或个人态度。 |
| 已完成核对。 | 若原材料没有执行主体，标注主体待确认。 | 擅自写成“质量团队完成核对”或编造因果。 |

以上是人工编写的预期边界，不是模型实验结果。真实模型对照未运行时报告 `not_run`；工程测试只能证明命令行为和文件处理，不证明读者偏好或实际改写保真。

## 固定源文件 SHA-256

- `SKILL.md`: `0612f1dfb1672b0ea9b97e139bf1f06cabe98d8b27424fe8ff01e1fb4cc99cad`
- `README.md`: `500b53c0d29cd3219d160b5f9a109c0969f706aec74b49a4a081d2026ba48ec7`
- `LICENSE`: `4ac4810254ab36d45419141aeb8e69bf50652cfafe5b2dab947d06d44e5cbf96`

## 上游许可（保留原文）

```text
MIT License

Copyright (c) 2025 Siqi Chen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
