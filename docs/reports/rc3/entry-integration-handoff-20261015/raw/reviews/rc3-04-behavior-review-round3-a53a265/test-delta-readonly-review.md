# R3 测试 delta 只读补充审查

范围是固定 R2→R3 的九个相关文件，不是全套测试审计；code reviewer 主审保持独立。精确内容保存在 `selected-test-delta.diff`，固定 snapshot 文件 hash 见 `selected-test-files.json`。本 reviewer 没有执行或导入这些产品测试及 helper，没有据此宣称 installed 行为 PASS。

未见本次所读 delta 为通过回归而放松原领域结果或建立产品绕行权限的明显证据。具体依据与边界如下：

- `engineering_render_helpers.py` 是显式测试内工程诊断。先调用真实 public `pipeline.produce`，要求 stage_prerequisite_missing / stage_quality_blocked，且完整 source snapshot 不变；随后从现有 SVG 调用实际 compiler/font/asset/render/readback，在 source 项目外输出。report 落盘后重新读取，实际 PPTX/manifest/PNG/report hash 记录；结束再次核 source/Document 不变。标签明确 L1_ENGINEERING_ONLY、visual_acceptance=not_evaluated、production_published=false。没有 patch gate 或伪 PageVisual/human PASS。
- 原九个低层回归（geometry 1、duplicate/paint 5、gradient 3）中，实际 slide size、readback status、重复文本/不可见像素和 gradient 像素结果断言保留；没有把 fail cases 改成 pass 或跳过。旧的“produce 已发布 outputs / 预览挂在 Page”断言确实改成了“正式 produce 拒绝 / outputs 为空 / 外部工程文件存在”。因此这九项仍提供 compiler/render/readback 回归，**不再单独提供正式生产发布正例**，报告不得混称旧 end-to-end 覆盖。该测试边界与当前严格阶段要求相符。
- 补充检查的 `test_rc3_notes_files.py` 仍通过实际 produce/export 验证完整 notes/dependencies；新前置条件明确构造 bounded L1 blueprint→SVG→preview→PageVisual，然后保留原 produce、原 SVG refs、输出匹配和实际 notes 文件断言。低层诊断并未被拿来替代该正式路径。此处仅只读核查断言，实际是否通过由 Root render 运行证实；不借 L1 reviewer 说真实 native/model/professional PASS。
- `rc3_fixtures.accept_synthetic_blueprint` 的唯一 API 扩展为 adopt=False。默认仍执行原 accept，非默认分支在已 claim/freeze/begin/settle 后返回同一已绑定 payload，将**首次 adoption** 留给另一个安装 CLI。没有新造 scope/grant，没有把 terminal replay 当首次 adoption，也没有升级 L1 费用/身份等级。
- F9 增加原句与协调命令正例，以及业务主题 coordination 不抢显式写稿动作的反例。C6 新测试保持 raw instruction equality、用户 API/Page v2/proposal Ref 文本及未知追加全文回退断言。既有 run_desk writer-floor 断言更新到 rank13，并另保留显式旧 reader fixture 的降级拒绝和现代 control 不变断言。

没有审查全 52-file delta 的每条断言；没有重复 broad unit/render 或证明测试完整性。测试辅助不属于安装包，本 reviewer 的 installed PASS 只来自 `probe_r3.py` 及对应真实产品响应。
