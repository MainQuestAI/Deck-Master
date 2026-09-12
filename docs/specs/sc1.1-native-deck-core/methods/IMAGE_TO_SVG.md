# 生产方法｜从真实图片蓝图重建可编辑SVG

由既有deck-builder按阶段加载；这是方法参考，不是新增公开Skill。执行前只检查本次变动相关的输入和工具，不重做已确认主线访谈。

## 输入

当前Content Lock、实际图片（不是文件名描述）、style lock、Diagram View（适用时）、asset manifest、compiler-supported SVG subset、page_id/action_id/revision与修复范围。关键输入缺失返回可定位任务，禁止凭空补齐。

## 执行

先读完整图片理解层级、网格、留白、背景和主要组件；再检查标题/正文/关系图和角落。提取的是视觉组织，不从图片重新认定事实。所有文字、数字、符号、单位和业务限定从Content Lock读取并定位text_ref。

按语义组件建立group与stable element_id，文字用text/tspan，框和业务图形用shape/path，连线/箭头用原生路径；Scene携带component/model_ref及必要几何。照片单独绑定登记资产；不得用整页或拼图截图替代主要内容。

仅输出支持子集。复杂效果优先用可编译的简化视觉，不改变事实与层级；需要明显改变已批准设计时给出差异，不静默转换为位图。路径的绝对/相对坐标、transform和样式由公共normalizer检查。

重建后实际渲染SVG，逐项核对：关键文字是否全在、关系方向是否正确、图表值与单位是否一致、重点层级与蓝图是否一致、有没有溢出/非法覆盖/内部文字、是否每个主要业务对象都可单独编辑。蓝图本身有错时，按锁纠正并记录allowed_delta，不抄错。

## 返修

只修当前pending/rework页面。已完成无关页的内容/几何/hash不改。小型文字或颜色改动复用视觉结构；结构性变动返回新蓝图阶段。失败记录问题位置、观察、改动和下一次验证，预算内继续；预算耗尽留已完成页并报告，而不是要求用户从头解释任务。

## 输出

approved候选SVG、Scene语义旁注、生成/修复结果指纹和实际验证记录，由acceptance_command接收；Agent不写runtime seal、approval或正式current pointer。不能仅写pass。完成接受后执行resume_command，直到交付批准点或真实阻断。
