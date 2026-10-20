# PR130 浏览器回归：中性用途字段的精确定位

测试修复源码 `11eba83447e121f34fdb95baddfc4ebceea3cb42`，基于 `d16ed39385274f61cf59e5833190b5db3dba7d96`。本轮没有修改产品代码。

## 合同与修复范围

UI-SPEC §7、SPEC UI-05 与 AC34 要求新建/内容区使用中性用途和受众文案，兼容教学、研究和工程评审，不强制商业行动建议。`content-sources.js` 的“用途与目标”和“受众”仍绑定 `task.brief` / `task.audience`，改名符合规格。

两份旧测试共七处精确字符串同步：五处“汇报用途”改为“用途与目标”，两处“汇报受众”改为“受众”。保持 `exact=True` 和 editor 范围，包括添加材料入口中用途字段不存在的断言，避免旧名称导致假通过。没有正则、别名回退、跳过或删除测试。草稿保留、预览差异、确认 payload、返回编辑、焦点/滚动、刷新恢复和业务对象断言全部保留。

## 原始失败

父线程读取精确 d16ed393 的 [PR CI39427209189](https://github.com/MainQuestAI/Deck-Master/actions/runs/39427209189/job/118642827596)：四组 unit 与 render 成功；浏览器 **11 failed / 537 passed / 3642 deselected**。这是父线程提供的远端证据，不能当作本轮新 head CI。

本云端未修改测试前运行原11项，得到 **11 failed in 298.51s**，均在旧用途标签处失败；不能据此判断之后业务断言正确。[原始复现日志](evidence/neutral-label-reproduction.log)。

## 本轮执行

修复后同一11项：**11 passed in 39.38s**。[定向日志](evidence/neutral-label-targeted.log)。实际范围：

- `test_material_editor_keeps_preview_confirmation_and_return_in_context`：材料数量0/1/2 × 1440×900、1280×800、390×844，共9项。
- `test_inputs_keep_other_entry_drafts_and_confirm_all_differences`：task、mixed，共2项。

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser /tmp/webui-unit-venv/bin/python -B -m pytest -q \
  'tests/rebuild/test_pr103_repair_browser.py::test_material_editor_keeps_preview_confirmation_and_return_in_context' \
  'tests/rebuild/test_webui_audit_browser.py::test_inputs_keep_other_entry_drafts_and_confirm_all_differences[task]' \
  'tests/rebuild/test_webui_audit_browser.py::test_inputs_keep_other_entry_drafts_and_confirm_all_differences[mixed]' --require-browser

PATH=/tmp/webui-render-tools/extracted/usr/bin:$PATH \
PLAYWRIGHT_BROWSERS_PATH=/tmp/webui-system-browser \
PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/webui-browser-wheelhouse \
/tmp/webui-unit-venv/bin/python -B -m pytest -q tests/rebuild -m browser --require-browser
```

完整 required browser 组：**548 passed, 3642 deselected in 1656.29s (0:27:36)**，无失败、无跳过。[完整日志](evidence/browser-full-neutral-label.log)。与 CI 相同的 `-m browser --require-browser` 选择条件，退出码0。完整组包含上述11项及 audit 的 add 模式，不能与定向11项相加作为去重数量。

环境：云端 Python3.12.14、Node24.19.0、系统 Chromium；CI Node22/Playwright Chromium 仍需新 head 远端验证。临时 wheelhouse 由声明依赖正常下载得到，供测试隔离 pip 使用；无替代测试或伪造依赖。原工作树、原 venv、PR127、真实 HOME 均未修改。

全仓 `ruff check src/deck_master tests/rebuild` 与 `git diff --check` PASS。此轮未重跑完整 unit/render、独立 wheel 安装后的两个脚本或实际 Host；旧结果保持原 SHA。专业审阅与人类验收仍 NOT_RUN。修复继续同一 Draft PR130，不合并、不发布。
