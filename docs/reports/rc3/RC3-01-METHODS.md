# RC3-01 方法与加载工程交接

基线：main `71c18f3acf87da7a7f62bf5501511f8179c1500c`（PR115 已合并）；实施工作树 `impl/rc3-01`。本记录只报告本卡方法和加载工程；当前完整首稿、双盲初判/裁决、真实方法效果及隔离安装由独立执行记录提供，不因方法提交自动 PASS。

## 本卡实施

五份 canonical 方法分别补齐全文材料消费、用途/权威/已知未知/条件、实质论证与逐页增量、四类完整正反页、六组成对浅稿及具体返修。四类是方法覆盖，不规定每稿四类齐全。保留培训、研究、阅读和说明任务，不统一套销售结构。

纠正既有 `54 条需补问版本`：Q2 观察是 `120 条中 54 条首次提交缺型号或版本`，不是补问计数、唯一主因或 45% 收益。推理必须保留前提/测量限制。Plan 不复制 Page 正文，atom/source/Narrative/notes 映射保持现行合同；必要限定上屏，制作记录内部留存。篇幅 exact/target/max、口播/互动/总时长、cues/verbatim/none、已确认稿 fidelity 与越界问题按有效任务范围处理。

`method_resources` 新增唯一 `content-calibration` ID，只有 preproduction review 增加这一读取资源；普通 compose、输入修订、最终 review 和版本号保持现行协议。前审的真实 packet 仍包括 Task、完整来源 extract、Narrative、Plan、全部页正文和 notes。既有 Runtime/provider 边界继续生效，默认没有 provider 时为 needs_reviewer；普通独立模型可由受信非作者 native controller 的实际观察形成 host_attested 回执，不要求平台密码学签名。synthetic provider 仅在测试使用，不作为真实独立执行/人类专业验收。

五固定 CyberPPT 全文读取及原始 SHA/字节/行覆盖见 `rc3-01-method-source-consumption.json`；固定 commit 为 `980e5576565f0673c67ee41b01d20ed66cb8417c`。学习实际对象证据、内容关系和静态/渲染复核；参考脚本、生成器锁和审批规则不作为本次执行授权。仅选择 b00df87 的五 canonical 方法相关内容，并补正/扩展；没有引入其他混合代码。

## 活动原件与历史

上传 R2 活动锚点 SHA `3f58b7392b30ceb4304699071cc12cc6b4eff487af512b48e4121a1e43efb2bc` 按原字节接收。旧锚点 `42774a7006dec5e8e319cfbd9c58d0cf9c3cc52f1e67793d81cfb9133643ad4c` 原字节归档；五份旧 evaluation 原件保留原位置和字节。fixture manifest 区分 current_inputs、historical_reviewed_inputs 与 historical_artifacts，记录当前规范在导入时未执行独立重评。README 标明历史 pass 不自动关闭新 CQ。

锚点导入属于规范一致性修正，不是双盲结果。控制映射、期望标签和投放归实验控制方；真实独立初判、分歧和裁决另存，不发标签给 judge。原始完整稿、至多一次自主返修后的首次 Owner 稿、后续修改和方法复跑分别保留，不用当前稿改好回写历史首稿通过。

## 当前 canonical 方法身份

| 方法 ID | SHA-256（UTF-8 原字节） | bytes |
|---|---|---|
| `source-reading` | `44eb27513dc6af907484ca0b60d77a0aa211ffe1f6d43339876ab6a904e18f08` | 6353 |
| `content-methods` | `ca27c8fea86784d1236c2b5d13ff51ad8616a5f594ce8ca037742def1dc71130` | 16268 |
| `content-examples` | `cace2f4dfb12c904bcaa4b011239cc186516510fbe90a56cfc2b35f53f6c995d` | 12121 |
| `content-calibration` | `bb672652bf1f0e7c1248a423af8ce432793bc0eb2fd4905c9a423ebea0a9718c` | 7824 |
| `review-and-repair` | `cf66ea3c6ad0c5776ebf8feb409f00530369823368fcb6f44f11c05b93b63f20` | 5838 |

实际消费示例：从当前 review 工作单取 task_id，运行 `deck-master methods --project <project> --task-id <task_id>`，保存返回的真实全文和 dispatch/current 方法身份。`basis_changed` 不重标旧任务；缺文件报错，不借另一个安装的旧方法。`methods --kind review --intent preproduction --read` 可只读当前安装内容。返回文本证明 Runtime 交付字节，Host 应用方法与专业效果由真实执行档案证明。

## 验证及尚缺证据

owner targeted：`test_rc3_content_methods`、`test_rc3_early_methods`、`test_content_preproduction_review`、`test_content_mapping_claims`、`test_compose_v2_phases`、`test_flow_quality` 共 122 passed。Ruff 和 git diff --check 通过。env-01 的 module_origin 为本卡 src，不混用 /source。新增测试覆盖真实前审 Task 读取五方法和完整 packet、只变 calibration 的旧任务 basis_changed、缺 calibration 拒读且保留原 Task/packet/current、默认真实 needs_reviewer、当前 R2 与历史原件 hash 关系。测试 provider 明确 synthetic L1。

独立代码审查、root 广泛回归/当前 CI、wheel 与隔离安装/真实 Host 消费、十二锚点双盲校准、范围内真实首稿和实质返修将由后续固定记录补齐。此处不提前宣称内容效果或整卡最终验收。人类 Owner/受众/完整试讲/桌面专业验收按用户安排延后，保持 NOT_RUN；不改实际 HOME。
