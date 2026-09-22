# P3 — PPT Deck Pro Max Bridge Lock And Smoke

## 1. 目标

把 `ppt-deck-pro-max` bridge 从“本机可用实现”升级为“release 可追溯依赖”。

## 2. In Scope

- bridge 正式来源确认
- bridge 固定 SHA
- cross-repo smoke
- capability lock bridge entry

## 3. Out Of Scope

- `ppt-master` backend manifest
- benchmark 资产准备
- RC gate 最终收口

## 4. 允许修改路径

外部仓 `PPT-Deck-Pro-Max`：

- bridge 对应脚本与说明文档
- cross-repo smoke 所需最小契约文件

Deck Master 主仓：

- `scripts/skills/installer.py`
- `scripts/generation/dispatch.py`
- `scripts/generation/handback.py`
- `tests/test_generation_session_bridge.py`
- `tests/test_skill_installation.py`
- 相关 smoke 文档或 UAT 文档

## 5. 必须实现

1. 明确 bridge 正式来源与正式 SHA
2. 建立标准 smoke 路径：
   - dispatch
   - import
   - export `deck_generation_result.v2`
   - import-results
3. capability lock 可记录 bridge SHA
4. release truth 可追溯 generation bridge 版本

## 6. 测试与验证

至少验证：

1. Deck Master 生成 dispatch package
2. bridge import 成功
3. bridge export canonical result 成功
4. Deck Master import-results 成功
5. run-state 正常前进

## 7. 成功标准

1. bridge 进入正式可追溯状态，不依赖“本机某个分支刚好可用”
2. release 级别可追踪 bridge 版本
3. cross-repo smoke 有真实证据

## 8. 依赖与并发

依赖 `P2`。  
可与 `P4` 的 benchmark 资产准备并行做前置协调，但正式验收必须早于 `P4`。

## 9. Agent 交付报告

必须输出：

1. 外部仓 SHA
2. Deck Master 写入 lock 的字段
3. cross-repo smoke 命令与真实结果
4. 产物路径
5. 风险与后续建议
