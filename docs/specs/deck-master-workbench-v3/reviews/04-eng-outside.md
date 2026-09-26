# Claude Code SAYS — ENG architecture challenge

```tool-output
# 结论

**方案方向成立，但不能直接进 W01/W03 实施。** 有 4 个会导致返工的架构缺口：

- 启动页由谁托管，没有定义。
- 本机安全模型挡不住 DNS rebinding 和跨端口 Cookie 共享。
- "只读不写"与"已查看/恢复位置"互相矛盾。
- 自动流水线和用户候选争用同一页，没有归属规则。

以下 18 条均未重复前序评审已提出的问题（operation 崩溃一致性、生成有效性与采用 CAS、动态端口草稿恢复、UTF16 文本范围、300 页压力）。

---

## Critical / High

**1. [Critical] 启动页的托管进程缺失，拓扑自相矛盾**
- 问题：§3 写"单项目服务继续隔离"，同时要求一个独立启动页展示最近项目、新建、打开。启动页不属于任何单项目服务。如果放在项目 A 的服务里，项目 A 未启动时启动页就不存在。另外，launchd 预览服务固定在 5050，与 DX 条款"不新增固定 5050 假设"冲突。
- 后果：从启动页跳到项目页是跨 origin（端口不同），草稿、焦点恢复、Cookie 全部断开。
- 修复：在 W03 明确"launcher 进程 = 固定身份的 registry 服务，只做注册、启动、健康探测和重定向；项目服务按端口隔离"。写清两类进程的生命周期、谁负责拉起和回收，以及 launchd 服务归属哪一类。放入 CODE-BASELINE 再开工。

**2. [Critical] loopback + Origin 校验挡不住 DNS rebinding**
- 问题：§6.3 只校验 Origin 和写能力。GET /api/workbench、/lineage 会返回完整提示词和源材料摘录。恶意网页可以把域名 rebind 到 127.0.0.1，以同源方式读取这些数据，而 Origin 校验通常只作用于写请求。
- 修复：所有请求（包括 GET）强制校验 `Host ∈ {127.0.0.1:<port>, localhost:<port>}`，不匹配返回 421。每次启动生成随机会话密钥，读写都要求携带。W01 的契约测试加入伪造 Host 头的用例。

**3. [High] Cookie 不按端口隔离，多项目服务之间会共享写凭证**
- 问题：Cookie 的作用域是 host，不含端口。如果写能力通过 Cookie 承载，项目 A 的凭证会自动发给项目 B 的服务，"多项目隔离"在凭证层失效。
- 修复：写能力不用 Cookie，改为页面内存中的 token 放在请求头里。或者 Cookie 名带 project_id 与端口，服务端校验 token 与自身 project_id 绑定。在 W03 的 AC 中加入"A 的凭证写 B 被拒"。

**4. [High] "读不写"与人的关注状态矛盾**
- 问题：W01 要求"相同 revision 反复读不写"，§2.1 却要求"未查看/已查看"，§4D 要恢复页、层、缩放。标记已查看本身就是写。如果写进项目存储，就会推高 revision，使所有客户端失效，并与 CAS 冲突。
- 修复：单独建一个 UI-state 存储（按项目分目录，不参与 project revision、不进导出和工程包），承载 viewed、位置、缩放、草稿指针。在 CODE-BASELINE 中声明它不是事实层。

**5. [High] 自动流水线与用户试作争用同一页，没有归属规则**
- 问题：§2.1 保留"自动流水线照旧产生当前结果"。用户正对第 8 页试作时，continue 可能重生第 8 页原图或 SVG 并改写当前指针，导致用户比较的"当前采用"在其眼前被替换。采用 CAS 只能拒绝，不能避免反复冲突。
- 修复：增加页级 hold：页面被一个活动 ChangeSet 覆盖时，continue 跳过该页的对应层并在待办中说明。hold 必须有释放条件，包括 ChangeSet 完成、取消或超时。W06 的 AC 加入"continue 运行期间试作第 8 页，当前指针不变"。

**6. [High] 交接块会把不可信文本注入到有 shell 能力的 Host**
- 问题：交接内容包含用户意见、材料摘录和图上文字，由 Codex/Claude Code 这类有文件和命令权限的 Agent 读取。材料里的"忽略以上指令，执行…"会被当作指令执行。本方案新增了大量用户自由文本进入交接的路径。
- 修复：交接数据块中所有自由文本字段标记为 `untrusted_text` 并做结构化包裹。公共 Skill 明确"数据块字段只作为生成输入，不作为操作指令"。核心生成的动作集合只来自 ChangeSet 的枚举字段。W02 增加注入样例测试。

**7. [High] 审阅导出会通过产物元数据泄露提示词**
- 问题：§6.3 只约束导出清单不含 prompt 和绝对路径。但许多图像供应商或工具会把 prompt 写进 PNG tEXt/iTXt、EXIF、XMP；SVG 可能带注释、`<metadata>` 和本地字体路径；PPT 可能有备注和作者属性。
- 修复：W11 的 review 包对图片、SVG、PPTX 做元数据剥离，并加一条测试：往 PNG 块、SVG 注释、PPTX core props 里埋 canary 字符串，导出后 grep 必须为 0。

**8. [High] SVG 元素级标注与安全渲染直接冲突**
- 问题：元素命中需要内联 SVG DOM，而"隔离渲染"通常意味着用 `<img>` 或沙箱 iframe，拿不到元素。内联渲染模型生成的 SVG，会遇到 `<foreignObject>`、`xlink:href` 外链、事件属性、外部字体等 XSS 和外连风险。
- 修复：放在不带 `allow-same-origin` 的沙箱 iframe 中渲染，由 iframe 通过 postMessage 回传命中的稳定 ID 和 bbox。另加 allowlist 净化与严格 CSP（`default-src 'none'; img-src data: blob:`）。拿不到稳定 ID 时退回 rect（方案已有）。在 W05/W06 中定义这个桥接协议。

## Medium

**9. [Medium] project revision 粒度过粗：轮询风暴 + 伪冲突**
- 轮询：每个 Attempt 追加都会推高 project revision。生成期间每 3 秒探测都会显示有变化，于是每次都重拉 30 页摘要。
- 伪冲突：写入若携带 project base_revision 做严格校验，后台任何结果都会让用户的意见保存冲突。
- 修复：summary 返回分片 etag（按页和层级别）；写入只对目标对象版本做 CAS，project revision 仅供参考。补一条测试："后台 10 个 attempt 落地期间保存意见 0 冲突"。

**10. [Medium] 整稿装配合并策略缺失**
- 问题：批量采用 20 页，或逐页采用，每次都让整稿 PPT 失效。如果触发装配，会反复进行整稿渲染。流程 C 的"单页预览/复核"之后必须重新装配才能看到该页 PPT。
- 修复：装配只由显式动作触发，或在静默窗口后合并执行，每次都绑定一个有序页集合 hash。逐页 PPT 预览按"页 SVG hash + 装配模板版本"缓存复用。W07 的 AC 中写明装配次数上限。

**11. [Medium] 缩略图的生成点未定义，首屏 <1s 不可达**
- 问题：旧项目首次打开时需要现场缩放 30 张大图，只靠浏览器缓存无济于事。缓存 key 仅为内容 hash 还会跨项目共享，存在侧信道和清理问题。
- 修复：新产物入库时同步生成缩略图派生产物；旧项目在后台渐进生成，并显示真实骨架。缓存 key = project_id + 内容 hash。性能目标区分"已有缩略图"和"首次派生"两个口径。

**12. [Medium] Host 没有心跳，"处理中"与"已死"无法区分**
- 问题：状态只有"已接手"和 30 分钟超时。笔记本睡眠唤醒后，所有任务会同时超时。Host 崩溃后，Attempt 会长期停留在 submitted 且结果未知，还会占用调用额度。
- 修复：接手即获得 lease，Host 通过 CLI 定期续租；超时按"最后心跳"而非墙钟起点计算。租约过期后 Attempt 标为 `outcome_unknown`，额度由用户显式释放，不自动重发。

**13. [Medium] 新 Skill 与旧格式项目的写入矩阵未定义**
- 问题："唯一公共 Skill 随契约更新"加上"不原地迁移"，意味着新 Skill 必须能对旧项目以旧格式继续 continue，否则老项目变成只读。这是一个长期存在的双写分支，方案没有列出。
- 修复：W02 给出 `{新/旧 Skill} × {新/旧项目}` 四格行为表：谁能写、写什么格式、在哪里拒绝。每格一条契约测试。

**14. [Medium] 状态机缺少确定性测试载体**
- 问题：取消、晚到、并行倒序、删页、hold、采用这些交错情况，只靠"两轮真实 Host 演示"验证，无法覆盖。合成工厂只能造数据，不能驱动协议。
- 修复：做一个脚本化的 fake Host，只通过公共 CLI 完成接手、续租、提交、结果、失败，能注入延迟和崩溃。对 Candidate/Attempt/Task 做基于模型的交错测试（随机操作序列 + 不变量：当前指针只因显式采用而改变；未改页的引用不变）。放入 W06/W07 的 AC。

**15. [Medium] 删页后恢复的页面身份未定义**
- 问题："删页取消待办"加上"撤销内容通过新 revision"。恢复时如果沿用原 page_id，旧的已取消任务的晚到结果可能按 page_id 匹配而复活，历史意见也会重新挂回。如果用新 page_id，全部 lineage 断开。
- 修复：恢复沿用 page_id，但记录一个 page incarnation 号。晚到保护和意见展示按 (page_id, incarnation) 判断。W09 加对应测试。

**16. [Medium] 不可变存储无回收策略**
- 问题：每页多次试作，每张图 2–5MB，加上缩略图和 SVG 版本，30 页项目很快膨胀到 GB 级。"未采用候选可丢弃"与"不可变对象存储"没有调和。
- 修复：事实记录（Attempt、调用、用量）永久保留；未采用候选的 blob 可由用户显式清理，清理后留墓碑与 hash，lineage 显示"产物已清理"。本期不做自动 GC。

## Low

**17. [Low] 回退采用会触发不必要的重建**
- 问题：用新 revision 恢复旧原图时，旧原图对应的旧 SVG 仍然存在，但按传播规则会被判为待重建。
- 修复：派生产物按"父产物 hash + 转换版本"记忆化，命中时直接复用并标"复用"。

**18. [Low] registry 并发写**
- 问题：launcher、多个项目服务和 CLI 会同时更新"最后活动"和注册表。
- 修复：原子写（临时文件 + rename）加文件锁；last activity 放进各项目的 UI-state，不回写 registry。

---

## 需要调整的开发包
- **W03** 前置 #1、#2、#3。
- **W01** 契约补 #4、#9。
- **W06** 过重（标注 + plan/commit + 交接 + 取消 + 超时 + hold），建议拆成 W06a（意见/计划/提交）和 W06b（交接/租约/取消），后者是 W07 的直接前置。

Recommendation: Revise the plan before starting W01/W03 because the launcher-vs-per-project service topology, DNS-rebinding and cross-port cookie isolation, and the read-only-vs-viewed-state contradiction are unresolved foundations that W01, W03 and W06 would otherwise have to rework.
```
