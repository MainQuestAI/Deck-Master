import {post, readableError} from './api.js';
import {el, button} from './dom.js';

const strategies={model_designed:'模型自主编排',agreed_layout:'按约定构图'};
export function designBasis(result, app) {
  const node=el('section',{class:'stack design-basis','aria-label':'本轮制作依据'},el('h3',{},'本轮制作依据'));
  for(const row of result.production_basis||[]) {
    const d=row.resolved_design_context,policy=d.design_policy||{},requirements=d.content_requirements||{};
    if(app)node.append(el('div',{class:'row wrap'},...[['content','核对正文'],['prepared_prompt','查看提示词'],['original_image','比较原图候选'],['svg','查看 SVG 重建'],['ppt','查看 PPT 记录']].map(([layer,label])=>button(label,()=>app.go({surface:'page',page_id:row.page_id,layer,revision:result.plan.base_revision,candidate_id:null,task_id:null})))));
    node.append(el('p',{},`${row.page_id} · ${strategies[policy.strategy]||policy.strategy||'未记录策略'} · ${row.recipe_ref?'选定的固定规范':'本页当前设计依据'}`),
      el('p',{},'必须保留：页面事实、文字、关系方向和责任归属。'),
      el('p',{},'构图要求：'+(policy.layout_instruction||'未额外限定')),el('p',{},'自由范围：'+(policy.free_layout||'按当前固定规范执行')),
      el('p',{},'实际选定图像资产：'+((d.asset_inputs?.images||[]).map(a=>a.asset_id).join('、')||'无')),
      el('p',{},'参考图：'+row.references.length+' 张；历史规范和参考图不自动构成本轮全稿方向。'),
      el('details',{},el('summary',{},'查看固定文字、参数与适用依据'),el('pre',{class:'evidence-json'},JSON.stringify({page:row.page_ref,recipe:row.recipe_ref,requirements,parameters:d.recipe_parameters,policy,assets:d.asset_inputs},null,2))));
  }
  const decision=result.eligibility;
  node.append(el('p',{class:decision?.allowed?'muted':'field-error'},decision?.allowed?'当前范围可交接；提交时仍会重新核对授权与依据。':'当前不可交接：'+(decision?.reason_codes?.map(code=>readableError({code,message:'此项条件尚未满足，请核对本轮范围与授权。'})).join('；')||'尚未核实资格')),
    el('p',{class:'muted'},'原图候选 → 比较采用 → 原图表达审查 → SVG 重建 → 组装 PPT。已知问题原图可用于修复对照，审查通过前不能作为扩页依据。正式产物记录与外部文件的交付验收分别核对。'));
  return node;
}

export function initialDesign(app) {
  const pages=app.summary.pages.filter(p=>p.stages.blueprint.existence!=='recorded');
  if(!pages.length)return null;
  let plan=null,busy=false,disposed=false,loaded=false,serial=0;
  const target=el('select',{'aria-label':'无参考初始设计目标'},...pages.map(p=>el('option',{value:p.page_id},p.title||p.page_id)));
  const instruction=el('textarea',{'aria-label':'初始设计要求',rows:2,value:'依据当前正文与设计策略完成首张原图；保留文字、关系方向和责任归属。'});
  const output=el('div',{class:'stack'});
  const invalidate=()=>{serial++;plan=null;output.replaceChildren();controls();};
  const controls=()=>{preview.disabled=!loaded||busy||app.readonly;submit.disabled=!loaded||busy||app.readonly||!plan?.eligibility?.allowed;};
  const preview=button('预览无参考初始试作',async()=>{
    const token=++serial,revision=app.route.revision;plan=null;busy=true;controls();
    try{
      const result=await post('/api/design/initial-plan',{input:{page_id:target.value,base_revision:revision,instruction:instruction.value}});
      if(disposed||token!==serial)return;
      if(app.route.revision!==revision||result.plan.base_revision!==revision)throw new Error('项目已更新，请重新预览当前依据。');
      plan=result;output.replaceChildren(el('p',{},'仅此页，最多一次图像调用。先交接任务，不在浏览器调用模型；候选返回后再比较采用。'),designBasis(result,app));
    }catch(error){if(!disposed&&token===serial)output.replaceChildren(el('p',{class:'field-error'},readableError(error)));}
    finally{busy=false;if(!disposed)controls();}
  });
  const submit=button('保存并交接初始试作',async()=>{
    if(!plan?.eligibility?.allowed||busy)return;
    const chosen=plan;busy=true;controls();
    try{await app.business.submit(app.editor,'changes.commit',{plan_id:chosen.plan_id,base_revision:chosen.plan.base_revision},{plan_id:chosen.plan_id,plan:chosen.plan},result=>app.go({surface:'runs',revision:result.revision_id,task_id:result.task_ids[0],runs_area:'tasks'}));}
    catch(error){if(!disposed)output.append(el('p',{class:'field-error'},readableError(error)));}
    finally{busy=false;if(!disposed)controls();}
  },true,{disabled:true});
  const save=()=>{invalidate();const editor=app.editor;if(loaded&&!editor.readonly&&!editor.disposed){editor.draft.content.initial_design={page_id:target.value,instruction:instruction.value};editor.changed();}};
  target.addEventListener('change',save);instruction.addEventListener('input',save);
  const hydrate=async()=>{loaded=false;invalidate();const editor=app.editor;await editor.ready;if(disposed||editor!==app.editor)return;const saved=editor.draft.content.initial_design;if(saved&&pages.some(p=>p.page_id===saved.page_id)){target.value=saved.page_id;instruction.value=saved.instruction;}loaded=true;controls();};
  app.root.addEventListener('draft-editor-replaced',hydrate);hydrate();
  app.root.addEventListener('summary-refreshed',invalidate);
  app.disposables.push(()=>{disposed=true;serial++;app.root.removeEventListener('summary-refreshed',invalidate);app.root.removeEventListener('draft-editor-replaced',hydrate);});controls();
  return el('section',{class:'panel initial-design'},el('div',{class:'panel-body stack'},el('h2',{},'无参考初始设计'),el('p',{},'没有旧原图也可先试一页；读取该页当前正文和策略，不强制上传或套用模板。'),target,instruction,el('div',{class:'row wrap'},preview,submit),output));
}
