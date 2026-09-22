# Astra Skill 与项目安装适配

日期：2026-09-06。开发基线：PR #28 合并后的 `1864a0e`。
分支：`codex/astra-skill-adaptation`。

本需求由 Codex 配置整理任务转交，目标是减少错误触发、无关预读、重复
确认和重复验证，支持中央 release 配合项目 `.agents/skills` 入口。
延续 Overdefense Governance v1 的当前产物绑定、结构页文案和阶段批处理规则。

## 需求与边界

1. 精简 suite 19 个 skill 的 description 和入口说明，细节按需读取。
2. 区分新建、指定页面修改、只读诊断、客户交付、软件发布；已确认方向的
   局部修改复用 brief、风格与授权，保留其他页面。
3. 移除重复的阶段说明、固定角色播报要求和无条件预读，按变更影响验证。
4. 安装、检查、修复与卸载识别 global/project/custom 根；兼容旧全局安装。
   中央升级和回退不要求重建各项目的稳定链接。
5. 独立生产版 PPT Master 单独归属；项目入口不安装同名 suite 兼容别名。

本轮在代码仓和临时隔离目录实现及验证。迁移本机全局入口、安装当前候选到
共享 release、修改独立 PPT Master、公开发布和其他项目配置均留待后续明确操作。

## 实现

- `scripts/skills/installer.py`：最近项目入口发现，显式 scope/root 解析，
  installation 根输出，central-only 兼容入口，按所有权卸载 suite 链接。
- `scripts/deck_master.py`：现有命令增加 `--scope`、`--project-root`、
  `--agent-skill-dir`；`--links-only` 附加到已验证中央包；
  `uninstall-skill --suite` 删除所选 scope 的 suite 链接。
- `scripts/runtime/skill_route.py`：显式任务路由，在 run 存在但流程不完整时
  仍保留局部修改或诊断意图，输出必要 read_refs；不修改审批和产物状态。
- `skills/`：删除入口重复流程；高密度细节移至自身 references；新增局部修改
  和安装迁移指引；description 与 manifest 同步。
- 旧 `triggers` 字段仅被仓库文档校验器使用，通用 Codex skill 校验不接受。
  本轮删除该重复元数据，文档校验兼容不带 triggers 的标准 frontmatter，
  保留命令参数、入口契约及产物引用校验。
- `validate-skill` CLI 改为只读，不再因追加安装日志而需要用户目录写权限。

## 使用与迁移

2026-09-07 状态更新：用户已移除本机 suite 和工作坊目录。以下仅保留产品
迁移方案，不是恢复安装授权；本分支只在临时隔离目录验证，不重建本机入口。

完整命令与迁移顺序见
[安装指引](../../../skills/deck-master/references/installation.md)。

1. 从候选源码构建新的隔离 release，验证校验和、CLI smoke 和项目内外发现。
2. 审阅完成后，从新版本源码安装中央 release，保留 previous 回退版本。
3. 各指定项目使用 `suite-install --scope project --project-root <project>
   --links-only --include-optional` 创建 18 个入口。
4. 回读项目 suite-status、核心命令与当前 REVISION。升级和 rollback 后检查
   同一链接是否继续指向中央 current。
5. 获得全局切换授权后，使用 `uninstall-skill --target codex --suite
   --scope global` 撤销 suite-owned 全局链接。独立生产版 PPT Master 保留。
6. 在 Codex 新任务中确认项目内发现与项目外不可见；原有任务可能仍带已加载
   的 skill 上下文，该动态发现验证应在实际切换之后执行。

## 验收

见 [验收记录](acceptance.md)。实现验证与模型实际自动选 skill、真实客户交付
分开记录；本次没有新增客户运行或公开版本。
