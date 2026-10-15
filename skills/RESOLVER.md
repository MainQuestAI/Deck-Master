# Deck Master 职责路由

| 原始意图 | 公开入口 | Runtime 范围 |
| --- | --- | --- |
| 新任务、完整作品、跨职责续作/修改、职责不明 | deck-master | 原始要求对应的 full_deck/content_only/design_trial/review_only/edit |
| 只策划、写逐页稿、只写口播、完整内容包 | deck-content | content_only + plan_only/write_only/speech_only/content_full |
| 设计方案、模板品牌、限定样页 | deck-design | design_trial，固定页/层/预算 |
| 只审项目、外部文件或明确文件集 | deck-review | review_only，strict persistence=none |

点名优先采用明确职责；自然语言按用户所求产物路由，不凭名称产生授权。
Master 连续调用传同一项目和固定 scope；恢复重读当前 request、scope、completion、暂停/撤回与调用事实，不建第二套状态。
四入口都先解析实际加载的 Skill 所属 release，用同版 Python/Runtime；共享方法只有 deck-master/references。
