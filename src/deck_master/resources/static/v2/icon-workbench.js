import {get, post, canonical, readableError} from './api.js';
import {el, button, modal, version} from './dom.js';
import {imagePool} from './images.js';

// Inert canvas only. Original and SVG regions belong to separate fixed artifacts.
export function iconComparison(app, columns, {highlight = true} = {}) {
  const root=el('div',{class:'icon-comparison stack'}), grid=el('div',{class:'icon-compare-grid'});
  const whole=el('input',{type:'checkbox','aria-label':'显示正常页面尺寸'});
  const zoom=el('select',{'aria-label':'图标局部放大倍数'},[1,2,4,8].map(v=>el('option',{value:v},`${v}×`)));
  const leases=[],views=[];let disposed=false;
  function paint(){for(const v of views){
    const {canvas,bitmap,region,objects}=v,ctx=canvas.getContext('2d');const box=whole.checked?{x:0,y:0,width:1,height:1}:region;
    const w=bitmap.width*box.width,h=bitmap.height*box.height; const requested=whole.checked?Math.min(1,420/w):Number(zoom.value);
    const k=Math.min(requested,2048/w,2048/h);
    canvas.width=Math.max(1,Math.ceil(w*k));canvas.height=Math.max(1,Math.ceil(h*k));
    ctx.drawImage(bitmap,box.x*bitmap.width,box.y*bitmap.height,w,h,0,0,canvas.width,canvas.height);
    if(whole.checked && highlight){ctx.strokeStyle='#b66a21';ctx.lineWidth=2;ctx.strokeRect(region.x*canvas.width,region.y*canvas.height,region.width*canvas.width,region.height*canvas.height);}
    if(highlight && objects){ctx.strokeStyle='#1478ff';ctx.lineWidth=1.5;for(const r of objects){ctx.strokeRect((r.x-box.x)/box.width*canvas.width,(r.y-box.y)/box.height*canvas.height,r.width/box.width*canvas.width,r.height/box.height*canvas.height);}}
  }}
  root.append(el('div',{class:'row wrap'},el('label',{},whole,' 正常页面尺寸'),el('label',{},'局部放大 ',zoom)),grid);
  whole.addEventListener('change',paint);zoom.addEventListener('change',paint);
  for(const [columnIndex,col] of columns.entries()){
    const slot=el('section',{class:'icon-compare-column'},el('h3',{},col.title));grid.append(slot);
    if(!col.file){const missing=el('p',{class:'muted',tabindex:0,'data-icon-column':columnIndex},col.missing||'尚未生成这一版本的预览');missing.addEventListener('keydown',event=>{if(event.key.startsWith('Arrow')){event.preventDefault();event.stopPropagation();}});slot.append(missing);continue;}
    const canvas=el('canvas',{role:'img','aria-label':col.title,tabindex:0,'data-icon-column':columnIndex}),scroll=el('div',{class:'icon-crop-scroll'},canvas);slot.append(scroll);
    canvas.addEventListener('keydown',event=>{const delta={ArrowLeft:[-80,0],ArrowRight:[80,0],ArrowUp:[0,-80],ArrowDown:[0,80]}[event.key];if(delta&&!event.altKey&&!event.ctrlKey&&!event.metaKey){event.preventDefault();event.stopPropagation();scroll.scrollBy(...delta);}});
    try {const lease=imagePool.acquire(app.info.project_identity,col.file,'large');leases.push(lease);
      lease.ready.then(bitmap=>{if(disposed)return;views.push({canvas,bitmap,region:col.region,objects:col.objects});paint();}).catch(error=>{if(!disposed)slot.append(el('p',{class:'field-error'},readableError(error)));});
    }catch(error){slot.append(el('p',{class:'field-error'},readableError(error)));}
  }
  return {node:root,dispose(){disposed=true;leases.splice(0).forEach(v=>v.release());views.splice(0).forEach(v=>{v.canvas.width=v.canvas.height=0;});}};
}

export const sampleKey = sample => JSON.stringify([sample.sample_candidate_id,sample.sample_icon_index]);

export function iconWorkbench(app,data){
  if(!app.business || !app.health.ui_capabilities?.includes('icon_quality.v1') || !['svg','ppt'].includes(app.route.layer))return el('div');
  const root=el('section',{class:'panel icon-workbench','aria-label':'优化图标'}), body=el('div',{class:'panel-body stack'});
  const status=el('p',{role:'status'}), proposals=el('div',{class:'stack'}), recipes=el('div',{class:'stack'});
  const method=el('select',{'aria-label':'图标处理方式'},el('option',{value:'redraw'},'忠实原图精细重绘'),el('option',{value:'standard'},'提出标准图标替换'),el('option',{value:'reuse'},'应用已采用样例到其它页'));
  const asset=el('select',{'aria-label':'建议的标准图标'}), sample=el('select',{'aria-label':'已采用图标样例'}), opinions=el('div',{class:'icon-opinions stack'});
  const selected=new Map();let disposed=false,busy=false,plan=null,samples=[],serial=0;const dialogs=[];
  root.append(el('div',{class:'panel-head'},el('h2',{},'优化图标'),button('刷新图标方案',refresh)),body);
  body.append(el('p',{class:'muted'},'先在画面框选并保存意见，再交给 Agent 定位对象。查看高亮和处理方式后确认范围，返回候选后再决定采用。'),
    el('label',{},'处理方式',method),el('label',{},'标准图标建议',asset),el('label',{},'跨页复用样例',sample),opinions,
    button('复制给 Agent 的图标要求',handoff),status,proposals,recipes);
  function persist(){const e=app.editor;if(!e||e.readonly||disposed)return;e.draft.content.icon_ui={method:method.value,asset:asset.value,sample_identity:samples.find(v=>sampleKey(v)===sample.value)||null,annotation_refs:[...selected.values()].map(n=>n.ref)};e.changed();}
  method.addEventListener('change',persist);asset.addEventListener('change',persist);sample.addEventListener('change',persist);
  function blocked(){return disposed||busy||app.readonly||app.historical||app.editor?.readonly||!app.editor||app.business.entries.size||app.business.loadWarning;}
  async function handoff(){try{
    if(method.value==='reuse'&&!samples.some(v=>sampleKey(v)===sample.value))throw new Error('原样例已失效或旧草稿仅有序号，请重新选择已采用样例。');
    const chosen=[...selected.values()];if(!chosen.length)throw new Error('请先框选、保存意见并在这里选入。');persist();await app.editor.save();
    const payload={project_id:app.info.project_id,base_revision:data.revision_id,page_id:data.page_id,annotation_refs:chosen.map(v=>v.ref),
      requested_method:method.value,suggested_asset_id:method.value==='standard'?asset.value:null,
      adopted_sample:method.value==='reuse'?samples.find(v=>sampleKey(v)===sample.value):null,
      instruction:'读取选定意见，使用 icons inspect 定位真实 SVG 对象，分别绑定原图和 SVG 区域；icons propose 提出方案。等待用户确认后执行已交接的零图像调用 repair 任务。',
      opinions:chosen.map(v=>v.annotation)};
    await navigator.clipboard.writeText(JSON.stringify(payload,null,2));status.textContent='图标要求已复制。尚未启动任务；Agent 提议返回后刷新这里。';
  }catch(error){status.textContent=readableError(error);}}
  async function compare(target,recipe,proposalId){try{
    const [lineage,inspection,proposed]=await Promise.all([get('/api/pages/'+encodeURIComponent(target.page_id)+'/lineage?'+new URLSearchParams({revision:recipe.base_revision})),get('/api/icons/inspect?'+new URLSearchParams({page_id:target.page_id,revision:recipe.base_revision})),post('/api/icons/preview',{proposal_id:proposalId||'icon-proposal-'+recipe.proposal_ref.sha256,page_id:target.page_id})]);
    if(disposed)return;const picker=el('select',{'aria-label':'查看方案中的图标'},target.icons.map((n,i)=>el('option',{value:i},n.label)));
    const slot=el('div');let view;
    function draw(){view?.dispose();const index=Number(picker.value),n=target.icons[index];const objects=n.objects.map(loc=>inspection.objects.find(o=>o.path===loc.path&&o.sha256===loc.sha256)?.region).filter(Boolean);view=iconComparison(app,[{title:'固定原图区域',file:lineage.stages.blueprint.file,region:n.original_region},{title:'当前 SVG 修改对象（蓝框）',file:lineage.stages.svg.file,region:n.svg_region,objects},{title:'标准/复用建议（SVG）',file:proposed.ready_icon_indices.includes(index)?proposed.file:null,region:n.svg_region,missing:'忠实重绘将在 Host 试作返回后比较'}]);slot.replaceChildren(view.node,el('p',{class:'muted'},`${n.label} · ${n.semantic_key} · 目标尺寸 ${Math.round(n.svg_region.width*1000)/10}% × ${Math.round(n.svg_region.height*1000)/10}%`));}
    const dialog=modal('图标范围 · '+target.page_id,el('div',{class:'stack'},picker,slot));draw();picker.addEventListener('change',draw);
    const close=()=>view?.dispose();dialog.addEventListener('close',close,{once:true});dialogs.push(close);
  }catch(error){status.textContent=readableError(error);}}
  async function relocate(record){try{await navigator.clipboard.writeText(JSON.stringify({project_id:app.info.project_id,base_revision:data.revision_id,previous_proposal_id:record.proposal_id,instruction:record.proposal.input.instruction,annotation_refs:record.proposal.input.annotation_refs,next_action:'读取当前版本，重新定位原图和 SVG 对象并提出新方案；原方案仅供固定比较，不沿用旧定位、不自动确认或派发。'},null,2));status.textContent='重新定位要求已复制；等待 Agent 返回新方案。';}catch(error){status.textContent=readableError(error);}}
  async function confirm(record){if(blocked())return;busy=true;try{
    await app.business.submit(app.editor,'icons.confirm',{proposal_id:record.proposal_id,base_revision:record.proposal.base_revision},{proposal_ref:record.proposal_ref},()=>refresh());
  }catch(error){status.textContent=readableError(error);}finally{busy=false;}}
  async function prepare(recipe,ids,impact){if(blocked())return;busy=true;const token=++serial;plan=null;try{
    if(!ids.length)throw new Error('请明确选择本次页面。');
    const response=await post('/api/icons/plan',{input:{recipe_id:recipe.recipe_id,page_ids:ids}});if(disposed||token!==serial)return;
    plan=response;impact.replaceChildren(el('p',{},`${ids.length} 页 SVG 候选 · 0 次图像调用；采用前当前稿不变。`),
      button('确认计划并交接图标修复',()=>commit(response,token),true));
  }catch(error){if(!disposed&&token===serial)impact.replaceChildren(el('p',{class:'field-error'},readableError(error)));}finally{busy=false;}}
  async function commit(value,token){if(blocked()||plan!==value||token!==serial)return;busy=true;try{
    await app.business.submit(app.editor,'changes.commit',{plan_id:value.plan_id,base_revision:value.plan.base_revision},{plan_id:value.plan_id,plan:value.plan},r=>app.go({surface:'runs',revision:r.revision_id,task_id:r.task_ids[0]}));
  }catch(error){status.textContent=readableError(error);}finally{busy=false;}}
  async function refresh(){++serial;plan=null;try{
    const [listing,notes,cat]=await Promise.all([get('/api/icons/list?'+new URLSearchParams({include_stale:'true',...(app.historical?{revision:data.revision_id}:{})})),get('/api/annotations'),get('/api/icons/catalog')]);if(disposed)return;
    asset.replaceChildren(...cat.icons.map(v=>el('option',{value:v.id},v.label)));
    if(listing.samples_unavailable)status.textContent='已采用样例的依据暂不可读取，请核实原记录；原选择与意见保留。';
    samples=listing.samples||[];sample.replaceChildren(el('option',{value:''},'请选择已采用样例'),...samples.map(v=>el('option',{value:sampleKey(v)},`${v.page_id} · ${v.label} · ${v.semantic_key}`)));
    method.querySelector('[value="reuse"]').disabled=!samples.length;sample.disabled=!samples.length;
    const saved=app.editor?.draft.content.icon_ui;if(saved){method.value=saved.method||'redraw';asset.value=saved.asset||cat.icons[0].id;sample.value=saved.sample_identity?sampleKey(saved.sample_identity):'';if(saved.sample!==undefined||saved.sample_identity&&!sample.value)status.textContent='原样例已失效或旧草稿仅有序号，请重新选择；已保存意见仍保留。';}
    opinions.replaceChildren(...notes.annotations.filter(n=>n.annotation.page_id===data.page_id&&['svg','ppt','original_image'].includes(n.annotation.layer)).map(n=>{
      const checked=selected.has(n.ref.sha256)||saved?.annotation_refs?.some(r=>canonical(r)===canonical(n.ref));if(checked)selected.set(n.ref.sha256,n);
      const box=el('input',{type:'checkbox',checked});box.addEventListener('change',()=>{if(box.checked)selected.set(n.ref.sha256,n);else selected.delete(n.ref.sha256);persist();});
      return el('label',{},box,n.annotation.body);
    }));
    const relevant=listing.proposals.filter(v=>v.proposal.input.targets.some(t=>t.page_id===data.page_id));
    proposals.replaceChildren(el('h3',{},'Agent 提出的范围'),...relevant.map(v=>el('article',{class:'stack icon-proposal'},
      el('p',{},v.proposal.input.instruction),el('p',{class:'muted'},({pending:'待确认范围',stale:'方案已过期，请重新定位；固定比较和意见仍保留',confirmed:'范围已确认',handed_off:'已交接修复',dispatch_unknown:'派发状态待核实；原记录与已确认范围保留，请先核实原任务，未确认前不要重复派发。'})[v.status]),...v.proposal.input.targets.map(t=>el('div',{},button(`查看 ${t.page_id} 的图标范围`,()=>compare(t,v.proposal,v.proposal_id)),
        el('p',{},t.icons.map(n=>`${n.label} · ${n.method==='redraw'?'忠实重绘':n.method==='standard'?'标准替换 '+n.asset_id:'复用已采用样例'} · ${n.objects.length} 个对象`).join('；')))),
      v.status==='stale'?button('复制重新定位要求',()=>relocate(v)):button('确认这些图标范围和处理方式',()=>confirm(v),true,{disabled:Boolean(v.status!=='pending'||app.readonly||app.historical||app.editor?.readonly)}))));
    recipes.replaceChildren(el('h3',{},'已确认范围 · 明确选页后交接'));
    for(const record of listing.recipes.filter(v=>v.recipe.input.targets.some(t=>t.page_id===data.page_id))){
      const r=record.recipe,ids=new Set(),impact=el('div',{class:'stack'}),row=el('article',{class:'stack icon-recipe'},el('p',{},r.input.instruction));
      for(const target of r.input.targets){const check=el('input',{type:'checkbox','aria-label':'选入图标页 '+target.page_id});check.addEventListener('change',()=>{if(check.checked)ids.add(target.page_id);else ids.delete(target.page_id);++serial;plan=null;impact.replaceChildren();});row.append(el('label',{},check,target.page_id,' · ',target.icons.map(n=>n.label).join('、')),button('查看 '+target.page_id+' 范围',()=>compare(target,r)));}
      row.append(button('预览选中页图标试作',()=>prepare(r,[...ids],impact),false,{disabled:Boolean(app.readonly||app.historical||app.editor?.readonly)}),impact);recipes.append(row);
    }
    if(!relevant.length)proposals.append(el('p',{class:'muted'},'此版本尚无待确认的图标方案。已保存的意见仍在上方，后台制作状态不会被推测为已启动。'));
  }catch(error){if(!disposed)status.textContent=readableError(error);}}
  const listener=()=>refresh();app.root.addEventListener('business-committed',listener);
  app.disposables.push(()=>{disposed=true;dialogs.forEach(fn=>fn());app.root.removeEventListener('business-committed',listener);});
  app.editor?.ready.then(()=>{if(!disposed)refresh();});return root;
}

export function candidateIconReview(app,record,base,{releaseComparison,restoreComparison}={}){
  if(!record.icon_recipe)return null;
  const root=el('section',{class:'panel stack candidate-icon-review','aria-label':'候选图标实际检查'}),status=el('p',{role:'status'}),slot=el('div');
  const target=record.icon_recipe.input.targets.find(t=>t.page_id===record.candidate.page_id);
  const choose=el('select',{'aria-label':'比较候选中的图标'},target.icons.map((n,i)=>el('option',{value:i},n.label)));
  const layer=el('select',{'aria-label':'图标比较产物'},el('option',{value:'svg'},'SVG'),el('option',{value:'ppt'},'实际 PPT'));
  let preview=null,view=null,disposed=false,timer=null,opened=false;
  const labels={not_requested:'尚未检查',queued:'等待实际 PPT 检查',running:'正在编译和渲染候选 PPT',ready:'工程检查通过 · 待视觉确认',failed:'需修复 · 工程检查未通过',needs_tool:'缺少实际渲染工具',interrupted:'实际检查已中断，请明确重试',busy:'实际检查队列已满，请稍后明确重试。'};
  function describe(value){
    if(value.error?.code==='candidate_preview_state_damaged')return value.status==='busy'
      ?'检查记录损坏，执行状态待核实；原记录已保留，等待现有任务结束后明确重试。'
      :'检查记录损坏，原记录已保留；请明确重试实际 PPT 检查。';
    return (labels[value.status]||value.status)+(value.error?' · '+value.error.message:'');
  }
  function receive(value){if(disposed)return;const changed=canonical([preview?.status,preview?.files,preview?.error])!==canonical([value.status,value.files,value.error]);preview=value;status.textContent=describe(value);
    if(opened&&changed)draw();clearTimeout(timer);if(['queued','running','busy'].includes(value.status))timer=setTimeout(refresh,2000);
  }
  async function refresh(){try{receive(await get('/api/candidate-preview/status?'+new URLSearchParams({candidate_id:record.candidate_id})));
  }catch(error){if(!disposed)status.textContent=readableError(error);}}
  async function check(){try{status.textContent='准备实际检查…';receive(await post('/api/candidate-preview/request',{candidate_id:record.candidate_id,retry:true,wait:false}));}catch(error){if(!disposed)status.textContent=readableError(error);}}
  function draw(){const focused=slot.contains(document.activeElement)?document.activeElement.dataset.iconColumn:null;view?.dispose();const n=target.icons[Number(choose.value)],ppt=layer.value==='ppt';
    view=iconComparison(app,[{title:'固定原图',file:base.stages.blueprint.file,region:n.original_region},
      {title:ppt?'基准实际 PPT':'基准 SVG',file:(ppt?(base.stages.ppt_preview?.applicability?.status==='current'?base.stages.ppt_preview:null):base.stages.svg)?.file,region:n.svg_region,missing:'此固定基准没有有效的实际 PPT 预览'},
      {title:ppt?'候选实际 PPT':'候选 SVG',file:ppt?(preview?.status==='ready'?preview.files?.['candidate.png']?.file:null):record.artifact.file,region:n.svg_region,missing:describe(preview||{status:'not_requested'})}]);slot.replaceChildren(view.node);if(focused!==null)slot.querySelector(`[data-icon-column="${focused}"]`)?.focus();}
  choose.addEventListener('change',()=>{if(opened)draw();});layer.addEventListener('change',()=>{if(opened)draw();});
  root.append(el('h3',{},'候选图标实际检查'),status,el('div',{class:'row wrap'},button('生成或重试实际 PPT 检查',check),
    button('打开局部对照',()=>{opened=true;releaseComparison?.();draw();}),button('关闭局部对照',()=>{opened=false;view?.dispose();slot.replaceChildren();restoreComparison?.();root.querySelectorAll('button')[1]?.focus();})),choose,layer,slot,
    el('p',{class:'muted'},'工程检查不代替视觉认可。请查看方向、状态标记、间距和正常尺寸，再使用候选采用操作。'));
  root.isOpen=()=>opened;
  root.dispose=()=>{disposed=true;clearTimeout(timer);view?.dispose();};app.disposables.push(root.dispose);refresh();return root;
}
