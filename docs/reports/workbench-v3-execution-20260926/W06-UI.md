# W06 版本绑定意见与持久修改交接

W06 核心 PR #51（8 项 CI 通过，合入 `6c3e156a47926187b71ada1bd5983a0ad73662f2`）先进入 main，本前端再接入其公共服务。前端实现提交为 `0e976f7e5b0d6a6cecf638bb3ed0f60b140bde74`，保持本线程专用 `workbench-implementation` checkout；原 A/B/设计工作树未改。

用户可以在固定页与图层上记录整页、点、框或精确文本意见，按项目/章节/页/产物范围保存。阅读拖动不产生意见；标注时关闭缩放，Esc 取消未保存范围，可删除并重新画区域。坐标按真实 contain 图像与 SVG viewBox 计算，留白不作为图像区域；多个区域生成独立的意见对象。文本沿用原始对象引用、locator、hash、Unicode 码点范围和原摘录，不归一 emoji、组合字或 CRLF，也没有图片 OCR 伪文本层。

保存意见仅追加事实，不建制作任务。选入已保存意见后才请求只读计划，显示具体页面、图层、基准、调用上限与下游影响。正文、意图或选入内容变化会撤销旧预览；提交时服务再校验基准。失败保留本机草稿和新基准说明。历史内容仍只读；仅元数据版本前进而 Page 基准未变时，可以继续写绑定原版本的意见，原 Page 已改变时保留原有历史草稿只读行为。

业务请求的 UUID 与完整原 payload 在发送前保存；未确认回包会暂停新的业务提交。核实只查询原编号，`not_found` 才允许重放已保存的原请求。后写草稿和 pending 请求分别保存；项目 journal ACK 只表示草稿持久化，不表示业务成功。项目已 ACK 的请求可跨端口恢复，未 ACK 的本机缓冲须显式下载、导入恢复文件。小数坐标的摘要采用与 Python 对实际 JSON 输入一致的科学计数法，并有跨语言回归测试。

修改交接面板从核心读取已提交计划、任务及真实执行引用，可从任务面返回。复制成功只记录本机“已复制、未接手”；剪贴板失败保留完整手动复制内容。真实 CLI start 后才显示已接手；部分完成、超过等待阈值、状态未知和取消分别呈现，没有自动重复调用。轮询不在状态未变时替换用户正在阅读的交接文本。

## 验证

- [主流程 24 项](w06/ui/browser-checks.json)：实际 Chromium / 同源 HTTP，范围保存、Unicode、计划只读与重新预览、持久交接、响应丢失、原请求重放、刷新恢复、剪贴板失败和导航返回。
- [边界 14 项](w06/ui/edge-checks.json)：实际并排比较留白、SVG viewBox 坐标、鼠标和百分比区域、极小小数、过期计划冲突、服务重启换端口、查询超时，以及已 ACK / 未 ACK 两种跨 origin 恢复。网络/剪贴板失败为明确故障注入；项目和图件均为合成素材。
- [真实 Host 记录](w06/ui/real-host-checks.json)：当前 Codex 会话读取浏览器实际创建的计划，经正式 CLI 声明 `changes.v1` / `change_plan` 并 start，浏览器看到真实 execution_ref 后确认取消。随后正式 CLI 接收晚到 repair 结果返回退出码 5 / conflict；所有 Page 指针、输出和 content identity 未变。核心按既有规则增加取消后结果的审计版本，因此不声称 revision 完全不动。这次没有模型调用或结果采用，也不等于专业质量通过。
- [104 项测试](w06/ui/pytest.txt)：现有 HTTP、固定读取、单页、journal、意见、计划及浏览器/Python 摘要。摘要用例涵盖 1,011 个确定性数字/Unicode 对象；额外本机 5,000 个数值样本也一致。
- 浏览器回归：[W03 主流程 15 项](w06/ui/w03-main-regression.json)、[W03 边界 13 项](w06/ui/w03-edge-regression.json)、[W04 画廊 18 项](w06/ui/w04-gallery-regression.json)、[W05 单页 15 项](w06/ui/w05-page-regression.json)通过。目录弹窗实机、完整 300×5×3、20 分钟刷新及 Office 使用验收不在这里升级结论。
- [wheel 文件核对](w06/ui/wheel-assets.json)：从固定实现提交隔离构建，24 个 UI 文件与 Git 源码及当前 checkout 字节一致；没有安装到实际 HOME，也未替换默认入口。
- Node 语法、Ruff、diff 检查通过。截图：[SVG 留白与定位](w06/ui/svg-letterbox.png)、[复制后未接手](w06/ui/handoff-unclaimed.png)、[真实接手](w06/ui/handoff-claimed.png)。

可运行脚本为 `examples/workbench/w06_annotations_browser.py` 和 `w06_annotations_edges.py`。`--wait-for-host` 只等待外部真实 CLI 接手，脚本不模拟 Host；完整请求、恢复文件、本机路径及交接原文只留本机 `local-only/`。核心三类故障 JSON 与恢复脚本继续见 [W06 核心报告](W06-CORE.md)。

W06-AC01–08 记录为工程验证，`accepted=false`。未进行用户验收，也未把本卡接手证明升级为图像制作、最终安装、离线或客户交付验收。后续按顺序进入 W07，W01/W04 的完整压力仍等待真实 Candidate 契约形成。
