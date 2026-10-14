# 实际审阅与返修

本方法指导实际审阅与返修。保留现有 PR33 的逐 finding 关闭、同页产物检查、原图来源、实际读回以及取消/晚到结果保护。

## 工作单就是本次审阅范围

读取当前 review_plan，确认哪些维度尚未执行、已经过期、存在旧问题或因输入变化需要重新检查。任务列出的每一项都要实际完成或准确说明缺口；不能只提交 instruction 中习惯出现的三个维度。

最终六维是：content、blueprint_content、blueprint_fidelity、conversion、readability、privacy。它们不是六名 Agent，也不是六次用户审批。

content 看任务、正式输入和整稿是否成立；blueprint_content 看全部可见表达是否正确进入正文；blueprint_fidelity 看原图的视觉与业务关系；conversion 看 SVG 到真实 PPT 的转换；readability 看实际阅读；privacy 看面向本次受众的可见/隐藏文字、备注及媒体限制。

## 两个时点不做同样的登记

逐页审图提前发现原图与 SVG 的内容、结构和阅读问题。最终查看实际 PPT，检查转换后结果和全稿一致性。前次真实观察可复用；但是只复制它的 pass 并不能证明最终 PPT 没有变化。

来源/任务变化但物理页面没有变化时，重新核对适用内容与披露条件；转换层的已有观察仍可供使用。不因为 Document 管理版本变化就让所有几何观察过期。

## 问题必须定位并形成动作

每项说明所在页和对象、期待、实际、依据及需要改动的范围。内容不足先补机制与论证，不用增大标题、扩大禁词表或堆几张卡片代替。确有制作缺陷时修 SVG 或转换结果，不改原始参考基准。

privacy 不等于宽泛法律认证；“缩略图”“右屏”等业务词不是自动泄密。真实禁止披露的信息应处理，包括讲者备注和媒体，不仅检查正文。

## 处理历史发现

fixed：同一发现有真实相关修订，当前产物经复查。

accepted_variance：原来需要判断的差异，经具体解释、观察和证据确认可接受；不将 must_fix 改名放行。

只有这两种关闭方式。输入更新让原要求失效时，按 input-update 的方法处理，不新增第三种关闭方式。

没有执行阅读就是未评估，不能填默认高分或两套 reviewer 名称。工具可报告真实机械检查，但不能替用户提供专业认可或独立审查身份。

## RC3 内容前审

preproduction 工作单给出 source-reading、content-methods、content-examples 与 content-calibration 的实际文件和 hash。读取完整材料、任务、Narrative、Plan、全部正文与 notes，再按六组校准检查：只有标签、页间重复、空矩阵、侧栏复述、无收益数据时造数/留空、以拥挤替代完整。合理留白、不确定性、教学复习和示意要结合用途判断。

问题定位到 Page/atom/关系、来源和用途影响；提交具体原句、改句与受影响页，不以加 observation/证据编号代替返修。保留首稿、首次 Owner 稿和后续修订；F0/F1 不能用最后精修覆盖，影响用途的 F2 也须修。

先读 `deck-master capabilities`。默认独立前审没有实际独立执行或可信人类通道就记 needs_reviewer；用户明确接受的 host_self 降级只在所绑定范围/原因内适用，不满足交付人类专业政策，不能换名字、声明已独立或自动降级。方法 identity 漂移（method_basis_status=basis_changed）时重核实际消费版本，旧记录保留原身份；`methods --kind review --intent preproduction --read` 可读当前安装的真实文本。

### 实际读取、判断与返修证据

先用工作单 task_id 读取 `deck-master methods --project … --task-id …` 返回的真实全文/hash，核对 dispatch/current 方法身份；再打开 packet 的相关完整来源、Task 事实、Narrative、Plan、每页全部可见 atom 与 speaker_notes。截图/摘要/locator 存在不能代替已读内容，材料含图时同时检查原图。Review 绑定当前被审产物及依赖；未知或未执行的维度保留 not_evaluated，不由通过的机械检查补齐。

每项 finding 写明 Page/atom 或关系、原句/实际结构、所读来源位置、期待、实际、用途影响与 F0–F3 依据；返修给出实际改句/单元格/分支与 diff，复读受影响的总结、引用和 notes。若修改超出 Scope，先报告范围缺口，不静默全稿改写。六组校准中的正对照同样核查，不能为凑密度删诚实限制、教学停顿或合理留白。

事实/批准/授权/改变结论的限定失真按 F0；需用户重建用途、中心论证或章节关系按 F1；局部实质问题影响用途按 F2，修复前不能通过该用途；F3 才是偏好微调。唯一等级依据仍是内容协作 v1.2 `ACCEPTANCE §1.2`，不另设同名 F1。平均分不抵消开放 F0/F1 或影响用途的 F2。

真实非作者 Host controller 观察 native 独立执行的身份、固定工作单和完成输出，并经当前 Runtime 已注册 provider 核对，可诚实取得 host_attested 独立回执；普通模型前审不硬加平台密码学签名。作者提交 JSON、执行 ID、hash 或换 reviewer.id 不能生成该证明。人类专业复核、Owner 接受、听众理解和完整试讲各自留证，没有对应人或环境就 NOT_RUN，模型不扮演人类。

按时间点保存：原始完整生成稿 → 至多一次同口径独立审阅/自主返修后的首次 Owner 完整稿 → Owner 后改稿；方法修改后的原输入复跑另存方法版本和首稿。当前稿修好可以关闭该缺陷，不能回写首次 Owner F1 失败为 PASS，也不能把人工精修旧稿改名为新方法首稿。
