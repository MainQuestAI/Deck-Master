# 过度防御治理 v1 开发计划

日期：2026-09-01  
主 Spec：[`../00-master-spec.md`](../00-master-spec.md)  
建议分支：`codex/overdefense-governance-v1`

## 执行原则

1. 每个阶段先补失败断言，再改最小代码，再跑 targeted tests。
2. 不用新安全层解决旧安全层过度扩张的问题。
3. P0/P1/P2 分阶段提交，避免 19 个问题混成一个不可回滚大改。
4. 保留真实风险阻断：路径、密钥、外部来源、unsupported fact、客户不可见内部执行语言、P0 finding。
5. 每个状态机修改都要验证 `next-step` 输出可执行命令。

## 阶段 A：P0 闭锁和误杀

目标：修复导致用户无法继续生产 PPT 的直接闭锁。

修改范围：

| 文件 | 动作 |
|---|---|
| `scripts/quality/customer_visible_safety.py` | 精简默认 forbidden terms，区分正常业务词和内部执行词 |
| `scripts/quality/pptx_audit.py` | 客户可见扫描排除 layout/master/presentation 和默认 shape name |
| `scripts/runtime/next_step.py` | 高密度完成态按当前 gate/render/readiness 返回下一步 |
| `scripts/runtime/final_readiness.py` | 引入 profile-aware final readiness 判断 |
| `tests/test_customer_visible_safety.py` | 增加业务词允许、OOXML layout/master 不误杀测试 |
| `tests/test_high_density_builder_v2.py` | 增加 completed high-density next-step 不循环测试 |

退出命令：

```bash
python3 -m pytest tests/test_customer_visible_safety.py tests/test_high_density_builder_v2.py
git diff --check
```

## 阶段 B：人工证明链和审批入口

目标：所有 required 人工动作必须能被用户或 Agent 真实执行。

修改范围：

| 文件 | 动作 |
|---|---|
| `scripts/high_density/integrity.py` | 将 review attestation key 调整为可配置增强门禁 |
| `scripts/high_density/svg.py` | 默认 main review 使用本地 receipt，保留 hash 和 reviewer_id |
| `scripts/high_density/engine.py` | 等待状态返回真实公开命令，移除默认密钥阻断 |
| `scripts/high_density/style.py` | 支持显式风格选择写入 |
| `scripts/deck_master.py` | 增加风格选择和蓝图批准相关 CLI |
| `scripts/high_density/blueprint.py` | Provider receipt 支持显式来源登记，不强绑默认缓存根 |
| `skills/deck-builder-high-density/SKILL.md` | 删除要求用户注入不可用密钥的指引 |
| `tests/test_high_density_builder_v2.py` | 覆盖无 review key 默认生产链、公开命令和 receipt |

退出命令：

```bash
python3 -m pytest tests/test_high_density_builder_v2.py
python3 scripts/deck_master.py build --help
git diff --check
```

## 阶段 C：页面角色化与批量审阅

目标：让质量规则识别页面用途，并减少 64 页人工操作成本。

修改范围：

| 文件 | 动作 |
|---|---|
| `docs/contracts/content-lock.v2.schema.json` | 增加或放宽页面角色相关证据/密度规则 |
| `scripts/high_density/content.py` | 对 cover/section/toc/visual 等角色放宽密度和 evidence 规则 |
| `scripts/high_density/svg.py` | 图片面积 caps 改为 role-aware policy |
| `scripts/quality/pptx_audit.py` | sparse/full-image 检查读取页面角色 |
| `scripts/review/workbench.py` | 增加批量 approve/reject/needs-work |
| `scripts/review/readiness.py` | 批量审阅后正确计算 ready/needs_review |
| `scripts/high_density/engine.py` | 批量 handoff 和失败页 rework queue |
| `tests/test_high_density_builder_v2.py` | 角色化页面和批量 handoff 测试 |
| `tests/test_review_workbench.py` | 批量审阅测试 |

退出命令：

```bash
python3 -m pytest tests/test_high_density_builder_v2.py tests/test_review_workbench.py
git diff --check
```

## 阶段 D：最终放行一致性和残留清理

目标：让 final readiness、delivery validation、export queue、override、output profile 统一。

修改范围：

| 文件 | 动作 |
|---|---|
| `scripts/runtime/final_readiness.py` | gate report freshness/supersession，P1 override 统一 |
| `scripts/delivery/validate.py` | 使用同一套当前 artifact 和 override 规则 |
| `scripts/orchestrate/export_queue.py` | 复用 shared override/freshness 判断 |
| `scripts/runtime/build.py` | 尊重 `output_profile` 的 required outputs |
| `scripts/high_density/engine.py` | `--watch` 可行动状态立即返回 |
| `scripts/high_density/contracts.py` | 历史 user decision receipt 降为兼容读取 |
| `docs/contracts/mbb-user-decision-receipt.v1.schema.json` | 标注 legacy，不作为新生产 required gate |
| `tests/test_final_readiness.py` | 当前 artifact、过期 report、override 测试 |
| `tests/test_delivery_validation.py` | delivery validation 与 final readiness 一致性测试 |
| `tests/test_export_queue.py` | P1 override 和 client queue 测试 |

退出命令：

```bash
python3 -m pytest tests/test_final_readiness.py tests/test_delivery_validation.py tests/test_export_queue.py
python3 -m pytest tests/test_customer_visible_safety.py tests/test_high_density_builder_v2.py
git diff --check
```

## 整包 Definition of Done

1. `ODG-01` 至 `ODG-19` 均有代码处理或明确替代验收。
2. `ODG-R1` 不再出现在用户可见 next-step 或 skill 指引中。
3. 当前 LVMH run 不再要求 `DECK_MASTER_USER_ATTESTATION_KEY` 或 `DECK_MASTER_REVIEW_ATTESTATION_KEY` 才能继续默认生产链。
4. 业务词允许、占位符阻断、unsupported factual values 阻断三类测试同时存在。
5. 高密度 completed 状态不会重复同一条 render gate。
6. 所有新增/修改测试通过。
7. `git diff --check` 通过。

