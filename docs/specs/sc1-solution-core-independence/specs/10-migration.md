# 10｜迁移、回滚与发布收口

## 10.1 三种迁移必须分开

软件迁移：把后端程序与套件方法纳入托管 release。
入口迁移：global/project Skill 和兼容别名的所有权与触发处理。
数据迁移：旧 Run、来源/证据 ID、MBB/narrative、Page Package 和批准版本的格式映射。

三者不得用一个 `rm -rf` 或一次覆盖安装代替。任何实际用户目录、文件路径、原有数据和链接状态均需要 Codex 核验。

## 10.2 全新安装

固定 release 内容可获得 → 校验与建立环境 → 真实标准后端 smoke → 安装套件方法 → Library 运行时 smoke → 状态报告 → 宿主可发现入口 → 首次真实新建。

无用户历史库时不执行默认扫描；库为空显示 empty/not_requested，不阻止标准真实新建。后续用户授权索引时再使用托管 Library 建索引。索引目录属于用户数据，独立于 release 生命周期。

## 10.3 已存在独立 Skill

先产出 dry-run：已有路径、real dir/symlink、owner、版本、文件哈希、用途、拟操作、备份位置和撤销方法。未知所有权视为 external，不自动占有。
只移除/更新本产品拥有的 symlink。需要迁移真正目录时逐项授权；保留独立 PPT Master 的非 Deck 工作流能力。过渡期优先用 project scope 的 Deck Master 主入口，不通过覆盖独立目录解决冲突。

迁移完成必须隔离旧目录再做实际生产验证；隔离是验收手段，不是永久删除指令。通过后可建议用户清理已经证明不再被调用的旧副本；用户数据、品牌包和索引不随之删除。

## 10.4 旧 Run

旧 Run 默认只读兼容；不得自动将其 policy/profile/schema 改为 SC-1，也不宣称其过去输出满足新质量标准。
继续编辑旧 Run 时，先做显式迁移或保留 legacy 运行路线并清楚显示质量标准。要以 SC-1 名义新交付，必须补齐新的当前语义/证据审查。

迁移流程：保存基线快照 → 校验旧 schema → 映射 source/evidence/narrative/page refs → 检查丢失字段/孤儿 refs/冲突 → 在新版本副本上生成目标对象 → 对照内容与顺序 → 失效应失效的审查/批准 → 切换活动版本。

裸 evidence ID 无法找到真实来源时保留 unresolved；不得用 Page Package customer_visible 回填 meaning 后当作原始证据。旧 Blueprint/receipt 不通过改 schema_version 复用为当前可信版本。

## 10.5 中断、并发与回滚

安装中断：current 保持旧 release。动作导入中断：旧结果仍为唯一生效版本，staging 可恢复/丢弃。多个 Agent 回传：预期 input hash/版本号冲突时拒绝后到的旧结果，不覆盖新状态。

软件回滚不回滚用户新素材和索引；若旧程序不能读新 Run 格式，明确拒绝写操作，使用升级前快照或兼容查看，不强行降级数据。把“可回滚软件”与“可无损降级全部新数据”分开。

## 10.6 发布状态

本轮至少区分 `implementation_pending`、`engineering_complete`、`outcome_pending`、`sc1_accepted`。版本编号沿用仓库当前规则，不能因为 Spec 名称 SC-1 就宣称已发布正式 1.0。

发布证据必须包含：锁定来源/依赖、真实标准后端验证、隔离安装、兼容迁移/回滚、核心全链路、内容质量人工对照、高密度 regression 和 provider 真实验收可用状态。

缺少真实 provider/真实 UAT 时明确 outcome_pending；可以合并已验证工程改动，不得伪造验收或把 Fixture 结果改名为 production。
