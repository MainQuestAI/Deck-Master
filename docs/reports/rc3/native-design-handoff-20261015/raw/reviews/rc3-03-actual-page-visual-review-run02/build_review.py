from pathlib import Path
import collections
import copy
import datetime
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile

from deck_master.models import validate_review_semantics
from deck_master.store import Store

OUT = Path('/workspace/work/rc3/reviews/rc3-03-actual-page-visual-review-run02')
PROJECT = Path('/workspace/work/rc3/native-image-pilot-03/run-02-project')
PACKET = Path('/workspace/work/rc3/native-image-pilot-03/run-02-page-visual-review-5dbdf72')
SVG_PATH = Path('/workspace/work/rc3/native-image-pilot-03/run-02-svg-native-author/p04-native-v1.svg')
PPT_PATH = Path('/workspace/work/rc3/native-image-pilot-03/run-02-native-ppt/native/deck.pptx')
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
EXECUTION = '/root/rc3_03_actual_page_visual_review'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


fixed = json.loads((PACKET / 'fixed-page.json').read_text())
binding = json.loads((OUT / 'current-subjects-dependencies.json').read_text())
subjects, deps = binding['subjects'], binding['dependencies']
entry = binding['entry']
visible = fixed['customer_visible']
atoms = [
    ('atom:p04:title', '顶部标题', visible['title']),
    ('atom:p04:subtitle', '标题下副标题', visible['subtitle']),
]
for label in visible['labels']:
    atoms.append((f"atom:p04:label:{label['id']}:text", f"主链 {label['id']} 节点", label['text']))
for block in visible['body_blocks']:
    if block['type'] == 'paragraph':
        atoms.append((f"atom:p04:block:{block['id']}:text", '异常模块标题', block['text']))
    if block['type'] == 'table':
        for col in block['columns']:
            atoms.append((f"atom:p04:column:{block['id']}:{col['id']}:label", f"表头 {col['id']} 列", col['label']))
        for row in block['rows']:
            for cell in row['cells']:
                atoms.append((f"atom:p04:cell:{block['id']}:{row['id']}:{cell['column_id']}:display_text", f"异常表 {row['id']} 行 / {cell['column_id']} 列", cell['display_text']))
for callout in visible['callouts']:
    atoms.append((f"atom:p04:callout:{callout['id']}:text", '底部边界提示', callout['text']))

ns = {'s': 'http://www.w3.org/2000/svg', 'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
svg = ET.fromstring(SVG_PATH.read_bytes())
svg_atoms = {t.attrib['data-atom-id']: ''.join(t.itertext()) for t in svg.findall('.//s:text', ns) if t.attrib.get('data-atom-id')}
with zipfile.ZipFile(PPT_PATH) as z:
    ppt_slide = ET.fromstring(z.read('ppt/slides/slide1.xml'))
    ppt_atoms = collections.defaultdict(str)
    ppt_sizes = collections.defaultdict(list)
    for shape in ppt_slide.findall('.//p:sp', ns):
        name = shape.find('.//p:cNvPr', ns).attrib.get('name')
        if name and name.startswith('atom:'):
            ppt_atoms[name] += ''.join(t.text or '' for t in shape.findall('.//a:t', ns))
            ppt_sizes[name].extend(float(r.attrib['sz']) / 100 for r in shape.findall('.//a:rPr', ns) if 'sz' in r.attrib)
    note_tree = ET.fromstring(z.read('ppt/notesSlides/notesSlide1.xml'))
    notes_text = '\n'.join(''.join(t.text or '' for t in para.findall('.//a:t', ns)) for para in note_tree.findall('.//a:p', ns))

checks = []
for atom_id, location, expected in atoms:
    checks.append({
        'atom_id': atom_id, 'location': location, 'expected': expected,
        'svg_text': svg_atoms.get(atom_id), 'pptx_native_text': ppt_atoms.get(atom_id),
        'svg_exact_equality': svg_atoms.get(atom_id) == expected,
        'pptx_exact_equality': ppt_atoms.get(atom_id) == expected,
        'pptx_font_sizes_pt': sorted(set(ppt_sizes[atom_id])),
        'actual_visual_observation': '在原始蓝图、当前 SVG 预览、PPTX 实际渲染中逐句可辨读；未见遗漏或语义变更。原图仅作肉眼语义核对，不声称光栅 Unicode 逐码点相等。',
    })
save('actual-atom-text-checks.json', checks)
assert len(checks) == 17 and all(c['svg_exact_equality'] and c['pptx_exact_equality'] for c in checks)
assert notes_text == fixed['speaker_notes']

store = Store(PROJECT)
records = json.loads((OUT / 'current-artifact-records.json').read_text())
byte_binding = {}
for role, local in [('blueprint', Path('/workspace/work/rc3/native-image-pilot-03/run-02-native/original-blueprint.png')), ('svg', SVG_PATH), ('svg_preview', Path('/workspace/work/rc3/native-image-pilot-03/run-02-native-svg-preview/actual-p04-preview.png'))]:
    local_data = local.read_bytes()
    ref = records[role]['file']
    byte_binding[role] = {'local_path': str(local), 'local_sha256': hashlib.sha256(local_data).hexdigest(), 'stored_file_ref': ref, 'bytes_equal_to_current_stored_file': local_data == store.read_object_bytes(ref)}
assert all(v['bytes_equal_to_current_stored_file'] for v in byte_binding.values())
save('inspected-bytes-current-artifact-binding.json', byte_binding)

prior_path = Path('/workspace/work/rc3/reviews/rc3-03-actual-candidate-review-run02/assessment.json')
prior = json.loads(prior_path.read_text())
save('prior-F01-F04-as-read.json', {'source': str(prior_path), 'sha256': hashlib.sha256(prior_path.read_bytes()).hexdigest(), 'findings': prior['findings']})

evidence = [entry['blueprint'], entry['svg'], entry['svg_preview']]


def finding(fid, kind, impact, elements, message, expected, actual, resolution, reason):
    return {'finding_id': fid, 'kind': kind, 'impact': impact, 'page_id': 'p04', 'element_refs': elements, 'message': message, 'expected': expected, 'actual': actual, 'evidence': copy.deepcopy(evidence), 'resolution': resolution, 'resolution_reason': reason}


f01 = finding('F01', 'design', 'must_fix', ['collect-retrieve', 'main-chain', 'main-chain-frozen-qualification'],
    '原图主链条件与四节点的视觉绑定弱；当前重建已修复这一局部用途问题。',
    '固定 requirements：主链只适用于条件可核对情形。只读检索的适用条件须就近约束四节点主链。',
    '原图只有标题与表格继续条件间接约束；当前在四节点共同框内、卡片上方以蓝色粗体完整显示“主链只适用于条件可核对情形。”。SVG 与实际 PPT 渲染均可见。',
    'fixed', '复查当前可见分组与已有冻结限定，未新增业务事实。未知行仍规定取得可核查条件后按主链继续；不适用行仍要求人工确认或保留未决。')
f02 = finding('F02', 'design', 'must_fix', ['main-chain-frame', 'table-border', 'boundary-background'],
    '原图外边距不足48px；当前1600×900稿已恢复安全边距。',
    'recipe.spacing：四周至少48px。',
    '当前主模块外框x=50至1550，底部提示y=762至850；最大1.5px描边计入后左右及底部净边距49.25px。顶部标题肉眼可见字形约y=54起，未逼近48px边界。',
    'fixed', '原始PNG仍保留，不裁剪、不重编码；当前SVG与PPT渲染外部留白充足且无裁字。')
f03 = finding('F03', 'design', 'must_fix', ['table-border', 'boundary-background'],
    '原图表格到边界提示不足24px；当前模块间距已修复。',
    'recipe.spacing：表格与边界提示保留至少24px。',
    '当前表格几何底边734px，提示顶边762px，间隔28px；计两侧描边后的净空约26.75px。PPT实际渲染保持模块分离。',
    'fixed', '保持全部六个单元格原文及24px正文，未靠删字或缩小正文制造留白。')
f04 = finding('F04', 'artifact', 'needs_judgment', ['original-blueprint', 'canvas'],
    '原始图1672×941与指令1600×900的差异必须永久保留。',
    '原始尺寸及SHA不改写；另建1600×900可编辑稿并如实记录尺寸差异。',
    '直接查看和读取PNG头：原图1672×941，SHA256=8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c；当前SVG/预览1600×900，PPT头less渲染2000×1126。',
    'accepted_variance', '本次接受差异仅用于视觉参考到原生重建的单页工程评阅。原图未被登记成1600×900或改标生成来源；1600×900重建保留固定全部内容、次序和关系。PPT渲染像素尺寸属于导出采样，不是原图尺寸。')
v01 = finding('V01', 'design', 'needs_judgment', ['main-chain', 'exceptions-table', 'boundary-module'],
    '当前稿与蓝图有可见重排，视觉保真按信息层级与业务关系判断。',
    '保留原图四节点→异常表→边界的阅读顺序、方向、行列归属及蓝白配色；允许落实既有修复要求。',
    '移除原图1–4装饰编号；四节点改为等宽、左对齐文字并增加共同条件框；表头改左对齐；边界提示由单行改两行且前缀不再单独加粗；标题整体较原图小。',
    'accepted_variance', '无事实、节点或关系丢失。顺序由空间与三条箭头清楚表达；24px正文/40px标题符合固定recipe，表头粗体与提示框仍表达层级。此结论不是逐像素相同。')
a01 = finding('A01', 'observation', 'advisory', ['review-submit', 'atom:p04:cell:exceptions:unsuitable:handoff:display_text'],
    '主链与异常的完整理解仍依赖阅读下方表格；保留这一表达边界。',
    '不把主链或找到资料理解成引用已获准、故障已解决、AI自动提交。',
    '四节点主链仍是简化顺序，未知与引用冲突/不适用通过两行表格说明，并未画分叉/返回箭头。正文明确人员提交、候选不可直接采用、无法确认则保留未决。',
    'open', '固定稿原本要求上方主链加下方表格；当前未增造分支。对整页阅读的模型判断为可理解，不代替真实受众测试或试讲。')

limitations = [
    '仅p04 page_visual单页工程评阅；不是content、conversion或privacy的全稿最终评阅。PPT实际渲染只作为本页补充观察。',
    '真实专业/人类评阅、Owner接受、真实受众理解、现场投影与PowerPoint桌面编辑均NOT_RUN。',
    '没有审阅或关闭公平E2/E3、其他七页完整交付、完整RC3集群验收；未运行其他E1臂。',
    '原始image_gen输出来源保留8057905；当前5dbdf720固定安装只用于SDK评阅与检查，不是原始蓝图的生成版本。',
    'host_attested是Root实际观察非作者模型spawn及本次SDK claim的Host层来源。Root尚未在本记录创建时观察本agent的FINAL/completed；它会在真实事件发生后另存完成观察。本记录没有平台签名、人类身份或未来完成receipt。',
    '当前工作单ppt_preview和outputs为空；本次补充查看的本地PPTX/渲染通过实际文件SHA记录，不伪装成已纳入正式Document输出或conversion最终通过。',
    '密集长句均可辨读且没有超出固定字号，但70秒讲述与真实受众理解仍需实际人员环境验证。',
]

common = [
    '真实独立非作者native model执行；execution_ref=/root/rc3_03_actual_page_visual_review；三图均通过view_image(detail=original)实际查看，先形成自身图像语义判断，再读技术readback。',
    '全文读取固定packet五文件与实际SVG；使用安装SDK读取task方法全文/hash及当前subjects/deps。完整固定来源S1–S3及p04相关Narrative节点/Plan角色已读。全稿Narrative/Plan的大型输出曾截断，不将其视为全稿完整审阅。',
    '原始PNG1672×941与目标1600×900差异保留；来源8057905不改标为当前5dbdf720安装。',
    '当前正式subjects为Page、blueprint、SVG、SVG preview四个不可变对象；依赖为content:page:p04、blueprint:p04、artifact:svg:p04、style:p04，无allowed assets。',
    '所有判断仅支持该页该次page_visual工程范围。未关闭公平E2/E3、完整八页交付、Owner/受众/PowerPoint桌面或整体RC3验收。',
    'Host层来源依据Root已观察spawn与SDK claim；Root的FINAL/completed完成观察将在实际发生后另存。identity_receipt=null，不声称平台或人类认证。',
]
dim_observations = {
    'blueprint_content': [
        '逐句核对17个固定可见原子在三图中的语义及全部限定：仍待验证、只读/许可/来源、采用与未采用及原因、现有系统人员提交、能补/不能补/取得条件后、启动前明确、无法确认/冲突/不适用/仍不确定、候选不得直接采用、未决及找到资料不等于解决、AI不自动提交/修改/关闭、非诊断或批准均保留。',
        'SVG全部17个atom的可见tspan拼接与固定正文完全相等；PPT原生文字按atom分组也全部相等。这是图像逐句审阅后的补充核对，不以字符串计数代替视觉判断。',
        '2×3数据表的unknown/unsuitable两行及trigger/action/handoff三列归属正确；四节点与三条向右关系保持，未新增自动提交、已核准或已解决的支路。',
    ],
    'blueprint_fidelity': [
        '蓝图白底深蓝文字、浅蓝框、横向四节点三箭头、下方异常表、底部边界提示的总体层级和阅读顺序保留。逐像素及排版并非相同：编号移除、共同条件框、左对齐表头、文字重流、提示拆两行。',
        '新增可见条件句来自固定requirements，处于共同主链框内；它修复原图F01，未从蓝图引入额外事实。三条实线箭头均向右，对应collect→retrieve→review→submit。',
        'PPT实际headless渲染与当前SVG预览在信息、行列归属、换行、层级和关系上无可见损失。PPTX XML有59个原生shape/35个文字shape，无picture或媒体嵌入；不据此声称桌面可编辑体验已验收。',
    ],
    'readability': [
        '在1600×900 SVG预览与2000×1126 PPT实际渲染中，标题、表头、每行正文及边界提示可逐句辨读，没有观察到裁字、重叠、缺字、行列串读或箭头反向。',
        '原生PPT标题/小节标题30pt，副标题/正文/表头/边界18pt；对应SVG40px/24px。标题粗体、表头粗体、蓝色主链条件、分隔表格和边界框构成明确层级。',
        '最大3行的表格单元格采用30px基线间距，左内距18px；外框计描边左右/底部至少49.25px；表到提示净空约26.75px。正文保留密度但没有通过缩字或删除限定逃避。',
        '阅读顺序为标题/副标题→带条件的主链→异常表→范围边界；异常需要读完整表格。真实投影距离、现场光照和受众阅读速度尚未检验。',
    ],
}
dim_findings = {'blueprint_content': [f01, a01], 'blueprint_fidelity': [f01, f04, v01, a01], 'readability': [f02, f03, a01]}
reviews = []
for kind in ['blueprint_content', 'blueprint_fidelity', 'readability']:
    review = {
        'schema_version': 'deck_review.v2', 'review_id': f'rc3-03-run02-p04-{kind}', 'kind': kind,
        'review_stage': 'page_visual', 'status': 'pass', 'subjects': copy.deepcopy(subjects),
        'dependencies': copy.deepcopy(deps),
        'reviewer': {'type': 'independent_host', 'id': EXECUTION, 'execution_ref': EXECUTION, 'independence_confirmed': True, 'identity_receipt': None, 'evidence_ref': None, 'assurance': 'host_attested'},
        'observations': common + dim_observations[kind], 'findings': copy.deepcopy(dim_findings[kind]),
        'created_at': NOW, 'replaces': None,
    }
    validate_review_semantics(review)
    reviews.append(review)

envelope = {'kind': 'review', 'reviews': reviews, 'notes': 'Actual independent native non-author model page_visual engineering review for p04 only. Three actual images inspected; original provenance and dimensions retained. No human/platform/desktop/global acceptance.'}
save('raw-accept-payload.json', envelope)
assessment = {
    'schema_version': 'rc3_actual_page_visual_assessment.v1', 'reviewed_at': NOW,
    'page_id': 'p04', 'task_id': '89aefcb92514', 'operation_id': 'review-a39964acba5f',
    'produced_against': binding['task']['produced_against'], 'execution_ref': EXECUTION,
    'reviewer_role': 'actual native non-author model reviewer',
    'scope_verdict': 'PASS: p04 page_visual engineering only',
    'dimension_results': {k: 'pass' for k in dim_observations},
    'decision_reason': '本人实际查看三张图后，确认固定全部17原子和限定语、四节点三向右关系、六个异常表单元格归属以及正文阅读顺序保留。当前主链条件分组明确，安全边距和模块间距修复。原生PPT实际渲染未见当前SVG的信息/关系损失。差异及未运行验收明确保留。',
    'method_release': binding['task']['method_release'], 'subjects': subjects, 'dependencies': deps,
    'image_views': json.loads((OUT / 'actual-image-view-record.json').read_text()),
    'fixed_atom_checks': checks,
    'qualifier_checks': dim_observations['blueprint_content'],
    'directed_relationship_checks': [{'edge': edge, 'observation': '在原图、SVG预览与PPT实际渲染中连接对应相邻节点并向右；当前条件句共同约束主链，未画AI自动提交分支。'} for edge in fixed['visual_spec']['edges']],
    'table_ownership': {'columns': ['trigger', 'action', 'handoff'], 'rows': ['unknown', 'unsuitable'], 'all_six_cells': '逐格核对完整正文与限定，行列归属无误；视觉分隔清楚。'},
    'reading_order': '标题→副标题→共同条件与四节点（左到右）→异常标题→表头及两行三列表格→底部范围/能力边界',
    'visual_differences': v01, 'findings': [f01, f02, f03, f04, v01, a01],
    'residual_interpretation_risk': '主链仍是简化顺序，表格承载未知和引用不适用等例外。只看上半页不能获得完整分支；必须读全页及结合固定cues。当前文本与分组足以支持模型工程评阅的可理解判断，但受众是否误读需真实受众验证。未把此风险伪称已被受众验收。',
    'supporting_pptx_readback': {'pptx_sha256': hashlib.sha256(PPT_PATH.read_bytes()).hexdigest(), 'native_shapes': 59, 'text_shapes': 35, 'picture_count': 0, 'notes_equal_fixed_page': notes_text == fixed['speaker_notes'], 'notes_sha256': hashlib.sha256(notes_text.encode()).hexdigest(), 'caution': '本人读XML和实际图所得；不引用author工程自评或actual-readback的status作为独立结论。'},
    'limitations': limitations,
    'provenance': {'assurance': 'host_attested', 'identity_receipt': None, 'existing_root_observation': 'Root实际观察本agent spawn与真实SDK claim；Root后续消息确认按v2 host_attested记录。', 'completion_observation': 'not yet issued at assessment creation; Root will save only after actual FINAL/completed', 'platform_signature': 'none', 'human_signature': 'none'},
    'sdk_submission': 'payload prepared; actual response recorded separately after service.accept_result',
}
save('assessment.json', assessment)

paths = [PACKET / n for n in ['task.json', 'workorder.json', 'fixed-page.json', 'prepared-method-bytes.json', 'current-p04-entry.json']]
paths += [SVG_PATH, PPT_PATH, Path('/workspace/work/rc3/native-image-pilot-03/run-02-native/original-blueprint.png'), Path('/workspace/work/rc3/native-image-pilot-03/run-02-native-svg-preview/actual-p04-preview.png'), Path('/workspace/work/rc3/native-image-pilot-03/run-02-native-ppt/rendered/page-1.png'), Path('/workspace/work/rc3/native-image-pilot-03/run-02-native-ppt/actual-readback.json'), Path('/workspace/work/rc3/native-image-pilot-03/run-02-native-ppt/actual-svg-ir.json'), prior_path, Path('/workspace/work/rc3/candidate-03-5dbdf72/manifest.json')]
for ref in subjects:
    paths.append(PROJECT / ref['path'])
paths += [PROJECT / ref['path'] for ref in [fixed['content_mapping']['narrative_ref'], {'path': '.deckmaster/objects/30/30e2c94b81273eee0a4205203dc0ed63c05fdcd9dd9e5c302e73a4f0bb31b6ef.json'}]]
save('read-input-hashes.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size, 'reading_scope': 'entire fixed packet / SVG; actual images visually inspected; binary PPTX ZIP/XML; supporting technical JSON; Narrative/Plan p04 relevant material (full large output not counted as full-deck review)'} for p in paths])
print(json.dumps({'verdict': assessment['scope_verdict'], 'reviews': [{'kind': r['kind'], 'status': r['status'], 'schema': r['schema_version']} for r in reviews], '17_atom_exact_checks': all(c['svg_exact_equality'] and c['pptx_exact_equality'] for c in checks), 'notes_exact': notes_text == fixed['speaker_notes'], 'payload': str(OUT / 'raw-accept-payload.json')}, ensure_ascii=False, indent=2))
