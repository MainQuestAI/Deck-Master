"""Prepare blinded neutral diagnostic inputs, never model-performance receipts.

Run outside the repository's tracked tree. Reviewer receives only reader/.
Private key and expected findings must remain withheld until review completes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess


SOURCES = [
    {'id': 'S1', 'text': '60 条售后咨询中，18 条首次缺少固件版本。未测补问工时或净节时。'},
    {'id': 'S2', 'text': '一期只检索批准资料，不向设备或工单系统写回。'},
    {'id': 'S3', 'text': '用户补充：来电时客户有时不在设备旁，版本暂缺也必须受理；摘要不急。'},
]
CASES = [
    ('Q01', '证据强度', '18/60 说明可节约 30% 工时。', '18/60 为首次缺版本比例 30%；净节时未测。', 'F0', 'S1', '比例不可外推工时'),
    ('Q02', '章内推理', '版本经常缺失，所以现在全面自动回答。', '先限定批准资料范围；版本暂缺时补问，再验证是否扩大覆盖。', 'F1', 'S1,S2,S3', '推论缺适用条件'),
    ('Q03', '页间推进', 'P1 提高效率。P2 加快响应。P3 提升效率。', 'P1 说明缺版本样本。P2 区分已知和未知路径。P3 推荐一期范围并列待验项。', 'F2', 'S1,S2,S3', '连续页面缺证据与推进'),
    ('Q04', '必要回顾', '三页逐字复述同一宣传句，没有新增信息。', '独立分发的操作页重复“只读、不写回”，便于脱离前页安全使用。', 'F2', 'S2', '无功能重复；保护安全回顾'),
    ('Q05', '必要术语', '以向量召回赋能知识中枢生态。', '向量召回按语义寻找相关资料；客服仍须核对固件版本和出处。', 'F2', 'S1', '无法复述实际动作；保护已解释术语'),
    ('Q06', '自然表达保真', '系统已经全面提升效率。', '建议先在试点使用；净节时还没有测量。', 'F0', 'S1', '改写扩大范围和承诺'),
    ('Q07', '来源版本', '虽然本期 S2 禁止写回，但沿用旧方案的自动写回承诺。', '本期按 S2 的只读限制执行；旧方案写回承诺不用于本期。', 'F0', 'S2', '旧承诺覆盖有效限制'),
    ('Q08', '公平比较', '检索只有收益，摘要只有风险，因此检索必然最优。', '先做可核查出处的检索；摘要是否引入取决于真实阅读负担和新增核验成本。', 'F2', 'S2,S3', '比较口径不对称'),
    ('Q09', '经验落稿', '已用 JTBD：版本必须填完才受理，检索摘要一起上线。', '客户不在设备旁时先受理再补问；一期检索先行，摘要作为后续选项。', 'F1', 'S3', '用户经验未改变正文与推荐'),
    ('Q10', '视觉关系', '已知版本与未知版本均画为自动写回。', '已知版本筛选资料；未知版本转客服补问，两条分支均不自动写回。', 'F0', 'S2,S3', '实际原图、SVG、PPT 端点需要像素验证'),
    ('Q11', '受众表达', '此处补充收益证据，待压缩成三点。', '首期检索提供资料出处；收益仍需另行测量。', 'F2', 'S1,S2', '制作指令未变成正文'),
    ('Q12', '可编辑与复查', '整页位图被声明为所有对象可编辑。', '明确只承诺当前实际可编辑的文本和形状；图片整体替换另列边界。', 'F0', 'artifact', '实际 PPT 对象和原 finding 需验证'),
]


def prepare(destination, seed=20261023, baseline=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    reader = destination / 'reader'
    reader.mkdir()
    root = Path(__file__).resolve().parents[1]
    baseline = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--verify',
                                       (baseline or 'HEAD') + '^{commit}'], text=True).strip()
    paths = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', '--name-only', baseline,
                                    '--', 'skills/deck-master/references'], text=True).splitlines()
    frozen = destination / 'author-resources'
    frozen.mkdir()
    resources = []
    for name in paths:
        raw = subprocess.check_output(['git', '-C', str(root), 'show', baseline + ':' + name])
        relative = Path(name).relative_to('skills/deck-master/references')
        target = frozen / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        resources.append({'path': str(relative), 'sha256': hashlib.sha256(raw).hexdigest()})
    rng = random.Random(seed)
    rows, private = [], []
    for case, topic, bad, good, severity, source, expectation in CASES:
        for version, text in [('problem', bad), ('protected', good)]:
            identity = f'item-{rng.getrandbits(64):016x}'
            payload = {'id': identity, 'task': '帮助业务负责人判断一期实施范围；审查正文及来源，不编辑材料。',
                       'sources': SOURCES, 'manuscript': text,
                       'artifact_requirement': 'actual_pixels_and_objects' if case in ('Q10', 'Q12') else 'text'}
            raw = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
            (reader / f'{identity}.json').write_text(raw, encoding='utf-8')
            rows.append({'id': identity, 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                         'execution_status': 'not_run', 'findings': None,
                         'artifact_ready': case not in ('Q10', 'Q12')})
            private.append({'id': identity, 'case': case, 'variant': version, 'topic': topic,
                            'severity': severity, 'source': source, 'expectation': expectation})
    rng.shuffle(rows)
    manifest = {'seed': seed, 'status': 'prepared_not_run', 'model': None, 'host': None,
                'baseline_resource_commit': baseline, 'shared_A_B_resources': resources,
                'budget': None, 'execution_denominator': 0, 'review_order': rows,
                'groups': {'A': 'existing methods and default continuation',
                           'B': 'same methods and facts; vary selection/continuation/co-creation only',
                           'C': 'not enabled; requires observed B defect and one targeted addition'},
                'required_retention': ['first_draft', 'first_review', 'repaired_draft', 'recheck',
                                      'model_version', 'method_hashes', 'prompt_hash', 'actual_usage'],
                'limitations': ['Author-prepared diagnostic examples are not model outputs.',
                                'Q10/Q12 require actual image/PPT objects before execution.',
                                'No capability result or human comprehension observation is implied.']}
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    (destination / 'private-answer-key.json').write_text(json.dumps(private, ensure_ascii=False, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination')
    parser.add_argument('--seed', type=int, default=20261023)
    parser.add_argument('--baseline', help='Commit containing the identical A/B method resources')
    args = parser.parse_args()
    result = prepare(args.destination, args.seed, args.baseline)
    print(json.dumps({'status': result['status'], 'items': len(result['review_order']),
                      'execution_denominator': result['execution_denominator']}))
