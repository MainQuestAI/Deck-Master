import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
SOURCE='5dbdf72089d6625449a23a52ef3e23859c597b4e'
TREE='1b69a05050c63d0a2fbc4aaac86350611ad9f504'
PLAN=Path('/workspace/work/rc3-planning/rc3-development-plan-20261014')
rows=[]
def row(id,requirement,code,entry,tests,evidence,engineering,actual,remaining):
 rows.append(dict(id=id,requirement=requirement,implementation=code,public_entry=entry,
  original_test_sources=tests,evidence=evidence,engineering_status=engineering,
  actual_evidence_status=actual,remaining=remaining))

row('RC3-03.1','完整content_requirements/content_basis投影；Page/Plan/recipe权威与fidelity诚实null',
 ['design_requirements.py:25,47,66,198,227','production.py:116,165,329','generation.py:58,170'],
 ['continue/task summary','styles propose/confirm/plan + changes commit','requests freeze'],
 ['test_rc3_design_requirements.py','test_rc3_design_workflows.py'],
 ['targeted-tests.xml','actual-chain-check.json','decision-audit-ref-result.json'],
 'FAIL_F9','ACTUAL_P04_PROJECTION_CONFIRMED',
 ['F9-A：合法替换design Decision后解析历史Ref阻断；F9-B：语义消费混入decision Ref壳。需新候选修复复审，不能记作04/05接手产品缺陷。'])
row('RC3-03.2','无旧blueprint初始设计；真实Page；零调用可行性和固定完整正文',
 ['design_recipe.py:183,337','styles.py:153,181,290,344','changes.py:138,166'],
 ['styles propose intent=initial_design|feasibility','styles confirm/plan','changes commit'],
 ['test_rc3_design_recipes.py','test_rc3_design_feasibility.py','test_rc3_design_workflows.py'],
 ['targeted-tests.xml','actual-chain-check.json'],
 'PASS_WITH_F9_CROSSCUT','ACTUAL_P04_NO_REFERENCE_IMAGE_CONFIRMED',
 ['P04 image执行身份为8057905，5db只读重建消费保留旧身份；本轮新候选实际入口影响分析后绑定。'])
row('RC3-03.3','风险驱动覆盖；1/2页候选不自动采用；维度接受、采用、扩范围分开',
 ['design_recipe.py:114,183','styles.py:290,344','changes.py:166','candidates.py','collaboration.py:468'],
 ['styles propose with page_profiles/sample_targets/uncovered_cases','styles plan selected page_ids/max_calls','candidates plan/adopt','collaboration decision record'],
 ['test_rc3_design_recipes.py','test_rc3_design_workflows.py','test_rc3_restyle_workflows.py','test_styles.py:108'],
 ['targeted-tests.xml','actual-chain-check.json'],
 'PASS_WITH_F9_CROSSCUT','ACTUAL_SINGLE_P04_CANDIDATE_ONLY_AT_SETTLEMENT',
 ['完整矩阵/机制/数据/架构风险覆盖与模型选择仍需实际证据；公平试验及最终验收由RC3-05汇总；维度version更新须先修F9。'])
row('RC3-03.4','Page→冻结prompt→原始PNG→SVG→PPTX→渲染；表格归属/箭头/单位/限定/阅读顺序/编辑性',
 ['production.py:173,260,329','pipeline.py:44,68,164,342','readback_relations.py:29','readback_text.py','compiler/native.py'],
 ['task start/requests freeze/task call begin/settle/task accept','reconstruct workorder','preview/compile/readback'],
 ['test_rc3_design_native.py','test_rc3_adopted_design_handoff.py'],
 ['actual-chain-check.json','actual-native-file-check.json','actual-native-edit-proof-copy.pptx','targeted-tests.xml'],
 'PASS_FOR_RETAINED_ACTUAL_PAGE','ACTUAL_P04_CHAIN_AND_NATIVE_FILES_CONFIRMED',
 ['Root正式page_visual review绑定仍待提交；不替代整个E3协议、整稿风险、人类桌面编辑。'])
row('RC3-03.5','同文字错归属/反箭头语义负例，同关系几何移动正例，无关Plan页不扩大失效',
 ['design_requirements.py:25,47,66','dependency_slices.py:142','visual_dependencies.py:30,58','pipeline.py:164','readback_relations.py:29'],
 ['editing + impact/freshness','requests freeze','task result acceptance','native readback'],
 ['test_rc3_design_requirements.py:232,251,290,307','test_rc3_preproduction_semantics.py','test_rc3_design_native.py:228,271,372','test_rc3_restyle_workflows.py:208'],
 ['targeted-tests.xml','independent-design-consumption.json','decision-audit-ref-result.json'],
 'PARTIAL_FAIL_F9_B','ACTUAL_CORRECT_P04_ONLY; SYNTHETIC_PAIRED_ENGINEERING',
 ['关系/布局工程正负例通过；Decision审计版本不变更语义仍污染消费比较，须修F9-B。实际模型成品负例/完整E3留RC3-05。'])
row('RC3-03.6','定位损失层后定向修复；不缩字/卡片化/虚构数量图；合理教学示意保留',
 ['production.py:329 prompt constraints','pipeline.py:164 located findings','service.py:1057 readback repair/no-progress','skills/deck-master/references/blueprint-svg.md','skills/deck-master/references/review-and-repair.md'],
 ['continue repair_readback/repair_no_progress','review/repair workorders'],
 ['test_rc3_design_native.py','test_production.py:49','test_rc3_adopted_design_handoff.py'],
 ['targeted-tests.xml','actual-chain-check.json','actual-native-file-check.json'],
 'PASS_FOR_OBSERVED_CONTROLS','P04_QUALIFIERS_RETAINED; NO_QUANTITY_CHART',
 ['真实错误模型产物的定向修复效果不能由prompt规则或合成负例代替；后续RC3-05保留失败原件/同预算记录。'])
row('RC3-03.7','固定正文E2与逐层E3；原始图片/失败保留；不借设计补写正文',
 ['原卡工作项7；ACCEPTANCE §4.1；RC3-05工作项3','production.py:329 preserves Page projection'],
 ['固定已审Page/Plan/recipe + 正式freeze/attempt/adopt','只读逐层比对'],
 ['test_rc3_design_native.py explicitly excludes E2/E3'],
 ['actual-chain-check.json','actual-native-file-check.json'],
 'NOT_A_CODE_ONLY_PASS','FORMAL_E2_NOT_RUN; E3_SINGLE_PAGE_ENGINEERING_SUBSET',
 ['RC3-05汇总正式公平E2/E3，本卡交付实际固定产物供复用。不得把本单页、synthetic或新旧执行安装混用称公平E2/E3完成。'])

row('AC-D01','Q4无旧图、P05一次授权真实样页；正文/布局理由/未覆盖页型/调用与停止状态',
 ['RC3-03.1–3 implementation'],['styles propose/confirm/plan + changes commit'],
 ['test_rc3_design_workflows.py','test_rc3_design_feasibility.py'],
 ['targeted-tests.xml','actual-chain-check.json'],'PARTIAL_FAIL_F9','ACTUAL_P04_ENGINEERING_VARIANT_ONLY',
 ['不得以P04工程例直接关闭原Q4/P05及专业效果AC；本轮RC3-05按原判据接收适用证据。'])
row('AC-D02','颜色接受仅对应维度；采用和整稿扩展独立；拒绝提案不自动复活',
 ['styles.py:290','candidates.py','collaboration.py:468','eligibility.py','collaboration_budget.py'],
 ['collaboration decision record','candidates plan/adopt','styles plan + explicit scope/grant'],
 ['test_styles.py:108','test_rc3_design_workflows.py:60','test_rc3_restyle_workflows.py:192,251,266'],
 ['targeted-tests.xml','decision-audit-ref-result.json'],'PARTIAL_FAIL_F9','ACTUAL_P04_NO_AUTO_ADOPTION_AT_SETTLEMENT',
 ['实际颜色-only/拒绝/后续显式扩展交互尚无本审计完整证据；合法决定更新先修F9。'])
row('AC-D03','已覆盖模板复用，新增密度/关系风险局部校准；信息和阅读顺序保留',
 ['design_recipe.py:114,183,337','styles.py:290','visual_dependencies.py:58','pipeline.py:164'],
 ['styles propose/plan scoped targets','reconstruct/page_visual workorders'],
 ['test_rc3_design_recipes.py','test_rc3_design_native.py','test_rc3_restyle_workflows.py','test_rc3_adopted_design_handoff.py'],
 ['targeted-tests.xml','actual-native-file-check.json','decision-audit-ref-result.json'],
 'PARTIAL_FAIL_F9','ACTUAL_P04_MIXED_MECHANISM_TABLE_ONLY',
 ['未覆盖页型的真实模型/成品效果及密度冲突选择留RC3-05；不能用字符回读关闭AC。'])
row('CQ-03/I04','CONTRACTS11.4.1完整投影、basis切片、fidelity无伪Narrative',
 ['design_requirements.py:227','production.py:116,165,329','generation.py:58,170'],
 ['continue generation_input/production_request','requests freeze'],
 ['test_rc3_design_requirements.py','test_rc3_design_workflows.py'],
 ['targeted-tests.xml','actual-chain-check.json','decision-audit-ref-result.json'],
 'PARTIAL_FAIL_F9','ACTUAL_FIXED_P04_PROMPT_IDENTICAL_TO_CALLBACK',
 ['修F9 currenthead选择/消费Ref壳；其余所检字段与实际原值一致。'])
row('CQ-04/I04','语义/布局区分，相关过期拒绝与无关页保留',
 ['design_requirements.py:25,47,66','dependency_slices.py:142','visual_dependencies.py:58','production.py:165'],
 ['editing/impact/task inputs current/requests freeze/result acceptance'],
 ['test_rc3_design_requirements.py','test_rc3_preproduction_semantics.py','test_rc3_native_visual_reuse.py','test_rc3_restyle_workflows.py'],
 ['targeted-tests.xml','independent-design-consumption.json','decision-audit-ref-result.json'],
 'PARTIAL_FAIL_F9_B','PAIRED_ENGINEERING_ONLY',
 ['F9-B已确认相同effective SHA的decision Ref壳污染消费等价；本审计不声称旧Task已stale（其identity快速通道仍current）。'])
row('CQ-05/I05','同全文错表格/反业务箭头负例被识别，移动同关系正例不过判；实际原图/成品/主要编辑性',
 ['pipeline.py:164','readback_relations.py:29','readback_text.py','compiler/native.py'],
 ['native compile/readback','review/repair'],
 ['test_rc3_design_native.py:187,228,271,372,390,416'],
 ['targeted-tests.xml','actual-native-file-check.json'],
 'PASS_FOR_NATIVE_ENGINEERING','ACTUAL_P04_POSITIVE_PLUS_SYNTHETIC_PAIRED_NEGATIVES',
 ['整体专业CQ仍不关闭；完整E3、实际model负例损失定位及人类桌面层由后续绑定。'])

row('GLOBAL-DESIGN-FONTS-ASSETS','全局版式/实际字体资产/fallback消费；只失效实际消费页',
 ['production.py:90,116,306,329','service.py:730','pipeline.py:44,68','editing.py:207'],
 ['create design','update_design','import_asset','continue workorder'],
 ['test_production.py:73,86','test_service_flow.py:781,812','test_rc3_restyle_workflows.py:208'],
 ['independent-design-consumption.json','targeted-tests.xml','actual-native-file-check.json'],
 'PASS_FOR_CHECKED_CONSUMERS','ACTUAL_P04_RESOLVED_NOTO_FONT_FILES_HASHED',
 ['不承诺模型逐像素使用字体；native文件实际字体/栅格已分开记录。'])
row('STYLE-RECIPE-PARAMETERS','七项执行参数唯一来源；planning prose不覆盖事实；page_rules/override可追踪',
 ['design_recipe.py:319,337','styles.py:369','production.py:116,329','generation.py:58'],
 ['styles propose/confirm/plan','requests freeze'],['test_rc3_design_recipes.py:99,211,227','test_rc3_restyle_workflows.py:135'],
 ['targeted-tests.xml','actual-chain-check.json'],'PASS_WITH_F9_CROSSCUT','ACTUAL_P04_TYPED_PARAMETERS_MATCH_PROMPT_AND_HANDOFF',
 ['后续候选修复不能更改旧recipe/Request；需保留同参数身份影响分析。'])
row('INITIAL-RESTYLE-REFERENCES','初始可无参考；restyle目标原图首位、独立原始JPEG/PNG随后；不可用preview偷换',
 ['design_recipe.py:183,381','changes.py:29,166','generation.py:58,170','native_image_evidence.py:85,187'],
 ['styles references import','styles propose intent=restyle','changes commit','requests freeze'],
 ['test_rc3_restyle_workflows.py:135','test_rc3_design_recipes.py:175,195'],
 ['targeted-tests.xml','actual-chain-check.json'],'PASS_FOR_PROTOCOL','ACTUAL_INITIAL_NO_REFS; RESTYLE_SYNTHETIC_CONTROLLER_ONLY',
 ['本审计无实际模型restyle调用，不把受控fixture附件验证冒称真实restyle效果。'])
row('ONE-TWO-CANDIDATES','首批1/2页准确数量；反序结果仍候选；无自动采纳和扩页',
 ['styles.py:290,344','changes.py:166','collaboration_budget.py','candidates.py'],
 ['styles plan page_ids/max_calls','changes commit','task accept','candidates adopt'],
 ['test_rc3_design_workflows.py:60','test_rc3_restyle_workflows.py:192'],
 ['targeted-tests.xml','actual-chain-check.json'],'PASS_FOR_PROTOCOL','ACTUAL_P04_SETTLEMENT_NO_AUTO_ADOPTION_EXPANSION',
 ['实际双模型结果顺序不在本审计原件范围；不能从一页推全范围。'])
row('G12-NATIVE-IMAGE-CHAIN','真实调用绑定固定prompt/参数/refs/Request/Attempt/allowance/installation，未知model/seed/fee不填',
 ['native_image_evidence.py:72,85,151,282','generation.py','tasks.py:1657,1799','observations.py'],
 ['task start/requests freeze/task call begin/settle/task accept'],
 ['test_rc3_native_image_bridge.py','test_rc3_native_visual_reuse.py'],
 ['actual-chain-check.json'],'PASS_FOR_RETAINED_EXECUTION_IDENTITY','ACTUAL_805_IMAGE_5DB_READER_DISTINCT_AND_CORRECT',
 ['原图1672x941而请求1600x900已据实保留；Host attestation不是平台签名/真实人类，不得重标调用为5db。'])
row('BUILD-INSTALL-METHODS','构建包/合同/Skill真实安装接口一致；下游方法读取不借cwd',
 ['setup.py','tools/build_hook.py','pyproject.toml','method_resources.py:58,82,101,149','cli.py:79,383'],
 ['python -I -B -m deck_master capabilities','methods --kind blueprint|reconstruct|review --read','methods --kind compose --phase design --read'],
 ['test_install.py','test_install_host_skill.py','test_rc3_adopted_design_handoff.py'],
 ['installation-interface.json','targeted-import-identity.json'],'PASS_FOR_ISOLATED_INSTALL','ACTUAL_LOCAL_INSTALLED_BYTES_AND_PUBLIC_CLI',
 ['RC3-04负责完整三入口/四Skill/导入迁移/只读恢复/最终安装集成；本审计未激活HOME、未重建wheel、未做04/05实现。'])

tests=ET.parse(OUT/'targeted-tests.xml').getroot()
cases=[{'class':case.get('classname'),'name':case.get('name'),'seconds':case.get('time')} for case in tests.iter('testcase')]
evidence_files=['installation-interface.json','targeted-tests.xml','targeted-tests-rerun.log','targeted-import-identity.json','independent-design-consumption.json','decision-audit-ref-result.json','decision-audit-ref-before.json','decision-audit-ref-after.json','actual-chain-check.json','actual-native-file-check.json','actual-native-edit-proof-copy.pptx']
sources=['docs/specs/deck-master-v1.0.0-rc3/task-cards/RC3-03.md','docs/specs/deck-master-v1.0.0-rc3/ACCEPTANCE.md','docs/specs/deck-master-content-collaboration-v1.2/CONTRACTS.md','docs/specs/deck-master-content-collaboration-v1.2/ACCEPTANCE.md','docs/specs/deck-master-content-collaboration-v1.2/TASKS.md']
coverage={'schema':'independent_rc3_scope_audit.v1','verdict':'REQUEST_CHANGES',
 'source_sha':SOURCE,'source_tree':TREE,'scope':'RC3-03 original-card independent engineering coverage audit; not overall RC3 ready',
 'snapshot':'/workspace/work/rc3/reviews/rc3-03-code-snapshot-5dbdf72',
 'installed_release_id':'5dbdf72089d6-94f6f31fcadf','external_image_calls_by_auditor':0,
 'active_real_project_writes_by_auditor':0,'original_card_ac_final_status':'NOT_CLOSED',
 'blocking_product_findings':[{'id':'F9-A','location':'production.py:149–158 + design_requirements.py:212–216',
  'trigger':'Public same-ID style/tradeoff Decision replacement using replaces=oldRef',
  'result':'Resolver collects historical ref as accepted after following the head, then rejects it as not current; new generation preparation blocked.',
  'repro':'probe_decision_audit_ref.py','evidence':'decision-audit-ref-result.json'},
 {'id':'F9-B','location':'production.py:165–169 + design_requirements.py:223,292–298',
  'trigger':'Same effective Decision semantic hash, new audit Ref; isolate with read-only head-only view',
  'result':'consumed_design differs because nested decision_ref survives in decision_slices; historical Ref shell enters semantic freshness.',
  'limitation':'This repro does not show old task staleness; the content_identity fast path still reports current.',
  'repro':'probe_decision_audit_ref.py','evidence':'decision-audit-ref-result.json'}],
 'source_documents':[{'path':str(PLAN/path),'sha256':hashlib.sha256((PLAN/path).read_bytes()).hexdigest()} for path in sources],
 'targeted_tests':{'passed':len(cases),'failures':0,'evidence_layer':'controlled engineering; no model/human inference','cases':cases},
 'rows':rows,
 'handoff_04':['完整三入口/四Skill/导入迁移/恢复只读/候选最终安装一致性；并非代修本次F9'],
 'handoff_05':['正式公平E2/E3，完整风险矩阵与actual model成品覆盖，最终适用AC/CQ台账及效果比较'],
 'explicit_human_later':['真实Owner/听众/计时/桌面PPT编辑及适用professional policy：NOT_RUN；用户明确延后软件与效果测试后'],
 'pending_root_binding':['正式actual p04 page_visual任务/非作者review原始完成与结果绑定；本审计不靠其他report推结论'],
 'evidence_manifest':[{'path':str(OUT/name),'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()} for name in evidence_files]}
(OUT/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'rows':len(rows),'tests':len(cases),'verdict':coverage['verdict']}))
