import {get, post, postBinary, digest, fileURL, readableError} from './api.js';
import {el, button, copyText} from './dom.js';
import {imageView} from './images.js';
import {openCandidate} from './trial-actions.js';
const names={palette:'配色',typography:'文字层级',composition:'构图',spacing:'间距',density:'密度',lines:'线条',icons:'图标'};

export function visualStyle(app){
  const root=el('section',{class:'visual-style stack','aria-label':'外部截图风格'}),status=el('p',{role:'status'}),images=el('div',{class:'visual-reference-list'}),rules=el('div',{class:'visual-rules stack'});
  const editor=app.editor,key=`deck-master:visual-style:${app.info.project_identity}`,uploadKey=key+':upload';
  let state={ids:[],targets:[],instruction:'分析配色与文字层级，保留目标页完整内容',task_id:null,recipe:null},pending=null,refs=[],spec=null,busy=false,disposed=false,leases=[],specLeases=[],analysisSerial=0,recipe=null,fonts=[],referencePage=0;
  try{state={...state,...JSON.parse(localStorage.getItem(key)||'{}')};pending=JSON.parse(localStorage.getItem(uploadKey)||'null');}catch{status.textContent='本机恢复记录无法读取，请核对已保存参考与任务。';}
  if(!Array.isArray(state.ids)||!Array.isArray(state.targets)||typeof state.instruction!=='string')state={ids:[],targets:[],instruction:'分析配色与文字层级，保留目标页完整内容',task_id:null,recipe:null};
  const persist=()=>localStorage.setItem(key,JSON.stringify(state));
  const input=el('input',{type:'file',accept:'image/png,image/jpeg,image/webp',multiple:true,'aria-label':'导入参考截图'});
  const requirement=el('textarea',{rows:2,maxLength:4000,'aria-label':'截图风格要求',value:state.instruction});
  requirement.addEventListener('input',()=>{state.instruction=requirement.value;invalidateAnalysis();persist();controls();});
  const target=el('select',{'aria-label':'截图风格试作目标'},el('option',{value:''},'先选一页试作'),app.summary.pages.map((p,i)=>el('option',{value:p.page_id},`第 ${i+1} 页 · ${p.title}`)));
  target.value=state.targets[0]||'';target.addEventListener('change',()=>{state.targets=[target.value,...state.targets.filter(id=>id!==target.value)].filter(Boolean);invalidatePlan();state.recipe=null;persist();showTarget();renderFutureTargets();controls();});
  const targetPreview=el('div',{class:'style-primary-target'});let targetLease;
  function showTarget(){targetLease?.dispose();targetPreview.replaceChildren();const page=app.summary.pages.find(p=>p.page_id===target.value);if(page?.stages.blueprint.file){targetLease=imageView(app,page.stages.blueprint,'试作目标原图');targetPreview.append(targetLease.node);}}
  const analyze=button('分析截图',()=>startAnalysis(),true),refresh=button('查看分析结果',()=>readAnalysis(true)),handoff=button('交给 Deck Master Agent',()=>copyText(state.handoff||`请接续 Deck Master 截图分析任务 ${state.task_id}，读取固定工作单后返回视觉规范。`));
  const confirm=button('检查并确认视觉规范',confirmSpec,true),trial=button('预览单页试作',()=>planTrial(false),true),dispatch=button('保存并交接试作',commitTrial,true);
  const planBox=el('div',{class:'stack'}),choices=new Map();let plan=null;
  const futureTargets=el('div',{class:'row wrap'}), expansionTargets=el('div',{class:'row wrap'}), candidateRows=el('div',{class:'stack'});
  const sample=el('select',{'aria-label':'已采用的截图风格样例'},el('option',{value:''},'先采用一页满意的试作'));
  const expansion=new Set(),expand=button('预览所选页扩展',()=>planTrial(true),true);
  sample.addEventListener('change',()=>{expansion.clear();invalidatePlan();renderExpansion();controls();});
  function invalidatePlan(){plan=null;planBox.replaceChildren();}
  function clearSpec(){spec=null;specLeases.splice(0).forEach(v=>v.dispose());rules.replaceChildren();choices.clear();}
  function invalidateAnalysis(){analysisSerial++;state.task_id=null;state.handoff=null;state.recipe=null;recipe=null;clearSpec();invalidatePlan();candidateRows.replaceChildren();sample.replaceChildren(el('option',{value:''},'先采用一页满意的试作'));}
  function renderFutureTargets(){futureTargets.replaceChildren(...app.summary.pages.filter(p=>p.page_id!==target.value).map((p,i)=>{
    const check=el('input',{type:'checkbox',checked:state.targets.includes(p.page_id),'aria-label':'允许后续风格扩展到 '+p.title,disabled:app.readonly});
    check.addEventListener('change',()=>{state.targets=check.checked?[...new Set([...state.targets,p.page_id])]:state.targets.filter(id=>id!==p.page_id);state.recipe=null;recipe=null;invalidatePlan();persist();controls();});
    return el('label',{class:'inline-control'},check,p.title);
  }));}
  function renderExpansion(){const adopted=sample.selectedOptions[0]?.dataset.page;
    expansionTargets.replaceChildren(...(recipe?.input.target_page_ids||[]).filter(id=>id!==adopted).map(id=>{const page=app.summary.pages.find(p=>p.page_id===id),check=el('input',{type:'checkbox',checked:expansion.has(id),'aria-label':'本次扩展到 '+page?.title});
      check.addEventListener('change',()=>{check.checked?expansion.add(id):expansion.delete(id);invalidatePlan();controls();});return el('label',{class:'inline-control'},check,page?.title||id);}));
  }
  async function loadRecipe(){if(!state.recipe)return;const chosen=state.recipe;
    try{const value=await get('/api/styles/'+chosen+'?'+new URLSearchParams({revision:app.route.revision}));if(disposed||state.recipe!==chosen)return;
      if(value.recipe.schema_version!=='style_recipe.v2')throw new Error('这不是截图风格规范。');recipe=value.recipe;
      const result=await get('/api/candidates?'+new URLSearchParams({revision:app.route.revision}));if(disposed||state.recipe!==chosen)return;
      const rows=result.candidates.filter(v=>v.style_recipe_ref?.sha256===value.ref.sha256&&recipe.input.target_page_ids.includes(v.candidate.page_id)&&v.candidate.stage==='blueprint');
      sample.replaceChildren(el('option',{value:''},'选择已采用的样例'),...rows.filter(v=>v.status==='adopted').map(v=>el('option',{value:v.candidate.candidate_id,'data-page':v.candidate.page_id},app.summary.pages.find(p=>p.page_id===v.candidate.page_id)?.title||v.candidate.page_id)));
      candidateRows.replaceChildren(el('p',{},'已确认视觉规范。先比较并采用单页试作，再明确勾选扩展页。'),...rows.slice(-30).map(v=>button('比较 '+(app.summary.pages.find(p=>p.page_id===v.candidate.page_id)?.title||v.candidate.page_id),()=>openCandidate(app,v.candidate,result.revision_id))));renderExpansion();
    }catch(error){if(!disposed)status.textContent=readableError(error);}finally{controls();}}

  const reference=el('div',{class:'stack'},el('label',{},'参考截图（1–5 张）',input),images);
  const targetBox=el('div',{class:'stack'},el('label',{},'试作目标',target),targetPreview);
  root.append(el('div',{class:'style-working-pair'},reference,targetBox),el('details',{},el('summary',{},'预先允许后续扩展的页面（默认不选）'),futureTargets),el('label',{class:'stack'},'想借用怎样的视觉风格',requirement),
    el('div',{class:'row wrap'},analyze,refresh,handoff),status,rules,el('div',{class:'row wrap'},confirm,trial),candidateRows,el('details',{},el('summary',{},'采用样例后扩展'),sample,expansionTargets,expand),planBox,dispatch);
  function controls(){const blocked=busy||app.readonly||disposed||Boolean(app.business.entries.size);
    input.disabled=blocked||Boolean(pending);requirement.disabled=blocked;target.disabled=blocked;
    analyze.disabled=blocked||!state.ids.length||state.ids.length>5||!requirement.value.trim();refresh.disabled=busy||!state.task_id;handoff.hidden=!state.task_id;
    confirm.disabled=blocked||!spec||Boolean(spec.conflicts.length)||!state.targets.length;trial.disabled=blocked||!state.recipe||!recipe;dispatch.disabled=blocked||!plan;expand.disabled=blocked||!recipe||!sample.value||!expansion.size;}
  function release(){leases.splice(0).forEach(view=>view.dispose());}
  async function loadReferences(){
    const value=await get('/api/styles/references?'+new URLSearchParams({revision:app.route.revision}));if(disposed)return;refs=value.references;fonts=value.fonts||[];
    state.ids=state.ids.filter(id=>refs.some(row=>row.reference.reference_id===id));renderReferences();
  }
  function renderReferences(){release();const pages=Math.max(1,Math.ceil(refs.length/12));referencePage=Math.min(referencePage,pages-1);
    const visible=new Set([...state.ids,...refs.slice(referencePage*12,referencePage*12+12).map(row=>row.reference.reference_id)]);
    images.replaceChildren(...refs.map((row,i)=>({row,i})).filter(({row})=>visible.has(row.reference.reference_id)).map(({row,i})=>{
    const check=el('input',{type:'checkbox',checked:state.ids.includes(row.reference.reference_id),'aria-label':`选用参考截图 ${i+1}`,disabled:app.readonly});
    check.addEventListener('change',()=>{if(check.checked&&state.ids.length>=5){check.checked=false;status.textContent='一次最多选择5张参考，请先取消一张。';return;}const id=row.reference.reference_id;state.ids=check.checked?[...state.ids,id]:state.ids.filter(x=>x!==id);invalidateAnalysis();persist();renderReferences();});
    const view=imageView(app,row.preview,`参考截图 ${i+1}`);leases.push(view);
    return el('label',{class:'visual-reference-choice'},view.node,el('span',{class:'inline-control'},check,`参考 ${i+1} · ${row.reference.width}×${row.reference.height}`));}));
    if(pages>1)images.append(el('div',{class:'row wrap'},button('上一组参考',()=>{referencePage--;renderReferences();},referencePage===0),el('span',{},`第 ${referencePage+1} / ${pages} 组 · 已选 ${state.ids.length} 张`),button('下一组参考',()=>{referencePage++;renderReferences();},referencePage===pages-1)));
    controls();}
  async function uploadFile(file,base){
    if(file.size>64*1024*1024)throw new Error('单张截图不能超过64 MiB。');
    const bytes=await file.arrayBuffer(),sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
    if(pending && pending.sha256!==sha)throw new Error('请先核实原上传，或重新选择同一张图片以重试。');
    if(!pending){pending={operation_id:crypto.randomUUID(),base_revision:base,sha256:sha};pending.request_digest=await digest({protocol:'changes.v1',kind:'styles.references.import',project_id:app.info.project_id,base_revision:base,payload:{sha256:sha}});localStorage.setItem(uploadKey,JSON.stringify(pending));}
    const value=await postBinary('/api/styles/references/import?'+new URLSearchParams({base_revision:pending.base_revision,operation_id:pending.operation_id}),file);
    if(value.status!=='committed'||!value.operation_result?.revision_id||value.operation_id!==pending.operation_id||value.request_digest!==pending.request_digest)throw new Error('上传回执身份不匹配，请保留原文件并核实。');
    pending=null;localStorage.removeItem(uploadKey);state.ids=[...state.ids,value.operation_result.reference_id].slice(-5);persist();return value.operation_result.revision_id;
  }
  async function verifyUpload(){
    if(!pending)return;
    try{const value=await get('/api/operations/'+pending.operation_id);if(value.status!=='committed'||!value.operation_result?.revision_id||value.operation_id!==pending.operation_id||value.request_digest!==pending.request_digest)throw new Error('上传回执身份不匹配。');
      pending=null;localStorage.removeItem(uploadKey);state.ids=[...state.ids,value.operation_result.reference_id].slice(-5);persist();app.go({revision:value.current_revision_id});
    }catch(error){status.textContent=error.status===404?'原上传尚未找到提交回执。请重新选择同一张截图，使用原编号重试。':readableError(error);input.disabled=false;}
  }
  input.addEventListener('change',async()=>{if(!input.files.length)return;if(input.files.length>5){status.textContent='一次最多导入5张截图。';return;}
    busy=true;controls();let base=app.route.revision;
    try{for(const file of input.files)base=await uploadFile(file,base);invalidateAnalysis();persist();if(!disposed)app.go({revision:base});}
    catch(error){status.textContent=readableError(error);if(error.status && error.status<500){pending=null;localStorage.removeItem(uploadKey);}else if(pending)status.append(button('核实原上传',verifyUpload));}
    finally{busy=false;controls();}});
  async function startAnalysis(ids=state.ids){
    busy=true;controls();
    try{await editor.ready;const request={reference_ids:ids,instruction:requirement.value,base_revision:app.route.revision};
      await app.business.submit(editor,'styles.analyze',request,{reference_ids:ids,instruction:requirement.value},result=>{
        state.ids=ids;state.task_id=result.task_id;state.recipe=null;spec=null;state.handoff=result.handoff;persist();app.go({revision:result.revision_id});});
    }catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}
  }
  async function readAnalysis(current=false){
    if(!state.task_id)return;const chosen=state.task_id,token=++analysisSerial;
    try{const value=await get('/api/tasks/'+chosen+(current?'':'?'+new URLSearchParams({revision:app.route.revision})));if(disposed||token!==analysisSerial||state.task_id!==chosen)return;if(current&&value.revision_id!==app.route.revision){app.go({revision:value.revision_id});return;}const task=value.task;
      if(task.status!=='completed'){clearSpec();status.textContent=task.status==='awaiting_host'?'分析要求已保存，等待 Agent 接手。':task.status==='running'?'Agent 已接手，等待分析结果。':`分析尚未完成：${task.status}。请核实或取消原任务。`;return;}
      if(task.kind!=='style_analyze'||task.result_refs.length!==1)throw new Error('分析结果类型不匹配。');
      const result=await get(fileURL(task.result_refs[0]));if(disposed||token!==analysisSerial||state.task_id!==chosen)return;spec={...result,ref:task.result_refs[0]};renderSpec();status.textContent='分析已返回，尚未确认或修改任何页。';
    }catch(error){status.textContent=readableError(error);}finally{controls();}
  }
  function renderSpec(){specLeases.splice(0).forEach(v=>v.dispose());rules.replaceChildren();choices.clear();const view=imageView(app,{file:spec.breakdown},'截图视觉规范拆解图');specLeases.push(view);
    rules.append(el('details',{},el('summary',{},'查看视觉拆解图'),view.node));
    for(const [key,value] of Object.entries(spec.dimensions)){const check=el('input',{type:'checkbox',checked:state.spec_edits?.ref===spec.ref.sha256 ? key in state.spec_edits.dimensions : ['palette','typography'].includes(key),'aria-label':'借用截图'+names[key]});const text=el('textarea',{rows:2,maxLength:4000,value:state.spec_edits?.ref===spec.ref.sha256 ? state.spec_edits.dimensions[key]??value.summary : value.summary,'aria-label':names[key]+'规范'});choices.set(key,{check,text});
      const detail=el('details',{},el('summary',{},'参考位置与不确定说明'),value.evidence.map(item=>el('p',{},`${item.certainty==='unknown'?'待核实':item.certainty==='approximate'?'近似判断':'已观察'}：${item.observation}`)));
      rules.append(el('div',{class:'visual-rule'},el('label',{class:'inline-control'},check,names[key]),text,detail));
      const saveRules=()=>{state.spec_edits={ref:spec.ref.sha256,dimensions:Object.fromEntries([...choices].filter(([,v])=>v.check.checked).map(([key,v])=>[key,v.text.value]))};state.recipe=null;recipe=null;invalidatePlan();persist();controls();};text.addEventListener('input',saveRules);check.addEventListener('change',saveRules);}
    if(spec.conflicts.length)rules.prepend(el('section',{class:'field-error'},el('h3',{},'参考风格存在冲突'),spec.conflicts.map(item=>el('p',{},item.description)),
      el('p',{},'选择其中一张重新分析，再确认单一规范。'),...state.ids.map((id,i)=>button(`以参考 ${i+1} 为准重新分析`,()=>startAnalysis([id])))));
    const font=el('select',{'aria-label':'确认使用的已注册字体'},el('option',{value:''},'沿用目标页已安装字体'),...fonts.map(f=>el('option',{value:f.font_id},f.family+' · '+f.face)));font.value=state.font_id||'';font.addEventListener('change',()=>{state.font_id=font.value;state.recipe=null;recipe=null;invalidatePlan();persist();controls();});rules.append(el('label',{},'字体选择',font));
    if(spec.font_suggestions.length)rules.append(el('p',{class:'muted'},'字体判断：'+spec.font_suggestions.map(f=>`${f.family}${f.approximate?'（近似）':''}：${f.reason}`).join('；')));
    if(spec.limitations.length)rules.append(el('p',{class:'muted'},spec.limitations.join('；')));
  }
  async function confirmSpec(){busy=true;controls();try{
    const input={schema_version:'style_input.v2',project_id:app.info.project_id,base_revision:app.route.revision,visual_style_ref:spec.ref,target_page_ids:state.targets,instruction:requirement.value,...(state.font_id?{font_id:state.font_id}:{}),
      dimensions:Object.fromEntries([...choices].filter(([,v])=>v.check.checked).map(([key,v])=>[key,v.text.value]))};
    const value=await post('/api/styles/propose',{input});
    await app.business.submit(editor,'styles.confirm',{proposal_id:value.proposal_id,base_revision:app.route.revision},{proposal_ref:value.proposal_ref},result=>{
      state.recipe=result.recipe_id;persist();app.go({revision:result.revision_id});});
  }catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}}
  async function planTrial(expanding=false){busy=true;controls();try{
    await app.business.available();const ids=expanding?[...expansion]:[target.value];
    if(!ids.length||!recipe)throw new Error('先确认规范并明确选择目标页。');
    const result=await post('/api/styles/plan',{input:{recipe_id:state.recipe,page_ids:ids,max_calls:ids.length,...(expanding?{adopted_candidate_id:sample.value}:{})}});
    if(disposed)return;if(result.plan.base_revision!==app.route.revision)throw new Error('项目已更新，请保留要求并返回当前版本重新预览。');
    plan=result;planBox.replaceChildren(el('p',{},`试作 ${ids.length} 页，最多 ${ids.length} 次生图；当前稿保留，返回后比较采用。`));
  }catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}}
  async function commitTrial(){if(!plan)return;busy=true;controls();try{const request={plan_id:plan.plan_id,base_revision:plan.plan.base_revision};await app.business.submit(editor,'changes.commit',request,{plan_id:plan.plan_id,plan:plan.plan},result=>{state.change_id=result.change_id;persist();app.go({surface:'runs',revision:result.revision_id,task_id:result.task_ids.length===1?result.task_ids[0]:null,candidate_id:null});});}catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}}
  if(pending){status.append(el('span',{},'存在待核实的截图上传。'),button('核实原上传',verifyUpload));}
  loadReferences().then(()=>{if(disposed)return;showTarget();renderFutureTargets();if(state.task_id)readAnalysis();loadRecipe();}).catch(error=>{if(!disposed)status.textContent=readableError(error);});
  app.disposables.push(()=>{disposed=true;analysisSerial++;release();specLeases.splice(0).forEach(v=>v.dispose());targetLease?.dispose();});controls();return root;
}
