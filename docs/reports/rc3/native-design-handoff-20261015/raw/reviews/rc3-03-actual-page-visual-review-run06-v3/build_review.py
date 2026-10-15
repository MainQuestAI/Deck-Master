from pathlib import Path
import collections, copy, datetime, hashlib, json, xml.etree.ElementTree as ET
from PIL import Image
from deck_master.models import validate_review_semantics

OUT=Path('/workspace/work/rc3/reviews/rc3-03-actual-page-visual-review-run06-v3')
ROOT=Path('/workspace/work/rc3/native-image-pilot-03')
PACKET=ROOT/'run-06-page-visual-review-v3'
SVG=ROOT/'run-05-svg-cell-clearance-repair/p04-native-v3-spacing-adjusted.svg'
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
EXEC='/root/rc3_03_actual_page_visual_review'
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
binding=json.loads((OUT/'current-subjects-dependencies.json').read_text())
fixed=json.loads((PACKET/'fixed-page.json').read_text())
work=json.loads((PACKET/'workorder.json').read_text())
native=json.loads((OUT/'independent-native-inspection.json').read_text())
measure=json.loads((OUT/'F07-all-nine-cells-both-layers.json').read_text())
allink=json.loads((OUT/'F07-all-antialiased-ink-crosscheck.json').read_text())
views=json.loads((OUT/'actual-image-view-and-reuse-record.json').read_text())
subjects,deps,entry=binding['subjects'],binding['dependencies'],binding['entry']
visible=fixed['customer_visible'];atoms=[('atom:p04:title',visible['title']),('atom:p04:subtitle',visible['subtitle'])]
for l in visible['labels']:atoms.append((f"atom:p04:label:{l['id']}:text",l['text']))
for block in visible['body_blocks']:
    if block['type']=='paragraph':atoms.append((f"atom:p04:block:{block['id']}:text",block['text']))
    elif block['type']=='table':
        for col in block['columns']:atoms.append((f"atom:p04:column:{block['id']}:{col['id']}:label",col['label']))
        for row in block['rows']:
            for cell in row['cells']:atoms.append((f"atom:p04:cell:{block['id']}:{row['id']}:{cell['column_id']}:display_text",cell['display_text']))
for c in visible['callouts']:atoms.append((f"atom:p04:callout:{c['id']}:text",c['text']))
tree=ET.fromstring(SVG.read_bytes());ns={'s':'http://www.w3.org/2000/svg'}
svgtext={n.get('data-atom-id'):''.join(n.itertext()) for n in tree.findall('.//s:text',ns) if n.get('data-atom-id')}
ppttext=collections.defaultdict(str)
for r in native['runs']:
    if r['shape_name'].startswith('atom:'):ppttext[r['shape_name']]+=r['text']
checks=[{'atom_id':aid,'fixed_text':text,'svg_text':svgtext.get(aid),'ppt_text':ppttext.get(aid),'svg_exact':svgtext.get(aid)==text,'ppt_exact':ppttext.get(aid)==text,'visual':'本轮两个新图逐句可辨读，限定和行列归属正确；原始蓝图inspection仅按未变SHA复用。'} for aid,text in atoms]
assert len(checks)==17 and all(x['svg_exact'] and x['ppt_exact'] for x in checks)
assert native['notes_text']==fixed['speaker_notes'] and native['matches_physical_canvas'] and native['all_runs_meet_role_floor']
assert measure['overall_F07_pass'] and all(v['all_9_pass'] for v in allink['results'].values())
assert all(v['all_9_cell_line_ink_separate'] and v['outer_minimum']>=48 for v in allink['full_antialiased_line_separation'].values())
save('actual-17-atom-checks.json',checks)

module={}
for role,d in measure['results'].items():
    im=Image.open(d['path']).convert('RGB');px=im.load()
    def blue(c):return c[2]>240 and c[0]<220 and c[1]<245 and c[2]-c[0]>10
    bottom=max(y for y in range(731,736) if blue(px[100,y]));top=min(y for y in range(757,762) if blue(px[100,y]))
    module[role]={'table_bottom_painted_y':bottom,'boundary_top_painted_y':top,'clear_empty_pixels':top-bottom-1,'meets24':top-bottom-1>=24}
assert all(v['meets24'] for v in module.values())
save('targeted-module-gap-check.json',module)
E=[entry['blueprint'],entry['svg'],entry['svg_preview']]
def f(fid,kind,impact,elements,message,expected,actual,resolution,reason):return {'finding_id':fid,'kind':kind,'impact':impact,'page_id':'p04','element_refs':elements,'message':message,'expected':expected,'actual':actual,'evidence':copy.deepcopy(E),'resolution':resolution,'resolution_reason':reason}
f01=f('F01','design','must_fix',['main-chain','main-chain-frozen-qualification','collect-retrieve'],'本轮新图重新确认主链条件绑定保持修复。','冻结主链限定就近约束四节点。','已有限定“主链只适用于条件可核对情形。”仍在共同框内，未知恢复条件及引用人工核查/未决规则全文可见。','fixed','新SVG与实际PPT重新阅读，未凭旧PASS放行。')
f02=f('F02','design','must_fix',['main-chain-frame','table-border','boundary-background'],'当前新图外边距满足至少48px。','四周至少48px。','全部实际painted内容：SVG外边距左49/上51/右49/下49px；PPT左49/上56/右50/下49px。','fixed','直接从本轮原始PNG读取全部painted外界，原图及旧记录不改写。')
f03=f('F03','design','must_fix',['table-border','boundary-background'],'当前新图模块间距保持至少24px。','模块间隔至少24px。','SVG表底733、提示顶759，计描边净空24.75逻辑px；两层实际蓝线之间均至少24个空白像素。主链框至异常标题肉眼亦有明确间隔。','fixed','定向像素检查与整页实际阅读共同确认。')
f04=f('F04','artifact','needs_judgment',['original-blueprint','canvas'],'原始蓝图尺寸和来源差异继续保留。','原图1672×941与8057905来源不重标；重建1600×900。','原图SHA8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c未变，本轮复用已实际查看的inspection；新SVG1600×900、PPT导出1601×900。','accepted_variance','原图来源及字节不变；导出取整与目标物理尺寸区分记录。')
f05=f('F05','conversion','must_fix',['ppt/presentation.xml:p:sldSz'],'仅对本轮精确新PPT保持物理尺寸修复。','12192000×6858000EMU，13⅓×7.5in。',f"新PPTX SHA{native['pptx_sha256']}的cx/cy精确匹配；type仍screen4x3，保留A02。",'fixed','本人重新读取新PPTX XML；旧物理尺寸失败记录不回写。')
f06=f('F06','conversion','must_fix',['ppt/slides/slide1.xml:a:rPr@sz'],'仅对本轮精确新PPT保持逐run字号修复。','两个明确heading atom30pt，其余body18pt。','本轮36个run：明确title及exceptions-heading共2段30pt，其余34段18pt；不用字号或加粗反推角色。','fixed','新XML独立核验，旧14.4/24pt失败历史不改写。')
f07=f('F07','readability','must_fix',['exceptions-table','table-header-bottom','table-row-divider','atom:p04:cell:exceptions:unknown:action:display_text','atom:p04:cell:exceptions:unsuitable:handoff:display_text'],'仅对本轮新SVG/PPT关闭全部单元格painted净空问题。','三列表头与两行三列数据共9格，两层四边painted净空均≥12逻辑/约120dpi像素，行墨迹不重叠。','逐格四边实测：SVG最小12px，PPT最小13px；SVG表头底16px、三行数据底16px，PPT相应均13px。包括全部淡抗锯齿墨迹的B<255交叉检查同样通过。每格行墨迹band数与实际行数一致，无合并/重叠。','fixed',f"本轮精确SVG SHA{hashlib.sha256(SVG.read_bytes()).hexdigest()}、PPT SHA{native['pptx_sha256']}、render SHA{measure['results']['ppt']['sha256']}实测。保留v2正式FAIL和原始F07，不反写过去通过。")
v01=f('V01','design','needs_judgment',['main-chain','exceptions-table','boundary-module'],'当前重排保留视觉层级及业务关系。','按蓝图总体次序与固定稿信息重建，落实必要修复。','省去装饰编号、共同条件框、左对齐表头、两行边界沿用；本轮上移并重分配表格/主链留白，body30px、heading50px、表格leading33px。','accepted_variance','新两图逐句可辨读，信息、限定、行列和3个箭头关系无损失；不声称像素一致。')
a01=f('A01','observation','advisory',['review-submit','atom:p04:cell:exceptions:unsuitable:handoff:display_text'],'完整异常理解仍依赖下方表格。','不把找到资料理解成批准、诊断或故障解决。','固定稿以表格承载未知及引用异常，无显式返回连线；全文明确人工核查、未决和人员提交。','open','模型全页可理解判断不替代真实受众测试/试讲。')
a02=f('A02','artifact','advisory',['ppt/presentation.xml:p:sldSz@type'],'保留type标签与实际尺寸不同的metadata事实。','物理尺寸按实际cx/cy核对。','type仍为screen4x3，cx/cy为正确16:9，当前实际headless图无拉伸。','open','不扩写未运行PowerPoint桌面的行为影响。')
prior={x['kind']:x for x in work['prior_page_visual_findings']}
common=['实际native非作者模型执行新Task24962551ff10；本轮只实际view_image(original)两个新SVG/PPT图。原图inspection按未变SHA复用，引用先前reportSHA，不假称本轮重看。','固定17原子、全部限定、4节点/3向右关系、2×3表格归属和阅读顺序在两个新图独立回归；原生文本17/17及notes全文相等。无裁字、墨迹行重叠或关系损失。','针对已复现F07，测两层全部9格四边painted净空，并用全部淡抗锯齿墨迹交叉核对；SVG最小12px/PPT最小13px。单位为1600×900逻辑/约120dpi实际PNG，不混用1280×720物理96ppi编译像素。','新PPT直接XML核对物理EMU及按明确角色的每段18/30pt。F05/F06/F07只对精确新artifact关闭；旧405Task inputs_current=false，旧FAIL/PASS保留。','Root实际followup/claim观察支持host_attested非作者模型来源；identity_receipt=null，无平台或人类签名。FINAL/agent completed完成观察仅在真实发生后由Root另存。','仅p04单页工程评阅，不关闭真实人类/专业、Owner、受众、桌面、公平E2/E3、完整八页或整体RC3。']
dimobs={'blueprint_content':['全部固定限定保留：仍待验证、许可只读与来源、采用/未采用及原因、未知原因/不能猜填、能补/不能补/取得条件再继续、启动前明确、无法确认/冲突/不适用/不确定、候选不可直接采用、继续未决/资料不等于解决、AI不自动提交/修改/关闭、非诊断/批准。'], 'blueprint_fidelity':['沿用白底深蓝/浅蓝结构与主链→异常表→边界层级，3条向右关系及6个数据格归属无损失。新增条件句来自冻结requirements，未从图像补事实。'], 'readability':['当前文字密度仍高但可逐句辨读；两层所有9格四边达12px且行墨迹分离，外边距至少49px、表格到边界实测24px空白。新物理尺寸与实际逐run字号均符合固定要求。']}
df={'blueprint_content':[f01,a01],'blueprint_fidelity':[f01,f04,f05,v01,a01,a02],'readability':[f02,f03,f06,f07,a01]}
reviews=[]
for kind in ['blueprint_content','blueprint_fidelity','readability']:
    r={'schema_version':'deck_review.v2','review_id':prior[kind]['review_id'],'kind':kind,'review_stage':'page_visual','status':'pass','subjects':copy.deepcopy(subjects),'dependencies':copy.deepcopy(deps),'reviewer':{'type':'independent_host','id':EXEC,'execution_ref':EXEC,'independence_confirmed':True,'identity_receipt':None,'evidence_ref':None,'assurance':'host_attested'},'observations':common+dimobs[kind],'findings':copy.deepcopy(df[kind]),'created_at':NOW,'replaces':prior[kind]['review_ref']}
    validate_review_semantics(r);reviews.append(r)
save('raw-accept-payload.json',{'kind':'review','reviews':reviews,'notes':'Actual native non-author targeted v3 F07 re-review plus full p04 regression. All three page_visual dimensions PASS on exact new subjects. Prior failures preserved. No human/desktop/fair E2E3/whole eight-page/RC3 acceptance.'})
closure={'new_svg_sha256':hashlib.sha256(SVG.read_bytes()).hexdigest(),'new_pptx_sha256':native['pptx_sha256'],'new_render_sha256':measure['results']['ppt']['sha256'],'F05':f05,'F06':f06,'F07':f07,'prior_F07_failed_review_ref':prior['readability']['review_ref'],'scope':'new exact artifacts only; old FAIL immutable'}
save('F05-F06-F07-exact-new-artifact-closure.json',closure)
assessment={'schema_version':'rc3_actual_page_visual_assessment.v1','reviewed_at':NOW,'task_id':'24962551ff10','operation_id':'review-1dba08ceae5e','produced_against':binding['task']['produced_against'],'execution_ref':EXEC,'page_id':'p04','scope_verdict':'PASS: exact new p04 page_visual engineering only','dimension_results':{r['kind']:r['status'] for r in reviews},'subjects':subjects,'dependencies':deps,'image_inspection':views,'fixed_atom_checks':checks,'qualifier_check':dimobs['blueprint_content'],'relationships':fixed['visual_spec']['edges'],'table_ownership':'header trigger/action/handoff; two rows unknown/unsuitable; all six data cells correctly owned and fully visible','reading_order':'标题/副标题→共同条件与四节点左至右→异常标题及三列表头/两行数据→范围/能力边界','findings':[f01,f02,f03,f04,f05,f06,f07,v01,a01,a02],'F07_targeted_measurements':{'all_cells_file':'F07-all-nine-cells-both-layers.json','all_antialias_file':'F07-all-antialiased-ink-crosscheck.json','svg_minimum_px':12,'ppt_minimum_px':13,'all_cells_lines_separate':True},'physical_and_typography':{'pptx_sha256':native['pptx_sha256'],'actual_emu':native['actual_emu'],'all_36_runs_role_floor_pass':native['all_runs_meet_role_floor'],'native_shapes':native['native_shape_count'],'pictures':native['picture_count'],'notes_equal':native['notes_text']==fixed['speaker_notes']},'closure':closure,'limits':['Only exact new p04 engineering review. Prior v2 readabilityFAIL/F07 and earlier physical/font/leading failures preserved.','No human/professional/Owner/audience/projection/PowerPoint desktop validation; no fairE2/E3,whole8page orRC3global acceptance.','Actual originalPNG inspection reused with verified byte hash; only two new full images viewed this run.','ppt_preview/outputs in formal workorder remain empty; local PPTX/render are explicit supplementary physical artifacts, not claimed formal deck delivery.','Host-attested non-author execution is not sealed preproduction/platform/human receipt. This run FINAL/agent completed observation will be stored only after actual events.'],'sdk_submission':'prepared; actual response saved separately'}
save('assessment.json',assessment)
paths=[PACKET/n for n in ['task.json','workorder.json','fixed-page.json','prepared-method-bytes.json','current-p04-entry.json']]+[SVG,Path(native['pptx_path']),ROOT/'run-06-native-ppt-v3-correct-physical/actual-physical-canvas-and-typography.json']+[Path(x['path']) for x in views['new_actual_views']]+[Path(views['original_reused_inspection']['path'])]
save('read-input-hashes.json',[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in paths])
save('reuse-and-history-references.json',{'original_inspection':views['original_reused_inspection'],'prior_v2_failed_review':prior['readability']['review_ref'],'prior_v2_report_path':'/workspace/work/rc3/reviews/rc3-03-actual-page-visual-review-run04-v2/report.md','prior_v2_report_sha256':'46714b217ac23866f6a41a8b97113cd06bda2d27d3972f893756583acd0c1a9e','old405_inputs_current':binding['old405_inputs_current'],'old_records_modified':False,'method_and_frozen_context':'unchanged immutable identities; prior full relevant source/context readings reused, this run new task/constraints/full visible content+notes/actual SVG/new physical artifacts read and checked'})
print(json.dumps({'verdict':assessment['scope_verdict'],'three_statuses':assessment['dimension_results'],'F07_svg_min':12,'F07_ppt_min':13,'module_gaps':module,'atoms_equal':True,'notes_equal':True},ensure_ascii=False,indent=2))
