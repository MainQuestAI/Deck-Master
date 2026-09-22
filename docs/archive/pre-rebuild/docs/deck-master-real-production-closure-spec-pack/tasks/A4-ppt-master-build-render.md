# A4 — PPT Master Production Build / Render

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `A4` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | A1, A2/A3 result shape |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

把真实页面源组装为客户可用 HTML、PDF、逐页 PNG 和有效 PPTX。

## 3. In Scope

- Build manifest。
- HTML assemble。
- Playwright render。
- PDF。
- page PNG。
- PPTX output。
- artifact manifest。
- editability declaration。

## 4. Out of Scope

不生成主叙事；不重新改写页面内容；不实现模型推理。

## 5. 必须实现

1. 新增 build prepare/run/status。
2. HTML 页面顺序必须与 manifest 一致。
3. PDF 和 PNG 由最终 HTML 渲染。
4. PPTX 至少支持 flat-image，有 native adapter 时标记 native/hybrid。
5. 输出 checksum、size、media type。
6. 字体缺失写 warning。
7. Build source fingerprint。
8. 任一 required output 失败时不能 completed。

## 6. 允许 / 预期修改路径

- `scripts/runtime/build.py`（新增）
- `scripts/runtime/render.py`
- `scripts/capabilities/ppt_master.py`（新增或重建）
- `product_capabilities/ppt-master/runtime/`
- `docs/contracts/`
- `tests/test_build_runtime.py`
- `tests/test_render_runtime.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- 3/12/60 页。
- Unicode / 中文。
- missing image。
- invalid page source。
- HTML open。
- PDF signature。
- PNG signature。
- PPTX parse。
- page count。
- source fingerprint。
- editability metadata。

## 8. 成功标准

- Client delivery 4 类产物全部存在且有效。
- 页数一致。
- Render result v2 valid。
- 不再调用 fixture-only HTML 作为 Production 默认。

## 9. 风险

浏览器、字体和 LibreOffice/PPTX 生成环境差异；需要明确 dependency doctor。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
