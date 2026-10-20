# PR127 RC5 评审修复：云端接续

2026-10-20；唯一新开发任务，工作区 `/workspace/Deck-Master`。未访问用户本机、恢复旧云端线程、下载原 ZIP，未合并、发布或激活真实 HOME。当前版本仍为 `1.0.0rc5`。

## 基线与变更

Git fetch/ls-remote 核实评审 head `02627c17d5046428609e6806569ad3cd790e7d26`，main/base `09f0213d07fc718dc4d41a52bb69c4595fcb1ac8`，工作区干净。读取仓库 AGENTS、task index、recovery playbook 和 RC5 README；仓库和 `/workspace/.agents` 无额外 `.agents/skills`。修复代码提交 `d1ee1c7d1f16db120fd4c91c2cc9e71ce31b915e`，已在复核远端未变化后普通 push 到现有 `codex/rc5-content-methods-20261020`，没有强推或新建 PR。

- **P2-1**：blueprint 在 production-request 对象写入之前按最终 kind/production/角色验证显式选择，保留 stamp_task 最终冻结。`continue_project(...content-m04)` 的回归检查完整 Document（含 revision/Task 集）、授权额度以及整项目所有文件路径和字节完全不变。未放宽 catalog scope。
- **P2-2**：有限输入界限下加、减、乘和差值使用足够的 Decimal 精度，覆盖 `10^40+1` 的零容差反例。除法单独规定 40 位有效数字、ROUND_HALF_EVEN；非精确除法必须明确提供正容差，输出注明舍入规则与 rounded_division。六种普通运算、零分母、超长数字、超大 JSON 等拒绝回归保留。
- **P2-3**：完整回读 E03 的 8 页、E06 的 7 页及其 input，参照 M08 与 content-calibration。E03 P7 移除标题中的答案提示，把适用版本、材料和承诺判断留给学员；E06 P6 的两题都要求先写判断及依据。两份阅读版分别标出现场题面和讲者作答后反馈，说明投影/发放时机；不增加机械页数。
- **A（已验证，不再仅是静态推断）**：generic production compose 的旧 RC5 manifest 重发实际报 method-selection scope 错误；无 manifest 历史任务原先通过。修复默认阶段选择，重发时仅移除早期 RC5 错放在 design/production/delivery 的 method-selection 默认，不扩张其合法选择范围。三路覆盖新 manifest、早期 RC5 manifest、无 manifest 历史 Task；原对象字节、有效授权引用、write_scope、adoption_policy、collaboration 控制记录不变，旧依据仍显示 basis_changed、新依据 current。
- **B（已验证）**：独立 deck-review 省略 stage 时原先拒绝 M04。统一到 runtime 默认 review units/phase；普通读取与 work_context.v2 均通过，page_visual 仍拒绝 M04。

## 内容审阅边界

这是修复作者的完整内容审读，不是独立专业复审或人类认可。E03 保留日期适用规则、非随机样本不可外推、无依据承诺删除与迁移练习；E06 保留关联条款/父子检索/上下文索引的候选比较、权限版本与成本约束、不可断言普遍效果。现场先作答后反馈，阅读版保留解析，不用关键词测试代替教学判断。

本次未取得用户本地工作树外的六份原始稿及原实验日志，未读取、未重新开展大型效果实验。既有 `package-verification.json` 绑定 `5d5db8cf`，原证据保留；本轮代码/资源变化另建 clean-source 包证据，不将文档 head 差异解释成旧验证失败。实际执行为本会话 Codex；未冒称另一次 Astra Medium 效果实验。

## 执行记录

所有源码 pytest 使用 `PYTHONPATH=src` 和 `.venv/bin/python -B`；完整日志在云端 `/tmp/rc5-*.log`。下列验证是工程证据，不是效果或专业验收。

- 新增回归先运行：6 failed、41 passed；确认 P2-1、>40 位加/乘舍入、Review 两种读取默认 scope 问题。另一次 A 窄探针 1 failed、1 passed，失败落在实际 reissue 的显式选择校验。
- `PYTHONPATH=src .venv/bin/python -B -m pytest -q tests/rebuild/test_rc5_host_selection.py tests/rebuild/test_rc5_library_acceptance.py tests/rebuild/test_rc5_resource_catalog.py tests/rebuild/test_rc4_content_review.py`：125 passed（4.00s）。随后增强 A 为非空真实授权引用，三路窄回归 3 passed；相同四模块最终复跑 125 passed（4.15s）。
- `PYTHONPATH=src .venv/bin/python -B -m ruff check src/deck_master tests/rebuild`：PASS。
- `PYTHONPATH=src .venv/bin/python -B tools/check_content_method_library.py`：PASS，66 catalog、四入口、76 映射文件、37 本地链接。
- `PYTHONPATH=src .venv/bin/python -B tools/build_release.py --out /tmp/rc5-cloud-candidate`：PASS，源码 d1ee1c7d、source_dirty=false，wheel/sdist 全映射哈希相等。
- 首次 render：54 failed、76 passed、3 skipped、1 error；doctor 明确缺 rsvg-convert。首次 managed 安装也因此失败，未激活。apt 无候选包，之后将 Debian 同版本 `librsvg2-bin_2.60.0+dfsg-1_amd64.deb` 下载并只解包到 `/tmp/rc5-render-tools/extracted`，不修改系统。以 `DECK_MASTER_RSVG_CONVERT=/tmp/rc5-render-tools/extracted/usr/bin/rsvg-convert` 重查 doctor：ready。
- `install_candidate('/tmp/rc5-cloud-managed-ready', '/tmp/rc5-cloud-candidate/release.json')`：candidate_ready、activated=false；安装内资源核验、原生编译/渲染探针通过。以安装解释器 `-I` 从带伪造 Skill 的 `/tmp/rc5-spoof` 读取默认 Review+M04 v2，安装资源路径与内容正确，未借 cwd。

### 完整单元与 render

- 完整单元命令：`PYTHONPATH=src .venv/bin/python -B -m pytest -q tests/rebuild -m 'not render and not browser' --basetemp=/tmp/rc5-cloud-unit`。结果：3466 passed、3 failed、3 errors、2 skipped、635 deselected（725.98s）。其中两项 failed 和三项 setup errors 位于隔离安装，实际错误是测试为 loopback 清空代理后 pip DNS 失败。
- render 补工具重跑命令：`DECK_MASTER_RSVG_CONVERT=/tmp/rc5-render-tools/extracted/usr/bin/rsvg-convert PYTHONPATH=src .venv/bin/python -B -m pytest -q tests/rebuild -m render --basetemp=/tmp/rc5-cloud-render-ready`：129 passed、1 failed、1 error、3 skipped（297.32s）；剩余同属安装依赖网络问题。
- 离线依赖由 `pip download --dest /tmp/rc5-wheelhouse 'setuptools>=77' wheel` 及对本轮 wheel 的依赖下载准备。首次自行列包取得 Pillow 13，不满足项目 `<13`，离线重跑仍失败；之后按 wheel 的真实约束补齐 Pillow 12.3。未修改项目依赖范围。
- 隔离 CLI fixture 会清除 `DECK_MASTER_*`，因此仅设置显式 converter 变量时仍返回 needs_tool；在评审基线 02627c17 独立 worktree 中同样复现。最终通过 PATH 传递真实工具：`PATH=/tmp/rc5-render-tools/extracted/usr/bin:$PATH PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/rc5-wheelhouse PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild/test_install.py --basetemp=/tmp/rc5-install-final`：**17 passed（33.74s）**。覆盖上述全部安装失败和错误。结合 render 全组，其非跳过用例均已有通过记录；没有声称一次完整绿跑。
- 单元剩余 `test_rc3_image_events.py::test_real_shared_lock_rechecks_frontier_after_wait[False]` 报 `current own rights/literal inputs changed before dispatch`。使用绝对解释器完整复跑该模块：27 passed、1 failed（5.34s）。在未修改的评审基线 worktree，分别用相对与相同绝对解释器窄复现同一错误（各 1 failed）。这是当前云端仍存在、且基线同样失败的验证限制；没有删断言、放宽安装身份或把既有本机 absolute-path 成功记录搬作本次成功。日志分别为 `/tmp/rc5-image-events-final.log`、`/tmp/rc5-baseline-image-relative.log`、`/tmp/rc5-baseline-image-absolute.log`。

### browser

初轮启动后发现部分 fixture 使用不存在的 Playwright Chromium 缓存，未完成就停止；不作为完整结果。`PLAYWRIGHT_BROWSERS_PATH=/tmp/rc5-playwright .venv/bin/python -m playwright install chromium` 被 CDN 返回 `403 Domain forbidden`，未下载成功。已有 Debian 系统 Chromium **151.0.7922.173**；在 `/tmp/rc5-system-browser` 的 Playwright executable 路径显式链接该真实二进制（不是其预期的 Chrome 153 下载版）。原失败导航用例以此复跑：1 passed（3.33s）。

完整 501 browser 节点按模块分为三组、使用各自临时目录运行，未改变测试断言；每组准确参数数组保存在 `/tmp/rc5-browser-shard-{0,1,2}-command.json`。共同配置：`PATH=/tmp/rc5-render-tools/extracted/usr/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/tmp/rc5-system-browser PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/rc5-wheelhouse PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -B -m pytest -q <该组节点> -m browser --require-browser --basetemp=/tmp/rc5-browser-shard-N`。最终三组分别 **167 passed（633.79s）**、**167 passed（585.59s）**、**167 passed**，共 **501 passed**；各进程退出码均为 0。具体第三组耗时见 `/tmp/rc5-browser-shard-2.log`。

## 外部状态

PR：<https://github.com/MainQuestAI/Deck-Master/pull/127>。本轮没有调用 ready/merge/release，保持已有 Draft 意图，待独立复审。

`gh pr view 127 --json headRefOid,headRefName,isDraft,url` 的 GraphQL 与 `gh api repos/MainQuestAI/Deck-Master/pulls/127` 的 REST 均被网络返回 Forbidden。Git fetch/push 正常；没有把 API 读取失败记为 CI 通过。PR 评论发布及准确新 head CI 读取尚未执行，需可用 GitHub API/连接器。这里是已提交到 PR 分支的修复回执，不能替代线上 Checks 的结果。
