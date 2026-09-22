# P1 — PPT Master Backend Certification

## 1. 目标

让 `hugohe3/ppt-master` 成为 Deck Master 可正式认证的 production backend。

## 2. In Scope

- `ppt-master` backend manifest
- required operation 声明
- smoke 命令
- Deck Master 兼容文档

## 3. Out Of Scope

- Deck Master 主仓的 bind / lock 逻辑
- benchmark 执行
- RC gate 闭环

## 4. 允许修改路径

外部仓 `hugohe3/ppt-master`：

- `skills/ppt-master/`
- `skills/ppt-master/references/`
- `skills/ppt-master/scripts/`
- `docs/` 或等价说明目录

Deck Master 主仓只允许补最小验证适配：

- `scripts/runtime/builder_backend.py`
- `tests/test_skill_installation.py`

如果需要扩大 Deck Master 改动范围，必须先在后续任务包中承接，不在 P1 内顺手扩展。

## 5. 必须实现

1. 在 `skills/ppt-master/` 下补 `deck-master-backend.json`
2. manifest 至少声明：
   - backend 名称
   - schema version
   - supported contracts
   - `render`
   - `smoke`
   - `writeback`
3. 增加最小 smoke 命令
4. 增加 Deck Master backend integration 文档

## 5.1 硬门槛

P1 必须满足以下约束：

1. 不能只靠 manifest 里声明了 `render / smoke / writeback` 就视为认证完成
2. manifest 必须使用固定 schema，并声明 Deck Master 需要的 contract version
3. smoke 至少要证明命令真实可执行、exit code 可判断、最小 `render_result` 写回样本可生成
4. 如果 Deck Master 生产 build 仍走内部 `contract_smoke` 路径，P1 不得把 `client_delivery_ready` 当作已闭环事实
5. P1 只建立“可认证基础”，不单独承担客户交付放行

## 6. 测试与验证

至少验证：

1. manifest 可解析
2. Deck Master backend verifier 能识别 `render / smoke / writeback`
3. smoke 命令可运行
4. `builder_backend_status()` 不再报 manifest missing
5. 坏 manifest、缺 operation、缺关键脚本时仍会被拒绝
6. 认证后的状态表达不能误导为“客户可交付已完成”

## 7. 成功标准

1. `ppt-master` 能被识别为完整 backend package
2. production backend 认证具备可落地前提，并带最小 smoke 证据
3. Deck Master 可以把它纳入后续 bind/verify 流程
4. 本阶段不会把“manifest 就绪”误表述成“客户版交付就绪”

## 8. 依赖与并发

无上游依赖。  
这是 v1.3.0 的起点包。

## 9. Agent 交付报告

必须输出：

1. 外部仓修改文件
2. backend manifest 字段说明
3. smoke 命令
4. Deck Master 验证命令与真实结果
5. 外部仓提交 SHA
6. 风险与建议评审重点
7. 当前仍未闭环的事实清单，尤其是 production build 是否已真实调用外部 backend、client delivery 是否仍待后续任务放行
