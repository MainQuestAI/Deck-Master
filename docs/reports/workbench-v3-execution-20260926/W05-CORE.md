# W05 共享核心切片

代码提交 `6f3e39635094543704ca498c32db0f2f7ead29dc`，基线为 W04 前端合入后的 `b00525557ac69e9453ae4d6e3b5faf20dbefcf8b`。这里只记录核心、CLI、HTTP 的工程验证；W05 界面、固定比较、用户验收尚未执行，候选比较仍依赖 W07。

`page_lineage.v1` 增补真实文本对象与制作摘要。逐页正文沿用 `visible_atoms` 的稳定 atom ID 和 JSON Pointer；旧 prepared、新 generation request、已记录 submitted 分别给出准确对象、字段、UTF-8 SHA256 和 Unicode 码点长度。只有旧核心请求中保存的 projection hash 与原文 JSON 尾段完全吻合时才提供两个可信段落，其余保留全文。

`POST /api/text-ranges/validate` 要求固定已提交版本、页、层、对象、字段、文本 hash、左闭右开范围和原始摘录全部相符。emoji、组合字符和 CRLF 不归一化；图片和 SVG 不产生伪造文本层。沿用本地 Host/Origin/session-token 防护，读取验证不落 journal 或业务版本。新协议冻结请求也可作为 W03 个人草稿的基准。

SVG/PPT 的 editability 来自 artifact 元数据；PPT 计数保留 render_report 的 `text_runs` / `native_shapes` 名称及来源，不能解释成文本框数或非文本形状数。旧报告和 trace 没有直接 PPTX 父引用，只能标注同快照下输入依赖相符，不升级为直接绑定。SVG 输入图像元素数仅在 trace 的 SVG 文件 hash 匹配时推导；PPT 光栅化比例、OCR、桌面字体替换未记录。声明字体/fallback 与编译输入字体 hash 分开；professional_use/desktop_editing 显示对应输出对象上的记录及 reviewer 类型，不作新的人工作业或质量认可。

验证命令（源码环境 `PYTHONPATH=src`）：

```
python -m pytest -q tests/rebuild/test_page_detail.py tests/rebuild/test_workbench_reads.py tests/rebuild/test_ui_journal.py tests/rebuild/test_generation_protocol.py tests/rebuild/test_web.py tests/rebuild/test_package_boundary.py
python -m ruff check src/deck_master tests/rebuild/test_page_detail.py
git diff --check
```

结果：106 passed（20.57s）；Ruff 与 diff 检查通过。新增 28 项行为用例包含精确 Unicode、归一化拒绝、跨页/跨版本拒绝、固定历史、真实 HTTP 权限和 CLI 投影一致性、新旧 prepared 与 submitted、冻结请求草稿、损坏/缺失/失效/错误范围制作记录、评估对象绑定与 reviewer 来源。制作记录与图片都是明确的合成夹具，未运行真实 PPT 编译、模型或桌面 Office 编辑。

W05-AC05/AC07 的核心部分已有工程证据，完整 AC 暂不签收。下一步先将此共享核心 PR 合入 main，再实施 W05 前端；保持 W02 原有实际提交证明边界，非空参考附件仍不自动升级为已验证。

补充：原图 provenance 指向的 generation request / attempt 仅在该固定版本中通过页与请求归属核验后返回 adopted 引用。测试在同页冻结第二份请求后采用第一份，确认读取没有猜测为最新请求。
