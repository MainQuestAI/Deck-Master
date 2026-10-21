# 独立复审追加修复

2026-10-20。产品与新包源码 `554e9e2f91301f1b2fd223db1552f22d0df05bff`。本回执更新 AC19/20/30/33/39/40/47；父线程独立代码复审仍进行中，不宣称全量收口。AC49 等待最终 head CI 与独立 Draft PR。

## 复现、修复与边界

| 问题 | 修复前准确复现 | 修复与最终断言 |
|---|---|---|
| P1/P2 双写交接 | 先保存到 saved；挂住旧自动保存 P1 回包；输入 P2；单击交接触发 blur/click 都等待 P1；释放 P1 后 blur 发 P2，click 提前返回；释放 P2 后不导航。saved 分支 FAIL，unknown/conflict 分支 PASS。 | save() 循环等待当前在途写入，成功 ACK 后若最新稿仍 dirty 则继续保存；其它等待者发起 P2 也必须等待。分别释放 P1/P2，一次点击导航且正文说明等于 P2；unknown/conflict 保留草稿、阻断导航，始终只有两笔个人草稿 POST、Document 不变。 |
| 合法 speech-only | deck-review / phase=review / review_units=[speech] 被私有集合400拒绝。 | string[] 形状校验后复用 method_ids_for(review,review_units=...) 校验合法范围。默认 IDs 与核心一致，显式 writing-profiles 成功；invented-unit 仍400，无副作用。 |
| D1失效、无D2 | D1 被同身份 rejected 替代，核心 can_record=true / can_adopt=false / existing_decision_ref=null；显式重评后理由仍锁定，无法新记录。 | 仅显式重新评估且满足核心准入时，将旧回执保留到 previous_decisions，解除理由锁定、显示记录新决定。重新记录必须用户再次确认；新决定 ACK 后仍独立采用。有效 D2 分支继续使用 D2。未核实 pending payload/UUID 不替换，不自动写入。旧“已记录待采用”提示在归档时清除，避免把失效决定当成当前有效决定。 |

复现日志：[双写](evidence/double-save-reproduction.log)、[speech/无D2](evidence/resolver-decision-reproduction.log)。原单笔 blur 测试继续保留，但不再被视为双写覆盖。

API-SPEC/UI-SPEC/ACCEPTANCE/traceability 的上述 AC 同步细化，未新增卡或 AC，也未改变持久合同、核心 resolver 合同、CAS/事务锁和 writer 边界。

## 验证结果

- 重点六分支：**6 passed，51 deselected，17.45s**。[日志](evidence/independent-review-focused-final.log)。包括双写 saved/unknown/conflict、speech/unknown unit、D2存在、D2不存在。
- 相关回归：**137 passed，135.56s**。[日志](evidence/independent-review-regression.log)。覆盖完整 matrix、reader、insight browser、旧个人草稿 browser、RC5 Host selection/resource catalog。重点组与它重叠，不相加。最终 speech 显式资源断言由重点组覆盖。
- 本次 clean wheel/sdist、managed candidate 安装成功，`activated=false`。安装服务 `python -I`、cwd `/tmp`、site-packages、无 checkout sys.path；三视口主线/方法/Review、两步采用、真实安装版 P1/P2 单击交接，共 **5 checks PASS**。[包及安装回执](evidence/package-review-fixes.json)、[浏览器日志](evidence/installed-browser-review-fixes.log)。
- 修改 Python 的 ruff、git diff --check PASS。规格脚本未执行。

```bash
PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild/test_webui_acceptance_matrix.py tests/rebuild/test_webui_content_insight.py tests/rebuild/test_webui_content_insight_browser.py tests/rebuild/test_pr105_draft_browser.py tests/rebuild/test_rc5_host_selection.py tests/rebuild/test_rc5_resource_catalog.py
PYTHONPATH=src PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser /workspace/Deck-Master/.venv/bin/python -B -m pytest -q tests/rebuild/test_webui_acceptance_matrix.py -k 'drains_old or method_speech_review or explicit_reassessment or reassessment_uses_new'
/workspace/Deck-Master/.venv/bin/python tools/build_release.py --out /tmp/webui-release-review-fixes
```

release：`554e9e2f9130-3f23db12f315`。此前441项回归、三场景实际Host和旧/新安装回退仍绑定 `3baf6caa`，作为原范围证据保留，没有重标为新 SHA 执行。新包未激活真实 HOME。

## 余项与远端

父线程已确认此前分支无 PR，PR127 未合并。新 Draft 应依赖 `codex/rc5-content-methods-20261020`，完整 A/B 范围仍在同一分支。父线程使用其合法 GitHub connector 创建；本任务不再运行 gh 创建或查询，不更换通道规避原 API 访问错误。

代码独立复审 IN_PROGRESS_PARENT；AC49 PENDING；独立专业审阅、人类认可 NOT_RUN。工程修复通过不替代上述结果，不合并或发布。最新 PR 正文在云端 `/workspace/webui-evidence/pr-body.md`，最终回执同时给出全文。
