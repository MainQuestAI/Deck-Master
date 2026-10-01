# 核验与证据层级

本轮核验代码为 main `66da345c84de48933a76de577114f08dcebf4f0e`，没有改生产代码。

- `sprint-review-20261001.json`：**冲刺终审**（用户要求的四层 subagent 评审：核心/前端阅读/前端决策/证据；4 P1+10 P2 结论与修复记录）。
- `a08-browser-verification.json` / `output/playwright/a08/*.png`：**A08 实施后新增**（基线 b8bbf59）：两视口（1440/1280）×六工作面 12 图矩阵 + 设计差异单 5 项；30 秒真实使用者观察 open。
- `b06-slice.json`：**B06 实施后新增**（基线 0ccd8dd）：preserve_dimensions 投影/范围校验/instruction 核心证据；AC02/AC03 真实层 open。
- `a07-browser-verification.json` / `output/playwright/a07/*.png`：**A07 实施后新增**（基线 2120421）：任务与交付面接入 B05 两阶段清理的端到端验证（清理后 drafts 空、revision 不变）。
- `a06-browser-verification.json` / `output/playwright/a06/*.png`：**A06 实施后新增**（基线 2120421）：候选台消费 B04 决定 + 正文候选文本差异的验证；含终审 P1（digest kind）修复后的收据解除与 reopen 端到端记录。
- `b07-slice.json`：**B07 实施后新增**（基线 fa41aae）：G54 三层收口（含终审修正）与 open 项记录。
- `a05-browser-verification.json` / `output/playwright/a05/*.png`：**A05 实施后新增**（基线 0ccd8dd）：内容面 content-layout 双栏与材料四态、大纲块导航、标注 segmented+键盘百分比区域、文本 code point 选段、草稿按页/基准隔离与刷新保留、保存意见不创建任务、页序/移除/合并/拆分影响预览、材料更新进入待协调流的真实服务浏览器验证；合成证据。
- `a04-browser-verification.json` / `output/playwright/a04/*.png`：**A04 实施后新增**（基线 a8f698e，冲刺支线 codex/webui-v4-completion）：整稿画廊设计布局（segmented/legend/slide-tile/有效列降级/页面搜索）、六段制作链（含来源段与提示词阶段切换）、连续阅读返回逐像素定位、并排同版比较与筛选外选中、历史固定只读无业务写、大图加载中切换工作面与离开零请求泄漏（W12 根因引 629d625，压力复测归 B07）的真实服务浏览器验证；24 页 create_gallery_sample 混合层项目，合成证据。
- `a03-browser-verification.json` / `output/playwright/a03/*.png`：**A03 实施后新增**（基线 931f19c）：overview.js 待办面板消费 B01 next_actions 与 8 列矩阵（排序/搜索/章节/批量选择，普通 Tab）的 24 页混合项目真实服务浏览器验证。
- `a02-browser-verification.json` / `output/playwright/a02/*.png`：**A02 实施后新增**（基线 e58d2df，含 B01/B02）：launcher 搜索与项目卡、五工作面外壳、连接面板消费 effective_actions（含 fixed_revision 前端组合）的真实服务浏览器验证；macOS 目录选择取消路径因终端无 UI 自动化权限保持待验。
- `a01-verification.md` / `a01-browser-verification.json` / `output/playwright/a01/*.png`：**A01 实施后新增**。在 `codex/webui-a-implementation` 分支完成设计基础落地与 PR66 有限移植后的分层验证（核心 905 项通过 + 真实服务双视口浏览器证据）；head/base 与缺项见该文件。基线核验（下述其余条目）仍对应 `66da345` 未实施状态。
- `current-core-tests.log` / XML：本轮运行9个相关测试文件，**148 passed / 24.94秒**；这是定向核心回归，不是完整905项回归，也不是新版浏览器验收。
- `probe_gaps.py` / `gap-probes.json`：本轮在临时合成项目运行5项源码行为核验，无模型调用，临时项目已清理。覆盖正文trial拒绝、attention/prompt摘要缺项、candidate summary/schema不一致、固定revision HTTP已实现、旧项目能力广告与实际可执行性不符。
- `inherited-execution-state.json`：旧执行线程台账快照，不等同本轮验收。
- `inherited-*.json`：按 `inherited-evidence-manifest.json` 收回旧证据；不修改源文件、不把旧时间/旧SHA改成新结果。W12安装摘要属于PR66 head93c76a1；可证明该候选记录过23步成功，不能证明新基线的最终安装。压力记录明确失败，不能计20分钟通过。
- `governance-before.json` / `governance-after.json`：本次本地分支归档事务与前后状态；没有远端删除、旧工作树清理或PR写操作。
- `source-anchors.json`：当前主线源码位置，用于复核差距判断。
- `spec-validation.json`：仅证明本Spec的文件/编号/依赖/收讫hash完整性。

## B01 工程切片证据（webui-b 线）

B01 在 `codex/webui-b-capabilities` 分支实施后新增：

- `b01_pressure.py` / `b01-pressure.json`：300页×5候选×3Attempt合成压力样本（6304个元数据对象，无模型调用），warm 120次 `workbench_summary`，**p50 72ms / p95 84ms / max 89ms**，低于250ms门槛；冷读首访675ms不作为门槛项。仅为读模型合成证据，不是生产运行或真实Host验收。复现：`PYTHONPATH=src python docs/specs/deck-master-webui-v4-20260930/evidence/b01_pressure.py /tmp/b01-pressure.json`（或用已装dev依赖的解释器直接运行）。
- gap-probes 的 P02（attention恒not_recorded、无prompt摘要）与 P03（candidate summary违反活动schema）已由 B01 产品实现关闭，回归见 `tests/rebuild/test_workbench_actions.py`（11项）及既有 `tests/rebuild/test_workbench_reads.py`；`probe_gaps.py` 的对应断言针对基线 `66da345` 的缺口，在新代码上会按预期失败，保留为基线记录不作修改。P05 属 B02 范围，本轮未处理。

复现探针：在仓库安装dev依赖后，`PYTHONPATH=src python docs/specs/deck-master-webui-v4-20260930/evidence/probe_gaps.py /tmp/deck-master-gap-probes.json`。脚本借用既有测试fixture创建候选，不能用于生产项目。
