from pathlib import Path
import collections
import copy
import datetime
import hashlib
import json
import xml.etree.ElementTree as ET

from deck_master.models import validate_review_semantics
from deck_master.store import Store

OUT = Path('/workspace/work/rc3/reviews/rc3-03-actual-page-visual-review-run04-v2')
PROJECT = Path('/workspace/work/rc3/native-image-pilot-03/run-02-project')
ROOT = Path('/workspace/work/rc3/native-image-pilot-03')
PACKET = ROOT / 'run-04-page-visual-review-v2'
SVG = ROOT / 'run-03-svg-physical-type-repair/p04-native-v2.svg'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
EXECUTION = '/root/rc3_03_actual_page_visual_review'


def save(n, v):
    (OUT / n).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')


fixed = json.loads((PACKET / 'fixed-page.json').read_text())
work = json.loads((PACKET / 'workorder.json').read_text())
binding = json.loads((OUT / 'current-subjects-dependencies.json').read_text())
entry, subjects, deps = binding['entry'], binding['subjects'], binding['dependencies']
native = json.loads((OUT / 'independent-native-pptx-physical-and-text-inspection.json').read_text())
history = json.loads((OUT / 'independent-old-artifact-failure-history.json').read_text())
views = json.loads((OUT / 'actual-image-view-record.json').read_text())
f07_measure = json.loads((OUT / 'F07-precise-measurement.json').read_text())
visible = fixed['customer_visible']
atoms = [('atom:p04:title', '顶部标题', visible['title']), ('atom:p04:subtitle', '副标题', visible['subtitle'])]
for label in visible['labels']:
    atoms.append((f"atom:p04:label:{label['id']}:text", f"主链{label['id']}", label['text']))
for block in visible['body_blocks']:
    if block['type'] == 'paragraph':
        atoms.append((f"atom:p04:block:{block['id']}:text", '异常模块标题', block['text']))
    elif block['type'] == 'table':
        for col in block['columns']:
            atoms.append((f"atom:p04:column:{block['id']}:{col['id']}:label", f"表头{col['id']}", col['label']))
        for row in block['rows']:
            for cell in row['cells']:
                atoms.append((f"atom:p04:cell:{block['id']}:{row['id']}:{cell['column_id']}:display_text", f"表格{row['id']}行/{cell['column_id']}列", cell['display_text']))
for callout in visible['callouts']:
    atoms.append((f"atom:p04:callout:{callout['id']}:text", '底部边界', callout['text']))
ns = {'s': 'http://www.w3.org/2000/svg'}
svg_tree = ET.fromstring(SVG.read_bytes())
svg_atoms = {n.attrib['data-atom-id']: ''.join(n.itertext()) for n in svg_tree.findall('.//s:text', ns) if n.attrib.get('data-atom-id')}
ppt_atoms = collections.defaultdict(str)
for run in native['runs']:
    if run['shape_name'].startswith('atom:'):
        ppt_atoms[run['shape_name']] += run['text']
checks = []
for atom_id, location, expected in atoms:
    checks.append({'atom_id': atom_id, 'location': location, 'fixed_text': expected, 'svg_visible_text': svg_atoms.get(atom_id), 'pptx_native_text': ppt_atoms.get(atom_id), 'svg_exact_equality': svg_atoms.get(atom_id) == expected, 'pptx_exact_equality': ppt_atoms.get(atom_id) == expected, 'independent_visual_observation': '本轮三图逐句肉眼核对可辨读、限定保留、行列归属正确；不从光栅声称Unicode逐码点相等。'})
save('actual-17-atom-checks.json', checks)
assert len(checks) == 17 and all(c['svg_exact_equality'] and c['pptx_exact_equality'] for c in checks)
assert native['notes_text'] == fixed['speaker_notes']
assert native['physical_matches'] and native['all_runs_meet_role_floor']

store = Store(PROJECT)
local_files = {'blueprint': ROOT / 'run-02-native/original-blueprint.png', 'svg': SVG, 'svg_preview': ROOT / 'run-04-native-svg-v2-preview/actual-p04-preview.png'}
byte_bindings = {}
for role, path in local_files.items():
    artifact = store.read_object_json(entry[role])
    data = path.read_bytes()
    byte_bindings[role] = {'artifact_ref': entry[role], 'file_ref': artifact['file'], 'local_path': str(path), 'local_sha256': hashlib.sha256(data).hexdigest(), 'same_bytes_as_current': data == store.read_object_bytes(artifact['file'])}
assert all(b['same_bytes_as_current'] for b in byte_bindings.values())
save('current-inspected-byte-binding.json', byte_bindings)

evidence = [entry['blueprint'], entry['svg'], entry['svg_preview']]


def finding(fid, kind, impact, elements, message, expected, actual, resolution, reason):
    return {'finding_id': fid, 'kind': kind, 'impact': impact, 'page_id': 'p04', 'element_refs': elements, 'message': message, 'expected': expected, 'actual': actual, 'evidence': copy.deepcopy(evidence), 'resolution': resolution, 'resolution_reason': reason}


f01 = finding('F01', 'design', 'must_fix', ['collect-retrieve', 'main-chain', 'main-chain-frozen-qualification'], '本轮重新查看确认原图主链条件绑定问题在SVGv2及新PPT中保持修复。', '固定限定“主链只适用于条件可核对情形。”须就近约束四节点主链。', '蓝色30px限定处于四节点共同框内；PPT实际18pt。未知行仍以取得可核查条件后恢复主链，引用例外仍保留人工确认/未决。', 'fixed', '按本轮新图与新SVG独立复查，不复制旧PASS。未新增事实或自动提交分支。')
f02 = finding('F02', 'design', 'must_fix', ['main-chain-frame', 'table-border', 'boundary-background'], '新稿四周安全边距保持符合固定要求。', '四周至少48px。', '主要外框x=50…1550；底部提示止于850px。计1.5px描边后左右与底部净边距49.25px；顶部实际标题字形位于48px安全边界之内。', 'fixed', '本轮两张新图均无裁字，原图边距不足的历史原件不修改。')
f03 = finding('F03', 'design', 'must_fix', ['table-border', 'boundary-background'], '新稿表格至边界提示的模块间隔仍符合要求。', '模块净空至少24px。', '表格几何底736，边界提示顶762；计描边净空约24.75逻辑px。实际PPT相邻边线之间可见分离。', 'fixed', '保留完整正文与所需字号。此项不抵消新发现F07的单元格内部留白不足。')
f04 = finding('F04', 'artifact', 'needs_judgment', ['original-blueprint', 'canvas'], '原始图与目标画布的尺寸差异继续如实保留。', '原始1672×941及SHA和8057905生成来源不改写；新建目标1600×900。', '原图1672×941、SHA8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c；新SVG预览1600×900；实际PPT渲染1601×900，属于导出像素取整。', 'accepted_variance', '不把原始蓝图改成1600×900或5dbdf720来源；当前重建保留固定稿内容和关系，渲染宽度1px取整未见信息或比例损失。')
f05 = finding('F05', 'conversion', 'must_fix', ['ppt/presentation.xml:p:sldSz'], '仅对本轮精确新PPTX关闭物理尺寸问题。', '13.333333333333334×7.5in，即12192000×6858000EMU。', '本人直接读新PPTX4c951dde9044506ad7cade8e06de13c50ed25e5173210265cd2b7c61d2c38ef6：cx12192000/cy6858000，精确匹配；type仍为screen4x3，单列A02保留。', 'fixed', '独立XML与新实际渲染共同核对。run02旧PPTX仍为15240000×8572500，其失败不回写；Root工程调用/单位指令修正与正式pipeline in*96实现证据另存。')
f06 = finding('F06', 'conversion', 'must_fix', ['ppt/slides/slide1.xml:a:rPr@sz'], '仅对本轮精确新PPTX关闭逐run字号问题。', '固定两个heading atom至少30pt，其余可见run至少18pt；不根据实际字号或加粗反推角色。', '本人直接读取新PPTX36个可见run：exact heading atom白名单2段均30pt，其余34段均18pt。SVG对应标题50px、正文30px，目标物理转换正确。', 'fixed', 'run03旧正确物理尺寸PPTX8affb8957e63919b73ea8be326786b5a322b1bd94418b0bba53a6c092c66ca1e的35段14.4/24pt不足历史另读确认且保留；本项通过不抵消F07。')
f07 = finding('F07', 'readability', 'must_fix', ['atom:p04:column:exceptions:trigger:label', 'atom:p04:column:exceptions:action:label', 'atom:p04:column:exceptions:handoff:label', 'atom:p04:cell:exceptions:unknown:action:display_text', 'atom:p04:cell:exceptions:unknown:handoff:display_text', 'atom:p04:cell:exceptions:unsuitable:trigger:display_text', 'atom:p04:cell:exceptions:unsuitable:action:display_text', 'atom:p04:cell:exceptions:unsuitable:handoff:display_text'], '当前实际PPT渲染的表头及三行单元格底部净空未达到固定12px。文字完整可读，但显式留白下限不满足。', 'recipe.spacing：单元格内距至少12px。保持全文、实际18pt正文/30pt标题及其他安全间隔。', '120dpi、1601×900实际PNG中表头墨迹底y481，表头边线像素y491/492，净空约9–10px；unknown三行正文墨迹底y602/边线613/614，unsuitable墨迹底y724/边线735/736，净空约10–11px。对应SVG表头净空13px、三行正文14px；实际native墨迹约下移3px。原生XML行边几何仍492/614/736逻辑px。', 'open', '需作者只调整本页表格垂直排布/基线，保持固定文本与实际字号，重新渲染物理目标PPT并核对≥12px。没有观察到裁字、内容失真或关系丢失；此FAIL针对明确工程下限，不夸大为不可读或广泛compiler缺陷。')
v01 = finding('V01', 'design', 'needs_judgment', ['main-chain', 'exceptions-table', 'boundary-module'], '新稿保持蓝图的信息层级和业务关系，排版仍有明确可解释差异。', '四节点三箭头→异常表→边界的层级、方向、行列归属与固定正文保留。', '原图装饰编号未继承，主链加共同条件框、表头左对齐、边界两行；SVGv2相较v1字号由24/40增为30/50px并重新换行。', 'accepted_variance', '业务信息、全部限定、节点和关系无损失；更大的文字本身可辨读。F07所述内部留白单独FAIL，不能被本项保真接受所掩盖。')
a01 = finding('A01', 'observation', 'advisory', ['review-submit', 'atom:p04:cell:exceptions:unsuitable:handoff:display_text'], '完整理解异常仍需阅读表格，保留模型工程评阅的解释边界。', '不把主链或资料检索理解成引用获批、故障解决或AI自动提交。', '固定稿依然通过两行表格承载未知和引用异常，没有显式分叉/返回连线；当前文字明确人工确认、继续未决与人员提交。', 'open', '本轮肉眼全页可理解的判断不代替真实受众测试、试讲或专业认可。')
a02 = finding('A02', 'artifact', 'advisory', ['ppt/presentation.xml:p:sldSz@type'], '保留原生PPTX type标签与实际宽高的不同。', '物理尺寸以精确cx/cy核对，不以type标签代替。', 'type="screen4x3"仍存在；实际cx/cy明确为16:9且目标13⅓×7.5in，当前headless渲染未见拉伸。', 'open', '作为metadata差异留证；本轮没有PowerPoint桌面证据，不扩写其桌面影响。F05只关闭实际物理尺寸。')

closures = {'scope': 'new precise artifact only; old evidence immutable', 'new_svg_sha256': hashlib.sha256(SVG.read_bytes()).hexdigest(), 'new_pptx_sha256': native['pptx_sha256'], 'new_render_sha256': views[2]['sha256'], 'F05': f05, 'F06': f06, 'new_open_F07': f07, 'independent_native_check': 'independent-native-pptx-physical-and-text-inspection.json', 'independent_failure_history': history}
save('F05-F06-new-artifact-closure.json', closures)

prior = {x['kind']: x for x in work['prior_page_visual_findings']}
common = [
    '实际native非作者模型复评；canonical execution_ref=/root/rc3_03_actual_page_visual_review；本轮原图及两张新图均由view_image(original)实际查看，先形成自身语义观察再读技术记录。',
    '正式新Task405175566aaf，绑定当前Page/blueprint/SVGv2/SVGpreview四对象及当前content/blueprint/svg/style依赖。旧Task89aefcb92514 inputs_current=false，其旧PASS不用于新subjects。',
    '完整固定packet和新SVG已读；固定来源全文及p04相关Narrative/Plan的既有不可变内容可复用。未声称全稿新评或人类专业认可。',
    '物理尺寸/逐run字号本人直接从新PPTX XML重测；没有借Root机械PASS代替视觉判断。F05/F06仅对精确新artifact关闭，run02物理错误与run03字号失败原件不改写。',
    '所有测量明确区分1600×900逻辑/约120dpi实际渲染像素与1280×720物理96ppi编译像素；观察到native墨迹相对SVG约3px下移，不据此推定一般产品缺陷。',
    'Root实际followup与本次claim观察支持Host层来源；FINAL/completed完成观察将在实际发生后另存。identity_receipt=null，无平台/人类签名，未用preproduction sealed receipt selector。',
    '仅单页工程评阅；公平E2/E3、全八页交付、Owner、真实受众理解、PowerPoint桌面及整体RC3验收均未关闭。',
]
dimension_observations = {
    'blueprint_content': ['全部17原子在三图中逐句核对，仍待验证、许可/来源、采用/未采用及原因、未知原因/不能猜填、能补/不能补/取得条件再继续、启动前明确、无法确认/冲突/不适用/仍不确定、候选不可直接采用、继续未决/不等于已解决、AI不自动提交/修改/关闭、非诊断或批准等限定均保留。', '四节点与三条向右关系完整，unknown/unsuitable两行及trigger/action/handoff三列归属明确，无新自动提交分支；SVG/PPT原生拼接17/17与固定正文相等，notes亦相等。'],
    'blueprint_fidelity': ['原图白底深蓝文字、浅蓝节点和表头、四节点向右主链、异常表及底部边界的层级与关系保留。条件句来自冻结requirements，未从图像引入新事实。', '本轮SVGv2与实际PPT在全部信息、表格归属、行折和箭头关系上无观察到的损失；PPT60个原生shape/36个文字run、0picture/0media。F07垂直留白偏差单列，不能被保真PASS掩盖。', 'F05精确EMU与F06逐run尺寸仅在本地实际PPT文件范围完成核对，不宣称正式Document outputs已交付或全稿conversion通过。'],
    'readability': ['新增大字号后全部文字肉眼仍可辨读，没有看到裁字/覆盖/缺字。实际18pt正文、30pt标题全部达标，密度较高但顺序和责任交接仍可辨。', '严格检查后发现F07：实际PPT表头净空约9–10px，部分三行单元格约10–11px，低于固定12px。新SVG预览对应13–14px；不能仅用SVG或字号达标放行实际PPT阅读约束。', '外边距及模块间隔F02/F03当前仍符合要求；F07为本轮新增开放must_fix，故此维度FAIL。修复要求不得删正文、降18pt门槛或放宽12px阈值。'],
}
dim_findings = {'blueprint_content': [f01, a01], 'blueprint_fidelity': [f01, f04, f05, v01, a01, a02], 'readability': [f02, f03, f06, f07, a01]}
reviews = []
for kind in ['blueprint_content', 'blueprint_fidelity', 'readability']:
    review = {'schema_version': 'deck_review.v2', 'review_id': prior[kind]['review_id'], 'kind': kind, 'review_stage': 'page_visual', 'status': 'fail' if kind == 'readability' else 'pass', 'subjects': copy.deepcopy(subjects), 'dependencies': copy.deepcopy(deps), 'reviewer': {'type': 'independent_host', 'id': EXECUTION, 'execution_ref': EXECUTION, 'independence_confirmed': True, 'identity_receipt': None, 'evidence_ref': None, 'assurance': 'host_attested'}, 'observations': common + dimension_observations[kind], 'findings': copy.deepcopy(dim_findings[kind]), 'created_at': NOW, 'replaces': prior[kind]['review_ref']}
    validate_review_semantics(review)
    reviews.append(review)
save('raw-accept-payload.json', {'kind': 'review', 'reviews': reviews, 'notes': 'Actual native non-author p04 SVGv2 re-review. Content PASS; fidelity PASS; readability FAIL for open F07 contracted minimum cell clearance. F05/F06 closure new precise artifact only. Original records/failures retained; no full delivery/human/desktop/global acceptance.'})

pipeline = Path('/workspace/work/rc3/candidate-03-5dbdf72/prefix/.deck-master/releases/5dbdf72089d6-94f6f31fcadf/venv/lib/python3.12/site-packages/deck_master/pipeline.py')
correction = ROOT / 'root-physical-unit-instruction-correction.json'
save('physical-unit-attribution-evidence.json', {'root_correction_path': str(correction), 'root_correction_sha256': hashlib.sha256(correction.read_bytes()).hexdigest(), 'root_correction_content': json.loads(correction.read_text()), 'independent_installed_pipeline_path': str(pipeline), 'independent_installed_pipeline_sha256': hashlib.sha256(pipeline.read_bytes()).hexdigest(), 'actual_line_378': pipeline.read_text().splitlines()[377], 'attribution': 'Root initial pixel-only helper call and18pt=24px author instruction omitted actual0.8contain scale. Installed formal pipeline already passes slide_width_in*96/slide_height_in*96. This evidence does not establish a product source defect.'})
assessment = {'schema_version': 'rc3_actual_page_visual_assessment.v1', 'reviewed_at': NOW, 'task_id': '405175566aaf', 'operation_id': 'review-ce4a9a178d7f', 'produced_against': binding['task']['produced_against'], 'execution_ref': EXECUTION, 'page_id': 'p04', 'scope_verdict': 'FAIL page_visual readability: new open F07; content/fidelity PASS', 'dimension_results': {r['kind']: r['status'] for r in reviews}, 'reason': '新原生尺寸和逐run字号均修复，固定全部信息和关系保留；但实际PPT表头及三行单元格底部净空没有达到明确12px最低要求，因此不能因机械字号PASS或旧review而放行。', 'subjects': subjects, 'dependencies': deps, 'image_views': views, 'fixed_atom_checks': checks, 'qualifier_checks': dimension_observations['blueprint_content'], 'relationship_checks': [{'edge': edge, 'actual': '本轮实际三图中对应相邻节点单向向右，当前共同限定约束主链，未增造AI提交分支。'} for edge in fixed['visual_spec']['edges']], 'table_ownership': {'rows': ['unknown', 'unsuitable'], 'columns': ['trigger', 'action', 'handoff'], 'all_six_cells': '逐格全文可见且行列归属正确'}, 'reading_order': '标题/副标题→带共同条件的四节点主链→异常标题/表头→两行三列→范围/能力边界', 'findings': [f01, f02, f03, f04, f05, f06, f07, v01, a01, a02], 'F05_F06_closure': closures, 'F07_precise_measurement': f07_measure, 'open_findings': ['F07 must_fix', 'A01 advisory', 'A02 metadata advisory'], 'notes_equal_fixed_page': native['notes_text'] == fixed['speaker_notes'], 'limits': ['仅新精确p04产物；旧run02三PASS/F05HOLD和run03字号失败原件不回写。', '未进行真实人类/专业、Owner、受众理解、现场投影或PowerPoint桌面验收。', '公平E2/E3、全八页、全稿最终六维和整体RC3均未关闭。', '工作单ppt_preview与outputs仍为空；本地PPTX与渲染是明确hash绑定的补充工程实物，不伪装正式Document输出。', 'host_attested为实际非作者followup执行和Root观察，不等于严格平台/人类身份receipt；本轮FINAL/completed观察目前尚未发生。', '当前文字可辨读，FAIL针对明确12px工程下限，不夸大为语义遗漏或一般compiler bug。'], 'sdk_submission': 'prepared; actual response recorded separately'}
save('assessment.json', assessment)

paths = [PACKET / n for n in ['task.json', 'workorder.json', 'fixed-page.json', 'prepared-method-bytes.json', 'current-p04-entry.json']]
paths += [SVG, ROOT/'run-04-native-ppt-v2-correct-physical/native/deck.pptx', ROOT/'run-04-native-ppt-v2-correct-physical/actual-physical-canvas-and-typography.json', correction, pipeline, Path('/workspace/work/rc3/candidate-03-5dbdf72/manifest.json')]
paths += [Path(v['path']) for v in views]
paths += [PROJECT/ref['path'] for ref in subjects]
save('read-input-hashes.json', [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in paths])
old = Path('/workspace/work/rc3/reviews/rc3-03-actual-page-visual-review-run02')
save('old-run02-evidence-preservation.json', {'old_report_sha256': hashlib.sha256((old/'report.md').read_bytes()).hexdigest(), 'old_assessment_sha256': hashlib.sha256((old/'assessment.json').read_bytes()).hexdigest(), 'expected_old_report_sha256': '6ded55beb455d9bbb9fc1c8ed4748ea5d64b674bf878336e1e5e3e2f7cd32b2b', 'expected_old_assessment_sha256': 'edcf26c8a3ee62146aa72216c61bcba1b0fa071c41160b924fb08cc325b0b089', 'modified_by_this_run': False})
save('reading-and-failure-log.json', {'sdk_failures': [], 'generation_calls': 0, 'product_mutations': 0, 'image_inspection': 'three originals plus four exact diagnostic crop views', 'truncated_output': 'Combined workorder output truncated; missing repeated context spans re-read with sed. Fixed-page, prepared method, entry and actual SVG read fully. No whole-deck reading claimed.', 'crop_authorization': 'Root expressly requested exact coordinate/crop evidence; only own new evidence directory contains derived raw crops, originals untouched.'})
print(json.dumps({'verdict': assessment['scope_verdict'], 'review_statuses': assessment['dimension_results'], 'atom_checks': len(checks), 'all_atom_texts_match': all(c['svg_exact_equality'] and c['pptx_exact_equality'] for c in checks), 'F05': 'fixed new artifact only', 'F06': 'fixed new artifact only', 'F07': 'open must_fix'}, ensure_ascii=False, indent=2))
