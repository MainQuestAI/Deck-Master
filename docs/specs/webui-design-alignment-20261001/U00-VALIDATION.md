# U00：工具链与必跑验证门

2026-10-01。基于 PR83 的 `7a73b2d`，工程提交 `75e5304c8cfdd30f0214647891af24cde1e78383`。本地 U00-1～U00-4 已完成；托管 CI 结论需单独读取，不以本地结果代替。PR83 尚未合并，本包以其分支为 PR 基线。

## 已实现

- 生产 `v2/package.json` 显式声明 ES module，实际模块测试使用稳定的 `--input-type=module`，支持 Node 22/24；保留原有正文、摘要与收据断言。清理正文测试中重复的准备代码。
- 浏览器测试标记为 `browser`。`--require-browser` 要求至少选中浏览器测试，并把依赖缺失、setup/call skip 判为失败。普通本地执行仍可明确 skip。
- CI 分为四组合 Python 3.11/3.12 × Node 22/24 单元矩阵、真实渲染组、必跑浏览器及安装包组；报告要求三组成功。浏览器组安装 Chromium，并保存安装验收证据。
- 安装验收递归核对公开静态资源的真实字节，包含 Logo/favicon，单独核对许可和 ESM 元数据。核对根入口及兼容入口、旧地址 404、无旧静态三件套、三用途固定版本 ZIP 的哈希与清单。支持显式指定真实 Chromium 路径。

## 实测结果

| 检查 | 结果 | 证据 |
|---|---|---|
| Python 3.11.16 / Node 22.23.3 单元组 | 964 通过，0 skip | [日志](evidence/u00/py311-node22-unit.log) |
| Python 3.12.14 / Node 24.19.0 单元组 | 964 通过，0 skip | [日志](evidence/u00/py312-node24-unit.log) |
| 真实渲染组，串行运行 | 31 通过，0 skip | [日志](evidence/u00/render.log) |
| 实际 Chromium 设计回归 | 2 通过，0 skip | [日志](evidence/u00/browser.log) |
| 受控缺少 Chromium，必跑模式 | 退出 1、2 个 setup error，符合预期 | [日志](evidence/u00/required-browser-missing.log) |
| Python 3.12 / Node 22、Python 3.11 / Node 24 的实际 JS 模块 | 各 5 通过 | [3.12/22](evidence/u00/py312-node22-modules.log) / [3.11/24](evidence/u00/py311-node24-modules.log) |
| 隔离 wheel 安装与本地浏览器导出 | 7 项检查、3 用途 ZIP 通过；无 JS 异常或外部请求 | [检查记录](evidence/u00/installed-checks.json) |
| 安装包元数据追加核验 | 1 通过；显式校验 ESM 文件随包 | [日志](evidence/u00/final-package-metadata.log) |
| 已安装 CLI `--ui legacy` | 退出 2、参数拒绝，符合预期 | [日志](evidence/u00/legacy-cli-rejection.log) |

当前测试集合共 997 项，按单元 964、渲染 31、浏览器 2 分组执行；没有使用 skip 形成通过结论。完整单元组只在表中的两个组合执行，另两个组合只实测纯 JS 模块；托管 CI 配置执行完整四组合。Ruff、Python 编译及 `git diff --check` 均通过。最终 ESM 打包断言是在全量单元收集之后增加，以单独的安装包测试补验。

工具版本、退出码、wheel SHA256 与首次失败原因统一见 [机器记录](evidence/u00/validation.json)。SVG 工具来自 Debian `librsvg2-bin` 2.60.0，下载后按本机 Debian Packages 清单核对 SHA256，再解压到独立工具目录；没有替代渲染工具。安装环境的 `doctor --step render` 和 `doctor --step view` 均为 `ready`，专业质量为 `not_evaluated`。

## 复现

在安装开发依赖、Node 22 或 24、Chromium 和真实渲染工具链后，按顺序执行，避免本地多进程构建争用同一 checkout 的 `build/`：

```bash
python -m ruff check src/deck_master tests/rebuild
python -m pytest -q tests/rebuild -m 'not render and not browser'
python -m pytest -q tests/rebuild -m render
python -m pytest -q tests/rebuild -m browser --require-browser
```

在新虚拟环境安装本候选 wheel 后执行：

```bash
python examples/workbench/w12_offline_browser.py --require-installed \
  --font 'DejaVu Sans' --out /tmp/workbench-browser-u00
```

`--out` 必须是新目录；使用系统 Chromium 时追加 `--chromium-executable /usr/bin/chromium`。默认使用 Playwright 安装的浏览器。精确本地工具目录及安装路径见机器记录与日志，不属于产品运行要求。

## 未完成边界与下一包

首次 Node 检查 5 项失败已修复。首次渲染组因本地并行构建争用目录失败，串行完整重跑 31 项通过。安装验收首次误认为根入口总会显示总览；生产正确恢复上次阅读位置，验收改为显式总览 URL，没有修改恢复行为。

本环境使用 LibreOffice 开发版；稳定 LibreOffice、桌面 PowerPoint 与 macOS 验收仍需对应环境。导出使用明确合成质量输入，不代表实际专业交付批准。本次设计 ZIP 不含真实 30 页制作项目；真实 Host、两轮修改、最终候选压力/回退和实际 HOME/真人观察继续保留在 U06。

下一包为 U01：待办目标解析契约及精确导航。按 [开发计划](DEVELOPMENT-PLAN.md) 先冻结接口，再实现服务和消费者；其功能 PR 的主线基准需绑定 PR83 的最终合并 SHA。
