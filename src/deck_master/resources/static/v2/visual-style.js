import {get, post, postBinary, digest, fileURL, readableError} from './api.js';
import {el, button, copyText} from './dom.js';
import {imageView} from './images.js';
import {stylePhases} from './style-phases.js';
import {candidateCards} from './candidate-cards.js';
const names={palette:'配色',typography:'文字层级',composition:'构图',spacing:'间距',density:'密度',lines:'线条',icons:'图标'};

export function visualStyle(app){
  const root=el('section',{class:'visual-style stack','aria-label':'外部截图风格'}),status=el('p',{role:'status'}),images=el('div',{class:'visual-reference-list'}),rules=el('div',{class:'visual-rules stack'});
  const editor=()=>app.editor,key=`deck-master:visual-style:${app.info.project_identity}`,uploadKey=key+':upload',continuationKey=key+':completed';
  let continuation=null,continuing=false,navigating=false;
  try{continuation=JSON.parse(localStorage.getItem(continuationKey)||'null');}catch{/* Old or damaged continuation never proves a commit. */}
  if(continuation&&(!continuation.revision||typeof continuation.route!=='object'||!Array.isArray(continuation.state?.ids)||!Array.isArray(continuation.state?.targets)||typeof continuation.state?.instruction!=='string'))continuation=null;
  let state={ids:[],targets:[],instruction:'分析配色与文字层级，保留目标页完整内容',task_id:null,recipe:null},pending=null,refs=[],spec=null,busy=false,disposed=false,leases=[],specLeases=[],analysisSerial=0,hydrateSerial=0,loaded=false,recipe=null,fonts=[],referencePage=0,savedTaskPage=0,savedCatalogSerial=0,savedTasks=[],specEditorOpen=false;
  try{state={...state,...JSON.parse(localStorage.getItem(key)||'{}')};
    // 复审 P3：恢复值按白名单定形——spec_edits.dimensions 不是对象时，borrowed/renderSpec 的 key-in 会崩掉整个规范阶段。
    if(!state.spec_edits||typeof state.spec_edits!=='object'||Array.isArray(state.spec_edits))state.spec_edits={};
    else for(const key of Object.keys(state.spec_edits.dimensions||{}))if(!state.spec_edits.dimensions[key]||typeof state.spec_edits.dimensions[key]!=='string')delete state.spec_edits.dimensions[key];
    if(!Array.isArray(state.ids))state.ids=[];
    if(!Array.isArray(state.targets))state.targets=[];
    pending=JSON.parse(localStorage.getItem(uploadKey)||'null');}catch{status.textContent='本机恢复记录无法读取，请核对已保存参考与任务。';}
  if(!Array.isArray(state.ids)||!Array.isArray(state.targets)||typeof state.instruction!=='string')state={ids:[],targets:[],instruction:'分析配色与文字层级，保留目标页完整内容',task_id:null,recipe:null};
  function persist(){
    try{localStorage.setItem(key,JSON.stringify(state));}catch{status.textContent='本机缓冲未保存，请先保存项目草稿或下载恢复文件。';}
    const current=editor();
    if(loaded&&!disposed&&current&&!current.disposed&&!current.readonly){current.draft.content.visual_style=structuredClone(state);current.changed();}
  }
  async function saveState(){
    const current=editor();await current.ready;
    if(disposed||current!==editor()||current.disposed)throw new Error('工作区已切换，已保存业务结果保留，请从项目恢复入口继续。');
    persist();await current.pendingWrite;await current.save();
    if(current.status==='dirty')await current.save();
    return current.status==='saved';
  }
  function rememberCompletion(revision, route={}, label='业务结果已保存', receipt=null){
    const receipts=[...(continuation?.receipts||[])];if(receipt&&!receipts.some(item=>item.operation_id===receipt.operation_id))receipts.push(receipt);
    continuation={revision,route:{revision,...route},state:structuredClone(state),label,receipts:receipts.slice(-20)};
    localStorage.setItem(continuationKey,JSON.stringify(continuation));
  }
  async function continueCompletion({preserveLocal=false}={}){
    if(!continuation||continuing||disposed||navigating)return;
    continuing=true;const original=continuation;
    try{
      state=structuredClone(original.state);
      if(!await saveState()){
        status.textContent=original.label+'；私人草稿仍待保存或核实，结果保留，不需要重新提交。';
        if(!preserveLocal||!editor().archiveLocal())return;
      }
      if(!disposed&&continuation===original){navigating=true;app.go(original.route);}
    }catch(error){if(!disposed)status.textContent=original.label+'；'+readableError(error);}
    finally{continuing=false;if(!disposed)controls();}
  }
  async function completedBusiness(result,route={},label='业务结果已保存'){
    rememberCompletion(result.revision_id,route,label);await continueCompletion();
  }
  function draftReady(){
    if(loaded&&!busy&&!disposed&&continuation&&editor().status==='saved'&&app.route.revision!==continuation.revision)continueCompletion();
  }
  const input=el('input',{type:'file',accept:'image/png,image/jpeg,image/webp',multiple:true,'aria-label':'导入参考截图'});
  const uploadRecovery=el('div',{class:'stack visual-upload-recovery','aria-live':'polite'});
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
  const cards=candidateCards(app);app.disposables.push(()=>cards.dispose());
  const sample=el('select',{'aria-label':'已采用的截图风格样例'},el('option',{value:''},'先采用一页满意的试作'));
  const expansion=new Set(),expand=button('预览所选页扩展',()=>planTrial(true),true);
  sample.addEventListener('change',()=>{expansion.clear();invalidatePlan();renderExpansion();controls();});
  function invalidatePlan(){plan=null;planBox.replaceChildren();}
  function clearSpec(){spec=null;specLeases.splice(0).forEach(v=>v.dispose());rules.replaceChildren();choices.clear();}
  function invalidateAnalysis(){analysisSerial++;state.task_id=null;state.handoff=null;state.recipe=null;recipe=null;clearSpec();invalidatePlan();cards.reset();candidateRows.replaceChildren();sample.replaceChildren(el('option',{value:''},'先采用一页满意的试作'));}
  function renderFutureTargets(){futureTargets.replaceChildren(...app.summary.pages.filter(p=>p.page_id!==target.value).map((p,i)=>{
    const check=el('input',{type:'checkbox',checked:state.targets.includes(p.page_id),'aria-label':'允许后续风格扩展到 '+p.title,disabled:app.readonly});
    check.addEventListener('change',()=>{state.targets=check.checked?[...new Set([...state.targets,p.page_id])]:state.targets.filter(id=>id!==p.page_id);state.recipe=null;recipe=null;invalidatePlan();persist();controls();});
    return el('label',{class:'inline-control'},check,p.title);
  }));}
  function renderExpansion(){const adopted=sample.selectedOptions[0]?.dataset.page;
    expansionTargets.replaceChildren(...(recipe?.input.target_page_ids||[]).filter(id=>id!==adopted).map(id=>{const page=app.summary.pages.find(p=>p.page_id===id),check=el('input',{type:'checkbox',checked:expansion.has(id),'aria-label':'本次扩展到 '+page?.title});
      check.addEventListener('change',()=>{check.checked?expansion.add(id):expansion.delete(id);invalidatePlan();controls();});return el('label',{class:'inline-control'},check,page?.title||id);}));
  }
  async function loadRecipe(){if(!state.recipe)return;const chosen=state.recipe,epoch=analysisSerial,hydration=hydrateSerial;
    try{const value=await get('/api/styles/'+encodeURIComponent(chosen)+'?'+new URLSearchParams({revision:app.route.revision}));if(disposed||state.recipe!==chosen||epoch!==analysisSerial||hydration!==hydrateSerial)return;
      if(value.recipe.schema_version!=='style_recipe.v2')throw new Error('这不是截图风格规范。');recipe=value.recipe;
      if(!spec){const result=await get(fileURL(recipe.input.visual_style_ref));if(disposed||state.recipe!==chosen||epoch!==analysisSerial||hydration!==hydrateSerial)return;spec={...result,ref:recipe.input.visual_style_ref};renderSpec();}
      const result=await get('/api/candidates?'+new URLSearchParams({revision:app.route.revision}));if(disposed||state.recipe!==chosen||epoch!==analysisSerial||hydration!==hydrateSerial)return;
      const rows=result.candidates.filter(v=>v.style_recipe_ref?.sha256===value.ref.sha256&&recipe.input.target_page_ids.includes(v.candidate.page_id)&&v.candidate.stage==='blueprint');
      sample.replaceChildren(el('option',{value:''},'选择已采用的样例'),...rows.filter(v=>v.status==='adopted').map(v=>el('option',{value:v.candidate.candidate_id,'data-page':v.candidate.page_id},app.summary.pages.find(p=>p.page_id===v.candidate.page_id)?.title||v.candidate.page_id)));
      openPhase(2,{auto:true});
      candidateRows.replaceChildren(el('p',{},'已确认视觉规范。先比较并采用单页试作，再明确勾选扩展页。'),...cards.render(rows.slice(-30),result.revision_id,{namedComparison:true}),button('到任务页查看全部候选',()=>app.go({surface:'runs',revision:result.revision_id,task_id:null,runs_area:'decisions'})));renderExpansion();
    }catch(error){if(!disposed)status.textContent=readableError(error);}finally{controls();}}

  const savedAnalysis=el('select',{'aria-label':'恢复已保存的截图分析'},el('option',{value:''},'选择已保存分析，不自动切换'));
  const savedRecipe=el('select',{'aria-label':'恢复已确认的截图规范'},el('option',{value:''},'选择已确认规范，不自动切换'));
  const savedPager=el('div',{class:'row wrap'});
  let savedLoading=false;
  async function loadSaved(requestedPage=savedTaskPage){if(savedLoading)return;savedLoading=true;const token=++savedCatalogSerial;
    savedPager.querySelectorAll('button').forEach(node=>node.disabled=true);
    try{const q=new URLSearchParams({revision:app.route.revision,limit:30,offset:requestedPage*30});
      const [taskPage,versions]=await Promise.all([get('/api/tasks?'+q),get('/api/styles?'+new URLSearchParams({revision:app.route.revision}))]);
      if(disposed||token!==savedCatalogSerial)return;savedTaskPage=requestedPage;savedTasks=taskPage.tasks.filter(t=>t.kind==='style_analyze');
      savedAnalysis.replaceChildren(el('option',{value:''},'选择已保存分析，不自动切换'),...savedTasks.map(t=>el('option',{value:t.task_id},`${t.instruction.slice(0,45)} · ${t.status==='completed'?'已返回':t.status==='awaiting_host'?'待接手':t.status==='running'?'处理中':'已停止'} · ${t.task_id.slice(-6)}`)));
      savedRecipe.replaceChildren(el('option',{value:''},'选择已确认规范，不自动切换'),...versions.recipes.filter(v=>v.recipe.schema_version==='style_recipe.v2').map(v=>el('option',{value:v.recipe.recipe_id},`V${v.recipe.version} · ${v.recipe.input.instruction.slice(0,45)} · ${v.recipe.input.target_page_ids?.length||0} 页 · ${v.recipe.recipe_id.slice(-6)}`)));
      savedPager.replaceChildren(button('上一组保存任务',()=>loadSaved(Math.max(0,savedTaskPage-1)),false,{disabled:savedTaskPage===0,'data-boundary':String(savedTaskPage===0)}),el('span',{},`第 ${savedTaskPage+1} 组任务`),button('下一组保存任务',()=>loadSaved(savedTaskPage+1),false,{disabled:taskPage.pagination.next_offset===null,'data-boundary':String(taskPage.pagination.next_offset===null)}));
      if(status.querySelector('button'))status.textContent=`已读取第 ${savedTaskPage+1} 组任务。`;
      controls();
    }catch(error){if(!disposed)status.replaceChildren(el('span',{},readableError(error)+' 已显示的任务与组号保持不变。'),button('重试读取这组任务',()=>loadSaved(requestedPage)));}
    finally{savedLoading=false;savedPager.querySelectorAll('button').forEach(node=>node.disabled=node.dataset.boundary==='true');}
  }
  savedAnalysis.addEventListener('change',async()=>{const chosen=savedAnalysis.value,task=savedTasks.find(t=>t.task_id===chosen);if(!task)return;
    invalidateAnalysis();openPhase(2);state.task_id=chosen;state.instruction=task.instruction;requirement.value=task.instruction;persist();await readAnalysis();});
  savedRecipe.addEventListener('change',async()=>{if(!savedRecipe.value)return;const chosen=savedRecipe.value,token=++analysisSerial;
    openPhase(2);
    busy=true;controls();try{const value=await get('/api/styles/'+encodeURIComponent(chosen)+'?'+new URLSearchParams({revision:app.route.revision}));
      if(disposed||token!==analysisSerial)return;const r=value.recipe;if(r.schema_version!=='style_recipe.v2')throw new Error('这不是截图视觉规范。');
      const result=await get(fileURL(r.input.visual_style_ref));if(disposed||token!==analysisSerial)return;
      clearSpec();invalidatePlan();state={...state,ids:r.reference_sources.references.map(v=>v.reference_id),targets:[...r.input.target_page_ids],instruction:r.input.instruction,recipe:chosen,task_id:null,font_id:r.input.font_id||'',spec_edits:{ref:r.input.visual_style_ref.sha256,dimensions:structuredClone(r.dimensions)}};
      spec={...result,ref:r.input.visual_style_ref};requirement.value=state.instruction;target.value=state.targets[0]||'';renderReferences();showTarget();renderFutureTargets();renderSpec();persist();await loadRecipe();
      status.textContent='已打开所选确认规范。请核对目标和固定依据后预览，当前稿保留。';
    }catch(error){if(!disposed)status.textContent=readableError(error);}finally{busy=false;controls();}});
  const reference=el('div',{class:'stack'},el('label',{},'参考截图（1–5 张）',input),images);
  const targetBox=el('div',{class:'stack'},el('label',{},'试作目标',target),targetPreview);
  // F07/§4.3/D2：截图路线由平铺改为四阶段，与项目路线共用阶段语义。
  const phase1=el('details',{class:'style-phase'},el('summary',{},'1 · 参考与目标'),
    el('div',{class:'style-working-pair'},reference,targetBox),
    el('label',{class:'stack'},'想借用怎样的视觉风格',requirement),
    el('details',{},el('summary',{},'预先允许后续扩展的页面（默认不选）'),futureTargets),
    el('div',{class:'row wrap'},analyze,handoff));
  const phase2=el('details',{class:'style-phase'},el('summary',{},'2 · 确认规范'),
    el('div',{class:'row wrap'},refresh),rules,el('div',{class:'row wrap'},confirm));
  // §2.2（深度复审）：试作动作属于阶段 3；扩展动作属于阶段 4。两路线共用同一
  // 规则——动作随所在阶段出现，交接随有效计划出现，计划结果与错误常驻阶段之外。
  const phase3=el('details',{class:'style-phase'},el('summary',{},'3 · 试作与采用'),
    candidateRows, el('div',{class:'row wrap'},trial));
  const phase4=el('details',{class:'style-phase'},el('summary',{},'4 · 扩展'),
    sample,expansionTargets,el('div',{class:'row wrap'},expand));
  const phaseNodes=[phase1,phase2,phase3,phase4];
  // 自动推进（分析返回、恢复完成）只在用户尚未主动选择阶段时生效——
  // 否则慢恢复会在用户已经打开"试作与采用"后把阶段抢回"确认规范"。
  const phaseReading=stylePhases(phaseNodes);
  const openPhase=(next,options)=>phaseReading.show(next,options);
  root.append(el('details',{},el('summary',{},'恢复项目中的截图分析与规范'),el('label',{class:'stack'},'已保存分析任务',savedAnalysis),savedPager,el('label',{class:'stack'},'已确认视觉规范',savedRecipe)),
    phase1,uploadRecovery,status,phase2,phase3,phase4,
    // 计划结果与错误出口常驻阶段之外（阶段切换不顺带隐藏失败原因）；
    // 交接动作只在有当前有效计划时出现。
    el('div',{class:'visual-plan stack'},planBox,dispatch));
  // 状态行在各阶段之外，任何阶段的提示都可见。
  openPhase(1);
  function controls(){const blocked=!loaded||busy||app.readonly||disposed||Boolean(app.business.entries.size);
    input.disabled=blocked||Boolean(pending&&pending.state!=='not_found');savedAnalysis.disabled=blocked;savedRecipe.disabled=blocked;requirement.disabled=blocked;target.disabled=blocked;
    uploadRecovery.replaceChildren();
    if(continuation)uploadRecovery.append(el('p',{},continuation.label+'；结果已保留。'),button('打开已保存的结果',()=>continueCompletion({preserveLocal:true}),false,{disabled:busy||continuing||!loaded}));
    if(pending?.state==='rejected')uploadRecovery.append(el('p',{},pending.rejection?.code==='visual_reference_conflict'?'本次上传因版本变化已明确拒绝，未提交。先读取当前版本，再重新选择截图上传。':'本次截图上传已明确拒绝，未提交。请结束这次失败上传后重新选择合法截图。'),button(pending.rejection?.code==='visual_reference_conflict'?'读取当前版本并重新上传':'结束失败上传，重新选图',restartRejectedUpload,false,{disabled:!loaded||busy||disposed||Boolean(app.business.entries.size)}));
    else if(pending)uploadRecovery.append(el('p',{},pending.state==='not_found'?'原上传尚未找到提交回执。请重新选择同一张截图，使用原编号重试。':'存在待核实的截图上传。原文件和请求编号保留。'),button('核实原上传',verifyUpload,false,{disabled:blocked}));
    analyze.disabled=blocked||!state.ids.length||state.ids.length>5||!requirement.value.trim();refresh.disabled=!loaded||busy||!state.task_id;handoff.hidden=!state.task_id;
    confirm.disabled=blocked||!spec||Boolean(spec.conflicts.length)||!state.targets.length;trial.disabled=blocked||!state.recipe||!recipe;
    // 交接动作按真实状态出现：没有当前计划时不出现，也不隐藏计划错误。
    dispatch.hidden=!plan;dispatch.disabled=blocked||!plan;expand.disabled=blocked||!recipe||!sample.value||!expansion.size;}
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
    // The references API returns a complete preview Artifact, including .file.
    const view=imageView(app,row.preview,`参考截图 ${i+1}`);leases.push(view);
    return el('label',{class:'visual-reference-choice'},view.node,el('span',{class:'inline-control'},check,`参考 ${i+1} · ${row.reference.width}×${row.reference.height}`));}));
    if(pages>1)images.append(el('div',{class:'row wrap'},button('上一组参考',()=>{referencePage--;renderReferences();},false,{disabled:referencePage===0}),el('span',{},`第 ${referencePage+1} / ${pages} 组 · 已选 ${state.ids.length} 张`),button('下一组参考',()=>{referencePage++;renderReferences();},false,{disabled:referencePage===pages-1})));
    controls();}
  async function uploadFile(file,base){
    if(file.size>64*1024*1024)throw new Error('单张截图不能超过64 MiB。');
    const bytes=await file.arrayBuffer(),sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
    if(pending && pending.sha256!==sha)throw new Error('请先核实原上传，或重新选择同一张图片以重试。');
    if(!pending){pending={operation_id:crypto.randomUUID(),base_revision:base,sha256:sha};pending.request_digest=await digest({protocol:'changes.v1',kind:'styles.references.import',project_id:app.info.project_id,base_revision:base,payload:{sha256:sha}});}
    pending.state='unknown';localStorage.setItem(uploadKey,JSON.stringify(pending));
    const original=pending;let value;
    try{value=await postBinary('/api/styles/references/import?'+new URLSearchParams({base_revision:original.base_revision,operation_id:original.operation_id}),file);}
    catch(error){
      // Only this endpoint's explicit pre-commit validation/CAS failures end
      // an attempt. Generic 4xx, 5xx, unreadable or mismatched receipts do not.
      const details=error.details;
      if(pending===original&&details?.operation_state==='not_committed'&&(!details.operation_id||details.operation_id===original.operation_id)&&
          (error.status===422&&error.code==='visual_reference_invalid'||error.status===409&&error.code==='visual_reference_conflict'&&error.field==='base_revision')){
        pending.state='rejected';pending.rejection={code:error.code,field:error.field};localStorage.setItem(uploadKey,JSON.stringify(pending));
      }
      throw error;
    }
    if(value.status!=='committed'||!value.operation_result?.revision_id||value.operation_id!==pending.operation_id||value.request_digest!==pending.request_digest)throw new Error('上传回执身份不匹配，请保留原文件并核实。');
    state.ids=[...new Set([...state.ids,value.operation_result.reference_id])].slice(-5);rememberCompletion(value.operation_result.revision_id,{},'截图已上传',{operation_id:value.operation_id,request_digest:value.request_digest,...value.operation_result});pending=null;localStorage.removeItem(uploadKey);persist();return value.operation_result.revision_id;
  }
  async function restartRejectedUpload(){
    if(!pending||pending.state!=='rejected'||busy)return;const original=pending;let focusUpload=false;busy=true;controls();
    try{
      let current=null;
      if(original.rejection?.code==='visual_reference_conflict'){
        current=await get(app.summaryURL());
        if(current.project_id!==app.info.project_id||!current.revision_id)throw new Error('当前项目版本无法核对，原失败请求仍保留。');
      }
      if(disposed||pending!==original)return;
      // User explicitly starts a new attempt; never rebase or replay the old UUID.
      localStorage.removeItem(uploadKey);pending=null;
      if(current&&current.revision_id!==app.route.revision)app.go({revision:current.revision_id});
      else{status.textContent='失败上传已结束。请重新选择截图，新上传使用新的请求编号。';focusUpload=true;}
    }catch(error){if(!disposed)status.textContent=readableError(error);}
    finally{busy=false;if(!disposed){controls();if(focusUpload)input.focus();}}
  }
  async function verifyUpload(){
    if(!pending||busy)return;busy=true;controls();
    try{const value=await get('/api/operations/'+pending.operation_id);if(value.status!=='committed'||!value.operation_result?.revision_id||value.operation_id!==pending.operation_id||value.request_digest!==pending.request_digest)throw new Error('上传回执身份不匹配。');
      state.ids=[...new Set([...state.ids,value.operation_result.reference_id])].slice(-5);rememberCompletion(value.operation_result.revision_id,{},'截图已上传',{operation_id:value.operation_id,request_digest:value.request_digest,...value.operation_result});pending=null;localStorage.removeItem(uploadKey);await continueCompletion();
    }catch(error){if(pending){pending.state=error.status===404&&error.code==='operation_not_found'?'not_found':'unknown';localStorage.setItem(uploadKey,JSON.stringify(pending));}status.textContent=readableError(error);}
    finally{busy=false;if(!disposed)controls();}
  }
  input.addEventListener('change',async()=>{const files=[...input.files];input.value='';if(!files.length)return;if(files.length>5||pending&&files.length!==1){status.textContent=pending?'请只选择原上传的同一张截图。':'一次最多导入5张截图。';return;}
    busy=true;controls();let base=app.route.revision;
    try{for(const file of files)base=await uploadFile(file,base);invalidateAnalysis();rememberCompletion(base,{},'截图已上传');await continueCompletion();}
    catch(error){status.textContent=readableError(error);if(continuation){invalidateAnalysis();rememberCompletion(continuation.revision,{},'部分截图已上传');await continueCompletion();}}
    finally{busy=false;controls();}});
  async function startAnalysis(ids=state.ids){
    busy=true;controls();
    try{await editor().ready;const request={reference_ids:ids,instruction:requirement.value,base_revision:app.route.revision};
      await app.business.submit(editor(),'styles.analyze',request,{reference_ids:ids,instruction:requirement.value},async result=>{
        state.ids=ids;state.task_id=result.task_id;state.recipe=null;spec=null;state.handoff=result.handoff;await completedBusiness(result,{},'截图分析要求已保存');});
    }catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}
  }
  async function readAnalysis(current=false){
    if(!state.task_id)return;openPhase(2,{auto:!current});const chosen=state.task_id,token=++analysisSerial;
    try{const value=await get('/api/tasks/'+encodeURIComponent(chosen)+(current?'':'?'+new URLSearchParams({revision:app.route.revision})));if(disposed||token!==analysisSerial||state.task_id!==chosen)return;if(current&&value.revision_id!==app.route.revision){app.go({revision:value.revision_id});return;}const task=value.task;
      if(task.status!=='completed'){clearSpec();status.textContent=task.status==='awaiting_host'?'分析要求已保存，等待 Agent 接手。':task.status==='running'?'Agent 已接手，等待分析结果。':`分析尚未完成：${task.status}。请核实或取消原任务。`;return;}
      if(task.kind!=='style_analyze'||task.result_refs.length!==1)throw new Error('分析结果类型不匹配。');
      const result=await get(fileURL(task.result_refs[0]));if(disposed||token!==analysisSerial||state.task_id!==chosen)return;spec={...result,ref:task.result_refs[0]};const ids=refs.filter(row=>result.references.some(ref=>ref.sha256===row.ref.sha256)).map(row=>row.reference.reference_id);if(JSON.stringify(ids)!==JSON.stringify(state.ids)){state.ids=ids;renderReferences();persist();}renderSpec();openPhase(2,{auto:true});status.textContent='分析已返回，尚未确认或修改任何页。';
    }catch(error){status.textContent=readableError(error);}finally{controls();}
  }
  function renderSpec(){specLeases.splice(0).forEach(v=>v.dispose());rules.replaceChildren();choices.clear();const view=imageView(app,{file:spec.breakdown},'截图视觉规范拆解图');specLeases.push(view);
    // §4.3：拆解图在规范核对阶段直接可见并可完整查看（不再默认折叠）。
    rules.append(el('div',{class:'visual-breakdown'},el('h3',{},'截图拆解图'),view.node));
    // 规范先显示借用/保留摘要；点击"调整借用维度"才出现对应编辑器。
    const borrowed=()=>state.spec_edits?.ref===spec.ref.sha256 ? Object.keys(state.spec_edits.dimensions) : ['palette','typography'];
    const summaryNode=el('p',{class:'muted visual-keep-summary'});
    const refreshSummary=()=>{const b=borrowed(),all=Object.keys(spec.dimensions);summaryNode.textContent=`借用：${b.map(k=>names[k]).join('、')||'无'}；保留：${all.filter(k=>!b.includes(k)).map(k=>names[k]).join('、')}。生成仍可能偏离，返回后逐项核对。`;};
    refreshSummary();rules.append(summaryNode);
    const editorBody=el('div',{class:'stack'});
    for(const [key,value] of Object.entries(spec.dimensions)){const check=el('input',{type:'checkbox',checked:state.spec_edits?.ref===spec.ref.sha256 ? key in state.spec_edits.dimensions : ['palette','typography'].includes(key),'aria-label':'借用截图'+names[key]});const text=el('textarea',{rows:2,maxLength:4000,value:state.spec_edits?.ref===spec.ref.sha256 ? state.spec_edits.dimensions[key]??value.summary : value.summary,'aria-label':names[key]+'规范'});choices.set(key,{check,text});
      const detail=el('details',{},el('summary',{},'参考位置与不确定说明'),value.evidence.map(item=>el('p',{},`${item.certainty==='unknown'?'待核实':item.certainty==='approximate'?'近似判断':'已观察'}：${item.observation}`)));
      editorBody.append(el('div',{class:'visual-rule'},el('label',{class:'inline-control'},check,names[key]),text,detail));
      const saveRules=()=>{state.spec_edits={ref:spec.ref.sha256,dimensions:Object.fromEntries([...choices].filter(([,v])=>v.check.checked).map(([key,v])=>[key,v.text.value]))};state.recipe=null;recipe=null;invalidatePlan();refreshSummary();persist();controls();};text.addEventListener('input',saveRules);check.addEventListener('change',saveRules);}
    // 编辑器展开状态跨重渲染保持：切换分析/规范不应把用户刚打开的编辑器合上。
    const editorNode=el('details',{class:'visual-spec-editor'},el('summary',{},'调整借用维度'),editorBody);
    if(specEditorOpen)editorNode.open=true;
    editorNode.addEventListener('toggle',()=>{specEditorOpen=editorNode.open;});
    rules.append(editorNode);
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
    await app.business.submit(editor(),'styles.confirm',{proposal_id:value.proposal_id,base_revision:app.route.revision},{proposal_ref:value.proposal_ref},async result=>{
      state.recipe=result.recipe_id;await completedBusiness(result,{},'视觉规范已确认');});
  }catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}}
  async function planTrial(expanding=false){busy=true;controls();try{
    await app.business.available();const ids=expanding?[...expansion]:[target.value];
    if(!ids.length||!recipe)throw new Error('先确认规范并明确选择目标页。');
    const result=await post('/api/styles/plan',{input:{recipe_id:state.recipe,page_ids:ids,max_calls:ids.length,...(expanding?{adopted_candidate_id:sample.value}:{})}});
    if(disposed)return;if(result.plan.base_revision!==app.route.revision)throw new Error('项目已更新，请保留要求并返回当前版本重新预览。');
    plan=result;planBox.replaceChildren(el('p',{},`试作 ${ids.length} 页，最多 ${ids.length} 次生图；当前稿保留，返回后比较采用。`));
  }catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}}
  async function commitTrial(){if(!plan)return;busy=true;controls();try{const request={plan_id:plan.plan_id,base_revision:plan.plan.base_revision};await app.business.submit(editor(),'changes.commit',request,{plan_id:plan.plan_id,plan:plan.plan},async result=>{state.change_id=result.change_id;await completedBusiness(result,{surface:'runs',task_id:result.task_ids[0]||null,candidate_id:null,runs_area:'tasks'},'试作要求已保存');});}catch(error){status.textContent=readableError(error);}finally{busy=false;controls();}}
  const referencesReady=loadReferences();
  async function hydrate(){const current=editor(),token=++hydrateSerial;loaded=false;analysisSerial++;savedCatalogSerial++;clearSpec();recipe=null;invalidatePlan();cards.reset();candidateRows.replaceChildren();controls();
    try{await Promise.all([current.ready,referencesReady]);if(disposed||token!==hydrateSerial||current!==editor())return;
      const saved=current.draft.content.visual_style;
      if(saved&&Array.isArray(saved.ids)&&Array.isArray(saved.targets)&&typeof saved.instruction==='string')state=structuredClone(saved);
      else if(token>1)state={ids:[],targets:[],instruction:'分析配色与文字层级，保留目标页完整内容',task_id:null,recipe:null};
      if(continuation?.revision===app.route.revision)state=structuredClone(continuation.state);
      state.ids=state.ids.filter(id=>refs.some(row=>row.reference.reference_id===id));requirement.value=state.instruction;target.value=state.targets[0]||'';loaded=true;
      renderReferences();showTarget();renderFutureTargets();if(state.task_id)await readAnalysis();if(disposed||token!==hydrateSerial)return;
      await loadRecipe();if(disposed||token!==hydrateSerial)return;await loadSaved();
      if(continuation?.revision===app.route.revision){persist();if(await saveState()){localStorage.removeItem(continuationKey);continuation=null;}}
      controls();
    }catch(error){if(!disposed&&token===hydrateSerial){loaded=true;status.textContent=readableError(error);controls();}}}
  app.root.addEventListener('draft-editor-replaced',hydrate);app.root.addEventListener('draft-state-changed',draftReady);hydrate();
  app.disposables.push(()=>{disposed=true;phaseReading.dispose();analysisSerial++;hydrateSerial++;savedCatalogSerial++;app.root.removeEventListener('draft-editor-replaced',hydrate);app.root.removeEventListener('draft-state-changed',draftReady);release();specLeases.splice(0).forEach(v=>v.dispose());targetLease?.dispose();});controls();return root;
}
