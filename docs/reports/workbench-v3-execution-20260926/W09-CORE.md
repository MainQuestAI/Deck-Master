# W09 内容与来源调整：共享核心

基于 W08 前端合并 `590e408c36409d435c81291ffea17686419e6fdf`。本切片补齐内容操作、来源版本导航和可恢复输入更新；前端尚未接线，用户验收未执行。

## 实现与边界

`content plan/commit` 绑定 Document、ContentPlan 与选定 Page：直接编辑可见正文、重排、移除及大纲编辑走同一幂等事务。未改 Page 完整条目保留，历史对象不删除；正文变更清空受影响 SVG/预览和整稿输出，保留原图但投影为依据已变。无变化保存不使内容产物失效。重排保留不受影响的单页任务。

改写、合并与拆分复用 compose/input_revision Host，增加 `content_operations` 能力与固定请求。改写保留身份且只能修改选定页；合并/拆分必须使用未在历史出现过的新 ID，记录不可变 page_derivation。未选目标及来源关系不可改，旧标注保留旧基准。Host 必须给出具体影响依据，输入变更后的晚到结果不能覆盖新稿。

`content inputs` 复用既有输入服务，增加同次提交的 operations 回执；未知结果使用原编号和 payload 恢复，材料文件随后丢失也不重复执行。旧 inputs 命令返回兼容。`content source` 按指定快照/来源版本读取，只在实际 locator 匹配时报告精确位置，明确提取结果不代表 Host 已判断影响。

新项目写入最低 writer `content-ops.v1`；旧核心拒读，current 指针不变。Page schema 不变；Document 增加可选派生关系，Task 增加可选固定内容请求，ContentPlan 增加人工编辑来源。活动 schema 与唯一镜像同步。

## 验证

- `tests/rebuild`：881 passed，137.51 秒；新增内容操作测试 18 项，包括并发幂等、索引丢失恢复、来源历史边界、未选页/目标拒改、新身份复用拒绝、原图适用性与晚到保护。
- Ruff 通过；公开 CLI 合成示例 7 项检查通过。HTTP 用例覆盖同源/token、操作查询和固定来源。
- PR #59 核心读取新项目返回 exit 4，明确最低 writer 不支持；current 字节未变。首次用 `view` 仅返回未运行服务状态，不构成读取兼容证明，随后改用 `inputs show` 完成实际拒读验证。
- [核心证据](w09/core/checks.json)、[完整测试输出](w09/core/pytest.txt)、[旧核心拒读](w09/core/old-core-denial.json)。

## 实际 Host 材料替换

当前 Codex Host 通过公开 CLI 读取两份真实落盘的合成材料，初稿为三页。第二版将“只读查询”替换为“可保存草稿”，同时将受众由经办改为部门管理者，汇报用途改为确认范围和验证前提。Host 明确解释每页影响，仅更新 capability 页；责任边界页和验证条件页完整条目不变，既定决定和页序保留，全部目标来源绑定新版本。

该回合通过实际 task start/accept 采用，非 fixture 生成影响判断。自动断言用于检查 ref 矩阵；材料是合成样例，无客户事实或独立专业验收，未调用图像模型，也未声称原图已更新。失败/晚到采用由单列合成故障测试覆盖。

[前后 ref 与检查](w09/real-host/ref-matrix.json)、[实际影响依据](w09/real-host/replacement-result.json)、[Host 范围声明](w09/real-host/host-provenance.json)、[文件 hash](w09/manifest.json)。

## 后续

核心合入后接材料、正文、大纲、来源与结构操作界面；验证草稿恢复、鼠标/键盘重排及合并拆分交接。W09 AC 保持 partial，直到界面证据完成；用户验收仍单独记录。

## 前端接线发现的合同修复

正文浏览器用例增加嵌套列表和表格后，发现 `customer_visible` 内的 `#/$defs/bullet_item` 在内容操作 input/plan 的新根中无法解析。此前只含标题/段落的测试未覆盖该缺陷。两份合同根补入与 Page 一致的递归定义，唯一镜像同步；新增用例通过公开 plan/commit 保存嵌套列表和表格，并拒绝缺失文字的子条目。内容操作及合同测试 21 passed（1.61 秒），Ruff 通过。该核心修复单独合入后才恢复前端工作，不用前端绕过合同验证。
