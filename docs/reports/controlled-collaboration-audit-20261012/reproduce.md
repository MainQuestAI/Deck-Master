# 隔离复现方式与证据边界

基线 `af9fd7a6b4d08f753d2f16536a03f386384f49d2`。以下代码只使用仓库现有合成 fixture，在自动清理的临时目录运行；不生图，不调用客户项目，不修改产品代码。P02–P05 的文件是测试产物，不能用于证明渲染、桌面或内容质量。

在仓库根目录使用已有开发虚拟环境执行：

```bash
PYTHONPATH=src:tests/rebuild .venv/bin/python - <<'PY'
import copy
import tempfile
import uuid
from pathlib import Path
import test_content_plan as cp
import test_export as ex
from deck_master import exports, handoff, models, pipeline, service

with tempfile.TemporaryDirectory(prefix='deck-flow-audit-') as temporary:
    root = Path(temporary)
    project, store, task, envelope = cp.flow.__wrapped__(root)
    for page in envelope['pages']:
        page['customer_visible']['body_blocks'] = [
            {'id': 'body', 'type': 'paragraph', 'text': '隔离合成审计正文。'}
        ]
    cp.start(project, task)
    adopted = cp.accept(project, task, envelope)
    result = service.continue_project(project)
    document = store.load_document()
    print('P01', document['task']['existing_decisions'],
          document['design_context']['default_style_id'],
          adopted['next_action'], result['next_action'])

    project, store = ex._passing_deck(root / 'export')
    document = store.load_document()
    exports._gate(store, document, exports._facts(store, document), 'delivery')
    print('P02', 'all host_self; delivery gate allowed')

    ex._set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    try:
        exports._gate(store, document, exports._facts(store, document), 'delivery')
    except exports.ExportError as error:
        print('P03 export', str(error))

    # 为隔离交付政策差异补测试角色槽位；这些不是实际生成的蓝图和预览。
    updated = copy.deepcopy(document)
    for role in ('blueprint', 'svg_preview'):
        updated['pages'][0][role] = pipeline.artifact(
            store, store.staging_dir / 'pptx' / 'page.svg', role, page_id='p1')
    operation = 'audit-slots-' + uuid.uuid4().hex
    updated = models.bump_revision(updated, {
        'operation_id': operation, 'kind': 'task_update',
        'description': 'synthetic audit slots', 'read_set': []})
    store.commit_change(base_revision=document['revision_id'],
                        document=updated, operation_id=operation)
    result = handoff.check_handoff(
        project, file_path=store.staging_dir / 'pptx' / 'deck.pptx', purpose='delivery')
    print('P03 handoff', result['status'], result['gaps'])

    ex._review(store, store.load_document(), 'professional_use', 'pass', seed='self')
    document = store.load_document()
    exports._gate(store, document, exports._facts(store, document), 'delivery')
    print('P04', store.read_object_json(document['reviews'][-1])['reviewer'], 'allowed')

    review = store.read_object_json(document['reviews'][-1])
    review['status'] = 'not_evaluated'
    review['subjects'] = [document['outputs']['pptx']]
    models.validate_schema('review', review)
    updated = copy.deepcopy(document)
    updated['reviews'][-1] = store.put_json_object(review)
    operation = 'audit-review-' + uuid.uuid4().hex
    updated = models.bump_revision(updated, {
        'operation_id': operation, 'kind': 'task_update',
        'description': 'synthetic unevaluated review', 'read_set': []})
    store.commit_change(base_revision=document['revision_id'],
                        document=updated, operation_id=operation)
    document = store.load_document()
    exports._gate(store, document, exports._facts(store, document), 'delivery')
    print('P05', 'PPT-only not_evaluated professional_use; delivery gate allowed')
PY
```

预期是复现当前缺口，而不是断言这些行为正确。P05 通过 fixture 插入合法形状记录以检验核心 gate，没有宣称已从 UI 构造同一记录。修复后的反向验收应优先通过正式服务/CLI/HTTP 入口，覆盖非法记录不可提交与底层 gate 不放行两层。

旧新阶段合同可只读对照：

```bash
git show 25a27e31 -- skills/stage-contracts.json
git show 2ce3004b -- skills/deck-master/SKILL.md
git show 1c2bb80c -- src/deck_master/service.py
git show --stat abb84a19
git show --stat ba8cebf5
```
