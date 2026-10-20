import {get, post, readableError, revisionQuery} from './api.js';
import {el, button, modal, field} from './dom.js';
import {projectAPI} from './collaboration-desk.js';

export const supportsInsights = app => app.health.ui_capabilities?.includes('content_insight.v1');
export const details = (title, value) => el('details', {}, el('summary', {}, title), el('pre', {class:'evidence-json'}, JSON.stringify(value,null,2)));
export function reader(app, path, render) {
  const box=el('section',{class:'insight-reading stack','aria-live':'polite'},el('p',{},'正在读取固定版本…'));
  const controller=new AbortController(); let disposed=false;
  app.disposables.push(()=>{disposed=true;controller.abort();});
  get(path,{signal:controller.signal}).then(value=>{if(!disposed)box.replaceChildren(render(value));}).catch(error=>{if(!disposed)box.replaceChildren(el('p',{role:'alert'},readableError(error)));});
  return box;
}
export const issues = value => value.issues?.length ? details('不可读记录与定位依据',value.issues) : null;
const objectText = value => typeof value==='string'?value:Object.entries(value||{}).filter(([k])=>!/(^id$|_id$|_ids$|ref$|refs$)/.test(k)).map(([,v])=>typeof v==='string'?v:Array.isArray(v)?v.map(objectText).join('；'):v&&typeof v==='object'?objectText(v):String(v??'')).filter(Boolean).join(' · ');
const roleNames={claim:'主张',evidence:'证据',qualification:'限定条件',context:'背景',action:'行动',question:'问题'};
const relationNames={supports:'支持',qualifies:'限定',contrasts:'对比',causes:'导致',depends_on:'依赖',explains:'解释',precedes:'先于'};
export function narrativeBody(value) {
  if(!value.data)return el('div',{},el('p',{},'这份主线有记录但暂不可读。'),issues(value));
  const d=value.data,n=d.narrative;
  return el('article',{class:'stack argument-reading'},el('h3',{},d.item.central_statement||'主线尚未形成核心回答'),
    el('p',{},d.item.communication_question||'未记录沟通问题'),
    el('p',{class:'muted'},({current:'当前主线',proposal:'本请求待选',historical:'历史主线'})[d.item.relation]+' · '+(n.maturity==='argument'?'论证稿':'框架稿')),
    el('h4',{},'论点与条件'),n.nodes.map(node=>el('section',{class:'insight-node'},el('strong',{},node.statement||node.node_id),el('p',{},roleNames[node.role]||'论点'),details('完整论点与来源',node))),
    el('h4',{},'论证关系'),n.edges.map(edge=>el('p',{},`${n.nodes.find(x=>x.node_id===edge.from_node_id)?.statement||'原论点不可读'} → ${n.nodes.find(x=>x.node_id===edge.to_node_id)?.statement||'目标论点不可读'} · ${relationNames[edge.relation]||edge.relation}`)),
    el('h4',{},'未决问题'),(n.issues||[]).map(i=>el('p',{class:'read-text'},objectText(i))),
    el('h4',{},'业务替代与代价'),el('p',{class:'muted'},'以下是稿件中的业务选项，不是另一个叙事候选。'),(n.alternatives||[]).map(i=>el('p',{class:'read-text'},objectText(i))),
    el('h4',{},'固定计划与页面职责'),!d.plans.length&&el('p',{},d.plan_status==='unreadable'?'关联计划暂不可读。':'没有记录与这份主线关联的计划。'),
    d.plans.map(plan=>plan.readable?el('div',{},plan.data.planned_roles.map(r=>el('div',{class:'read-text'},el('strong',{},r.role.role),el('p',{},r.role.audience_question),el('p',{},r.role.intended_takeaway),el('p',{class:'muted'},r.page_ref?'已有页面引用':'计划职责，尚无页面'))),details('固定计划原文',plan)):details('不可读计划',plan)),
    details('完整主线、固定引用与决定依据',d),issues(value));
}
export function argumentDesk(app) {
  const revision=app.route.revision;
  const root=el('section',{class:'stack'},el('h2',{tabindex:'-1'},'论证主线'));
  const list=el('div',{class:'stack'}),reading=el('div',{class:'argument-comparison'}); let offset=0;
  function open(left,right=null){app.go({surface:'content',content_area:'arguments',proposal:left,compare_proposal:right,revision});}
  function load(){list.replaceChildren(reader(app,'/api/content/arguments?'+new URLSearchParams({revision,offset,limit:30}),value=>{
    const items=value.data?.items||[];
    const select=el('select',{'aria-label':'选择右侧比较主线'},el('option',{value:''},'选择另一份真实主线'),items.filter(i=>i.readable&&i.ref.sha256!==app.route.proposal).map(i=>el('option',{value:i.ref.sha256},i.central_statement||i.narrative_id)));
    return el('div',{class:'stack'},items.length?items.map(i=>el('div',{class:'insight-list-row'},el('span',{},i.readable?(i.central_statement||'未记录核心回答'):'主线暂不可读'),i.readable&&button(({current:'阅读当前主线',proposal:'阅读待选主线',historical:'阅读历史主线'})[i.relation],()=>open(i.ref.sha256)))):el('p',{},'没有记录论证主线；已有逐页稿和材料仍可阅读。'),
      app.route.proposal&&el('div',{class:'row wrap'},select,button('固定比较两份主线',()=>{if(select.value)open(app.route.proposal,select.value);})),
      el('div',{class:'row wrap'},button('上一组',()=>{offset=Math.max(0,offset-30);load();},false,{disabled:offset===0}),button('下一组',()=>{offset=value.data.pagination.next_offset;load();},false,{disabled:value.data?.pagination.next_offset==null})),issues(value));
  }));}
  for(const sha of [app.route.proposal,app.route.compare_proposal].filter(Boolean))reading.append(reader(app,`/api/content/arguments/${sha}`+revisionQuery(revision),value=>el('div',{class:'stack'},narrativeBody(value),value.data&&!app.route.compare_proposal&&adoptionControls(app,value))));
  root.append(list,reading);load();return root;
}
function adoptionControls(app,value){
  const d=value.data,a=d.adoption;
  const node=el('div',{class:'stack'},details('采用范围与影响',a));
  try{if(localStorage.getItem(`deck-master:direction:${app.info.project_identity}:${d.item.ref.sha256}`))node.append(button('核实或查看原方向操作',()=>directionDialog(app,value)));}catch{node.append(el('p',{},'方向操作缓冲暂不可读。'));}
  if(app.readonly||!(a.can_adopt||a.can_record_direction_decision)) {node.append(el('p',{},'此对象目前只读。'),details('阻断原因',[...a.decision_reason_codes,...a.adoption_reason_codes]));return node;}
  node.append(button(a.can_adopt?'核对并采用此方向':'记录方向决定',()=>directionDialog(app,value),true));return node;
}
function directionDialog(app,initial){
  const sha=initial.data.item.ref.sha256,key=`deck-master:direction:${app.info.project_identity}:${sha}`;
  let saved=null,busy=false,current=initial;
  const status=el('div',{role:'status',class:'stack'}),text=field('确认这份方向的理由',el('textarea',{rows:3,required:true}));
  try{saved=JSON.parse(localStorage.getItem(key)||'null');if(saved?.text)text.input.value=saved.text;}catch{status.append(el('p',{},'原操作草稿无法读取，请核实后再提交。'));return modal('方向操作恢复',status);}
  const persist=()=>{localStorage.setItem(key,JSON.stringify(saved));};
  const submit=button('确认',send,true);
  const dialog=modal('方向决定与采用',el('div',{class:'stack'},el('p',{},'记录决定与采用是两项独立操作。采用不会启动页面制作或生图。'),text.node,details('固定对象与范围',initial.data.adoption),status),[submit],{protectDraft:true});
  function paint(){const adopted=saved?.adopted;submit.hidden=Boolean(adopted);submit.disabled=busy; text.input.disabled=Boolean(saved?.pending||saved?.decision);submit.textContent=saved?.pending?'核实原操作':saved?.decision||current.data.adoption.can_adopt?'确认采用此方向':'确认记录方向决定';if(saved?.decision&&!adopted)status.prepend(el('p',{},'方向决定已记录，采用尚未完成。'));if(adopted)status.replaceChildren(el('p',{},'方向已采用；原比较保持固定。'),button('阅读采用后的版本',()=>{dialog.close();app.go({revision:saved.adopted.revision_id});}));}
  async function send(){if(busy)return;busy=true;paint();try{
    let response;
    if(saved?.pending){
      try{const result=await get('/api/operations/'+encodeURIComponent(saved.pending.payload.operation_id));response=result.operation_result||result;}
      catch(error){if(error.code!=='operation_not_found')throw error;response=await post(saved.pending.path,saved.pending.payload);}
    }else{
      const a=current.data.adoption,isAdopt=Boolean(saved?.decision||a.can_adopt);
      if(isAdopt&&!a.can_adopt)throw Error('采用准入已变化。决定仍保留，请读取当前状态后明确重新确认。');
      if(!isAdopt&&!text.input.value.trim()){text.input.reportValidity();return;}
      const operation_id=crypto.randomUUID(),payload={project_id:app.info.project_id,base_revision:a.assessed_control_revision,operation_id};
      if(isAdopt)Object.assign(payload,{proposal_ref:current.data.item.ref,decision_ref:saved?.decision?.decision_ref||a.existing_decision_ref,write_scope:a.write_scope});
      else payload.decision={topic:'direction',authority_mode:'direct_user',subject_refs:[a.subject_ref],scope:a.write_scope,basis:a.basis,value:{selected:sha},disposition:'accepted',instruction_evidence:{kind:'host_attested_instruction',text:text.input.value,source_locator:'studio:direction:'+operation_id}};
      saved={...saved,text:text.input.value,pending:{kind:isAdopt?'adopt':'decision',path:projectAPI(app)+'/collaboration/'+(isAdopt?'proposal-adoptions':'decisions'),payload}};persist();
      response=await post(saved.pending.path,payload);
    }
    const result=response.result||response,kind=saved.pending.kind;
    saved={...saved,[kind==='decision'?'decision':'adopted']:result,pending:null};persist();
    status.replaceChildren(details('真实操作回执',result));
    if(kind==='decision')current=await get('/api/content/arguments/'+sha+revisionQuery(result.revision_id));
  }catch(error){status.replaceChildren(el('p',{role:'alert'},readableError(error)),el('p',{},'原版本、请求与操作编号已保留。不会自动换用新基线。'));}finally{busy=false;paint();}}
  if(saved?.decision&&!saved?.pending&&!saved?.adopted){busy=true;get('/api/content/arguments/'+sha+revisionQuery(saved.decision.revision_id)).then(value=>{current=value;}).catch(error=>{status.append(el('p',{},readableError(error)));}).finally(()=>{busy=false;paint();});}
  status.append(button('明确读取当前准入以另建采用请求',async()=>{if(busy)return;busy=true;paint();try{if(saved?.pending){try{await get('/api/operations/'+saved.pending.payload.operation_id);throw Error('原操作已有回执，请先核实原操作。');}catch(e){if(e.code!=='operation_not_found')throw e;}saved={...saved,previous_attempts:[...(saved.previous_attempts||[]),saved.pending],pending:null};persist();}current=await get('/api/content/arguments/'+sha);status.prepend(el('p',{},'已读取当前准入，请再次核对范围后明确确认。'));}catch(e){status.prepend(el('p',{},readableError(e)));}finally{busy=false;paint();}}));
  paint();
}
export function taskMethods(app,id,revision){return reader(app,`/api/tasks/${encodeURIComponent(id)}/methods?`+new URLSearchParams({revision,availability:'current'}),value=>{
  const d=value.data;if(!d)return el('p',{},'任务依据暂不可读。');
  return el('div',{class:'stack'},el('h3',{},'任务方法依据'),el('p',{},d.frozen_status==='recorded'?'以下是派发时冻结的有序清单。':'旧任务未记录冻结清单，不套用当前默认方法。'),el('ol',{},d.resources.map(r=>el('li',{},r.display_name||r.id))),details('派发时的版本与字节',d.resources),details('当前安装可用性',d.availability),el('p',{class:'muted'},'资源可读不代表已应用、专业通过或人类认可。缺失或变化请使用下方核实原任务入口。'),issues(value));});}
