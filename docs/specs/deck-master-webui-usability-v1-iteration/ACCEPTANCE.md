# 验收与证据记录

四层证据分别关闭：合同与工程、浏览器可用性、真实制作与安装、用户认可。
本轮只交付前两层；后两层保持未完成，不以工程通过替代。

## 批次 0 · 基线与环境（2026-10-04）

工作区：worktree `/Users/dingcheng/.codex/worktrees/webui-usability-v1/Deck-Master`，
分支 `codex/webui-usability-v1`，基线提交 `7662a11`（PR #98 tip）。
证据目录：`/Users/dingcheng/.codex/worktrees/webui-usability-v1/evidence/batch0/`。

| 层次 | 命令 | 结果 |
|---|---|---|
| 静态 | `ruff check src/deck_master tests/rebuild` | All checks passed |
| 工程（非浏览器非渲染） | `pytest -q tests/rebuild -m "not render and not browser"` | **1222 passed, 143 deselected, 0 failed**（97.99s，`unit-tier-clean.txt`） |
| 浏览器可用性 | `pytest -q tests/rebuild -m browser --require-browser` | **91 passed, 1274 deselected, 0 failed**（173.73s，`browser-tier.txt`） |
| 渲染 | `pytest -q tests/rebuild -m render` | **52 passed, 1313 deselected, 0 failed**（137.09s，`render-tier.txt`） |

环境性修正与说明（详见 COMPAT-NOTES）：

1. 本机 HTTP 代理导致伪造 Host 头的负例被代理拦截（403 变 502），统一以
   `no_proxy='*'` 前置运行；未改任何代码。修正前 `unit-tier.txt` 的两项失败属此原因。
2. Python 3.12 venv 默认无 setuptools，`tests/rebuild/test_install.py` 的 wheel/sdist 构建
   会 `BackendUnavailable`；补装 `setuptools wheel` 后 17 项全部通过
   （`install-after-setuptools.txt`）。
3. 基线提交为 `7662a11`，工具版本 Python 3.12.12 / Node v22.22.3 / Playwright 1.63.0。

此后批次以本表为「无未处理新失败」的对照基准。

## 批次 1 · （待填）

## 批次 2 · （待填）

## 批次 3 · （待填）

## 批次 4 · （待填）

## 本层明确未执行

| 项目 | 状态 | 说明 |
|---|---|---|
| 真实 Host 制作（意见→trial→候选→采用→下游重建→检查→导出） | **未执行** | 需独立工程、实际工具与执行授权 |
| 独立 30 页副本两轮有边界修改 | **未执行** | 同上 |
| 安装包真实运行与真实 HOME 安装 | **未执行**（仅做 checklist 级 wheel 复验） | 不安装到 HOME |
| 用户视觉认可与连续操作认可 | **未执行** | 工程与浏览器证据不能替代 |
