# PR130 CI 集成遗漏：eligibility 入口分类

产品源码 `7b414a92c77a2578465e4495f5932320a1a95cb1`。本修复只修改 `eligibility_entries.py`，增加15行精确分类与理由；未修改测试、发现扫描、封闭豁免词表、路由实现或 Runtime 准入。

## 真实失败与复现

父线程读取精确旧 head `eabee7dd` 的 push CI `39421563183`、PR CI `39422228545`，确认 unit 四失败来自入口未分类；不是环境波动。[父线程提供的日志来源](https://github.com/MainQuestAI/Deck-Master/actions/runs/39422228545/job/118625786070)。本云端执行原 `test_eligibility_entry_coverage.py`，同样得到 **4 failed、18 passed / 0.36s**。未分类项为新增 `collaboration.prepare_decision` 和六个 HTTP 发现字符串。原日志保留于 [复现](evidence/entry-registry-reproduction.log)。

## 分类根据

| 新入口 | 分类 | 依据 |
|---|---|---|
| collaboration.prepare_decision | read_plan | 共享纯校验，调用 decision.record 准入检查后只返回内存 proposal；不保存决定、不提交、不颁发授权。record_decision 仍是独立加锁/门禁写入口。 |
| /api/(tasks/[^/]+/methods\|reviews/[^/]+/reading) | read_model | GET 读取固定快照的冻结任务依据和 Review 阅读投影。 |
| /api/content/arguments | read_model | GET 索引/详情读取合法可达 Narrative 和真实 Plan；不采用。 |
| /api/content/evidence/ | read_model | GET 按固定 Page/atom 读取实际映射和来源。 |
| /api/content/requirements/ | read_model | GET 读取冻结要求或纯推导要求，不创建制作任务。 |
| /api/method-library/resources/ | read_model | GET 返回登记资源的已校验字节，不执行脚本。 |
| /api/method-library/preview | read_plan | POST 只是 context/selection 的传输形式；解析目录和准备结果，不存业务对象，不派发，不改 allowance/call。 |

这些是实际发现字符串的精确行，不是新增通配前缀豁免。现有“未知写入口必须报未分类”“新参数化路由必须被发现”“未知后代不得继承豁免”的断言全部保留。额外只读检查确认上述路由的任意 new-write 后代仍无分类，真实 decision.record/proposal.adopt 仍为 gated。

## 验证

- 原入口覆盖组 + WebUI reader 无副作用组：**34 passed / 1.41s**。[日志](evidence/entry-registry-targeted.log)
- inventory：431项，158 gated / 273 exempt；`uncovered={}`、`stale={}`。[统计](evidence/entry-registry-inventory.json)
- 全仓 rebuilt core/tests Ruff：PASS；git diff --check：PASS。
- 全量 unit 已完整运行：**3500 passed、2 skipped、3 failed、3 errors，682 deselected / 630.13s**。[原始完整日志](evidence/unit-full-entry-fix.log)。四个原 CI 入口覆盖失败消失，不能把本轮其它本地失败抹去或把整组标 PASS。
- 其中五项隔离安装失败/错误：fixture 为新 venv 安装 `setuptools>=77` 时明确 `Temporary failure in name resolution`，尚未进入产物路径。对同一配置源显式启用网络权限进行 DNS 核对后仍失败；没有更换源、绕过拒绝或降低依赖要求。这五项在此环境 **BLOCKED_DNS**，待新 head CI 独立验证。
- 另一项 image-event shared-lock 测试已单独复现并找到准确差异：parent 的 metadata_version 为当前源码 `1.0.0rc5`，`python -I` child 从旧 `/workspace/Deck-Master/.venv` 读取 `1.0.0.dev2`，其余绑定一致。[差异](evidence/image-identity-difference.json)、[定向复现](evidence/image-lock-targeted.log)。复制依赖到独立 `/tmp/webui-unit-venv` 并以 `--no-deps --no-build-isolation -e` 安装本 checkout 后，原两个 shared-lock 分支 **2 passed / 0.54s**：[日志](evidence/image-lock-correct-sdk.log)。正确SDK环境下入口/reader组再次34项通过：[日志](evidence/entry-registry-correct-sdk.log)。未改测试/产品，原 venv 和原工作树未改。此局部重跑不重标第一次整组运行结果。

```bash
PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild/test_eligibility_entry_coverage.py tests/rebuild/test_webui_content_insight.py
PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild -m 'not render and not browser'
/workspace/Deck-Master/.venv/bin/ruff check src/deck_master tests/rebuild
```

环境：当前云端 Python3.12.14 / Node24.19.0，CI所需三个固定历史基线对象均存在。其它 Python/Node 矩阵由新 head CI 验证。上一轮包、浏览器、渲染和实际 Host 证据保留原 SHA，不重标为本轮新执行。

## 交付边界

修复推送现有 Draft [PR130](https://github.com/MainQuestAI/Deck-Master/pull/130)，base 仍为未合并 PR127 的 `codex/rc5-content-methods-20261020`。不创建新 PR，不合并、不发布。AC49 仍待新 head 完整 CI，专业效果/人类验收 NOT_RUN。
